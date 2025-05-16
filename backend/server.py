from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta, timezone
from google.cloud import firestore
from firebase_admin import credentials, firestore, initialize_app
import os
import json
import firebase_admin
app = FastAPI()
cred = credentials.ApplicationDefault()

# Threshold configurations
PAIN_THRESHOLDS = {
    "nerve_pain": {
        "weekly": 3,
        "monthly": 10
    },
    "muscle_strain": {
        "weekly": 4, 
        "monthly": 15
    },
    # Add more pain types as needed
    "default": {
        "weekly": 4,
        "monthly": 12
    }
}

def get_pain_threshold(pain_type):
    """Get thresholds for specific pain type"""
    key = pain_type.lower().replace(" ", "_")
    return PAIN_THRESHOLDS.get(key, PAIN_THRESHOLDS["default"])
def init_firebase():
    if "RENDER" in os.environ:
        # Render.com environment - use the file directly
        return credentials.Certificate("firebase-prod.json")
    else:
        # Local development
        return credentials.Certificate("firebase-prod.json")

if not firebase_admin._apps:
    cred = init_firebase()
firebase_admin.initialize_app(cred)
db = firestore.client()
PORT = int(os.getenv("PORT", 10000))

def count_recurrences(history: list, target_body_part: str, target_condition: str) -> dict:
    now = datetime.now(timezone.utc)
    weekly = 0
    monthly = 0
    first_report_date = None
    
    for entry in history:
        # Normalize field names
        body_part = entry.get("body_part") or entry.get("bodyPart")
        condition = entry.get("condition")
        timestamp = entry.get("timestamp")
        
        if not all([body_part, condition, timestamp]):
            continue
            
        try:
            # Handle different timestamp formats
            if isinstance(timestamp, str):
                # Handle ISO string (frontend format)
                entry_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            elif hasattr(timestamp, 'isoformat'):
                # Already a datetime object (Firestore)
                entry_time = timestamp.replace(tzinfo=timezone.utc)
            else:
                continue
        except Exception as e:
            # Log or handle the exception
            continue
                
        if body_part == target_body_part and condition == target_condition:
            if not first_report_date or entry_time < first_report_date:
                first_report_date = entry_time
                
            if (now - entry_time) <= timedelta(days=7):
                weekly += 1
            if (now - entry_time) <= timedelta(days=30):
                monthly += 1
                
    days_since_first_report = (now - first_report_date).days if first_report_date else 0
    
    return {
        "weekly": weekly,
        "monthly": monthly,
        "show_monthly": days_since_first_report >= 7,  # New flag
        "first_report_days_ago": days_since_first_report
    }
def calculate_dosage(condition, age, weight_kg=None, existing_conditions=[]):
    warnings = []
    
    # Nerve Pain Logic
    if condition == "Nerve Pain":
        if age < 18:
            return "Consult pediatric neurologist", ["Not approved for patients under 18"]
        elif age > 65:
            msg = "Gabapentin 50mg 2x daily"
            if "kidney_disease" in existing_conditions:
                warnings.append("Requires creatinine clearance testing")
            return msg, warnings
        else:
            return "Gabapentin 100mg 3x daily", warnings

    # Muscle Strain Logic
    elif condition == "Muscle Strain":
        if age < 12:
            dosage = f"Acetaminophen {15*(weight_kg or 10)}mg every 6h" if weight_kg else "Acetaminophen 15mg/kg"
            return dosage, ["Avoid NSAIDs under age 12"]
        elif age > 65:
            warnings.append("Monitor for GI bleeding with NSAIDs")
            return "Naproxen 250mg every 12h with food", warnings
        else:
            return "Ibuprofen 400mg every 8h with food", warnings

    return "Consult doctor", []

# API Endpoints
@app.get("/")
async def root():
    return {"message": "AI Server is running"}

@app.post("/predict")
async def predict_risk(data: dict):
    # Input validation
    required_fields = ["body_part", "condition", "severity", "age", "user_id"]
    for field in required_fields:
        if field not in data:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

    try:
        # Get thresholds
        thresholds = get_pain_threshold(data["condition"])
        weekly_threshold = thresholds["weekly"]
        
        # Check consultation status
        user_ref = db.collection("users").document(data["user_id"])
        doc = user_ref.get()
        is_cleared = False
        
        if doc.exists:
            pain_key = f"{data['body_part']}_{data['condition']}".lower().replace(" ", "_")
            threshold_data = doc.to_dict().get("thresholds", {}).get(pain_key, {})
            expires_at = threshold_data.get("expires_at")
            
            if hasattr(expires_at, 'timestamp'):
                expires_at = expires_at.to_datetime()
            
            is_cleared = threshold_data.get("cleared", False) and \
                        expires_at and \
                        expires_at > datetime.now(timezone.utc)

        # Count recent reports
        now = datetime.now(timezone.utc)
        weekly_reports = 0
        monthly_reports = 0
        
        for entry in data.get("history", []):
            entry_body_part = entry.get("body_part") or entry.get("bodyPart")
            entry_condition = entry.get("condition")
            entry_time = entry.get("timestamp")
            
            if not all([entry_body_part, entry_condition, entry_time]):
                continue
                
            try:
                if isinstance(entry_time, str):
                    entry_time = datetime.fromisoformat(entry_time.replace('Z', '+00:00'))
                elif hasattr(entry_time, 'timestamp'):
                    entry_time = entry_time.replace(tzinfo=timezone.utc)
                else:
                    continue
                    
                if (entry_body_part == data["body_part"] and 
                    entry_condition == data["condition"]):
                    if (now - entry_time) <= timedelta(days=7):
                        weekly_reports += 1
                    if (now - entry_time) <= timedelta(days=30):
                        monthly_reports += 1
            except:
                continue

        # Decision
        if weekly_reports >= weekly_threshold and not is_cleared:
            return {
                "threshold_crossed": True,
                "weekly_reports": weekly_reports,
                "monthly_reports": monthly_reports,
                "threshold": weekly_threshold,
                "medication": "CONSULT_DOCTOR_FIRST",
                "is_cleared": False
            }
        else:
            medication, warnings = calculate_dosage(
                data["condition"],
                data["age"],
                data.get("weight"),
                data.get("existing_conditions", [])
            )
            return {
                "medication": medication,
                "warnings": warnings,
                "weekly_reports": weekly_reports,
                "monthly_reports": monthly_reports,
                "threshold": weekly_threshold,
                "threshold_crossed": False,
                "is_cleared": is_cleared
            }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@app.post("/verify-consultation")
async def verify_consultation(data: dict):
    try:
        if "user_id" not in data or "pain_type" not in data:
            raise HTTPException(status_code=400, detail="Missing user_id or pain_type")
        
        pain_key = data["pain_type"].lower().replace(" ", "_")
        user_ref = db.collection("users").document(data["user_id"])
        print(f"Updating consultation status for {data['user_id']} - {pain_key}")
        # Calculate expiration date (30 days from now)
        expires_at = datetime.now(timezone.utc) + timedelta(days=30)
        
        # CORRECTED: Remove 'await' from set()
        user_ref.update({
            f"thresholds.{pain_key}": {
                "cleared": True,
                "cleared_at": firestore.SERVER_TIMESTAMP,
                "expires_at": expires_at
            }
        })
        
        return {
            "status": "success",
            "expires_at": expires_at.isoformat()  # Send back expiration
        }
        
    except Exception as e:
        print(f"Consultation error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT) 

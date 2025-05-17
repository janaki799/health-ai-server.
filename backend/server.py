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
        return credentials.Certificate("firebase-prod.json")
    else:
        return credentials.Certificate("firebase-prod.json")

if not firebase_admin._apps:
    cred = init_firebase()
firebase_admin.initialize_app(cred)
db = firestore.client()
PORT = int(os.getenv("PORT", 10000))

def count_recurrences(history: list, target_body_part: str, target_condition: str, cleared_at: datetime = None) -> dict:
    now = datetime.now(timezone.utc)
    weekly = 0
    monthly = 0
    first_report_date = None
    
    for entry in history:
        body_part = entry.get("body_part") or entry.get("bodyPart")
        condition = entry.get("condition")
        timestamp = entry.get("timestamp")
        
        if not all([body_part, condition, timestamp]):
            continue
            
        try:
            if isinstance(timestamp, str):
                entry_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            elif hasattr(timestamp, 'timestamp'):
                entry_time = timestamp.replace(tzinfo=timezone.utc)
            else:
                continue
        except Exception:
            continue
        if cleared_at and entry_time <= cleared_at:
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
        "show_monthly": days_since_first_report >= 7,
        "first_report_days_ago": days_since_first_report
    }

def calculate_dosage(condition, age, weight_kg=None, existing_conditions=[]):
    warnings = []
    
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

@app.get("/")
async def root():
    return {"message": "AI Server is running"}

@app.post("/predict")
async def predict_risk(data: dict):
    print("\n=== NEW PREDICTION REQUEST ===")
    print("Full request data:", data)
    
    required_fields = ["body_part", "condition", "severity", "age", "user_id"]
    for field in required_fields:
        if field not in data:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
    if not isinstance(data.get("history", []), list):
        raise HTTPException(400, "History must be a list")

    try:
        thresholds = get_pain_threshold(data["condition"])
        weekly_threshold = thresholds["weekly"]
        
        pain_key = f"{data['body_part'].lower().replace(' ', '_')}_{data['condition'].lower().replace(' ', '_')}"
        user_ref = db.collection("users").document(data["user_id"])
        doc = user_ref.get()
       
        is_cleared = bool(cleared_at)
        filtered_history = data.get("history", [])
        
     # Get cleared_at timestamp properly
        cleared_at = None
        if data.get("reset_counts"):
            pain_key = f"{data['body_part'].lower().replace(' ', '_')}_{data['condition'].lower().replace(' ', '_')}"
            user_ref = db.collection("users").document(data["user_id"])
            doc = user_ref.get()
            
            if doc.exists:
                threshold_data = doc.to_dict().get("thresholds", {}).get(pain_key)
                if threshold_data and threshold_data.get("cleared"):
                    cleared_at = threshold_data.get("cleared_at")
                    if isinstance(cleared_at, str):
                        cleared_at = datetime.fromisoformat(cleared_at.replace('Z', '+00:00'))
                    elif hasattr(cleared_at, 'timestamp'):
                        cleared_at = cleared_at.replace(tzinfo=timezone.utc)

        # Filter history
        filtered_history = [
            h for h in data.get("history", [])
            if (not cleared_at or 
                datetime.fromisoformat(h.get("timestamp").replace('Z', '+00:00')) > cleared_at)
        ] if data.get("reset_counts") else data.get("history", [])


        counts = count_recurrences(filtered_history, data["body_part"], data["condition"])
        weekly_reports = counts["weekly"]
        monthly_reports = counts["monthly"]

        if weekly_reports >= weekly_threshold and not is_cleared:
            print("Threshold crossed and not cleared - requiring consultation")
            return {
                "threshold_crossed": True,
                "weekly_reports": weekly_reports,
                "monthly_reports": monthly_reports,
                "threshold": weekly_threshold,
                "medication": "CONSULT_DOCTOR_FIRST",
                "is_cleared":  is_cleared 
            }
        else:
            print("Either threshold not crossed or consultation cleared")
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
        print("Error in prediction:", str(e))
        raise HTTPException(status_code=400, detail=str(e))
    
@app.post("/verify-consultation")
async def verify_consultation(data: dict):
    try:
        if "user_id" not in data or "pain_type" not in data or "body_part" not in data:
            raise HTTPException(status_code=400, detail="Missing required fields")
        
        pain_key = f"{data['body_part'].lower().replace(' ', '_')}_{data['pain_type'].lower().replace(' ', '_')}"
        expires_at = datetime.now(timezone.utc) + timedelta(days=30)
        
        db.collection("users").document(data["user_id"]).update({
            f"thresholds.{pain_key}": {
                "cleared": True,
                "cleared_at": firestore.SERVER_TIMESTAMP,
                "expires_at": expires_at
            }
        })
        
        return {
            "status": "success",
            "expires_at": expires_at.isoformat()
        }
        
    except Exception as e:
        print(f"Consultation error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

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

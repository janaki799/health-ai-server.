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
    weekly = monthly = 0
    first_report_date = None
    
    for entry in history:
        try:
            # Handle timestamp conversion
            entry_time = entry.get('timestamp')
            if isinstance(entry_time, str):
                entry_time = datetime.fromisoformat(entry_time.replace('Z', '+00:00'))
            elif hasattr(entry_time, 'timestamp'):
                entry_time = entry_time.replace(tzinfo=timezone.utc)
            else:
                continue
                
            # Skip entries before clearance if exists
            if cleared_at and entry_time <= cleared_at:
                continue
                
            # Verify entry matches target
            entry_body = entry.get('body_part') or entry.get('bodyPart')
            entry_cond = entry.get('condition')
            if entry_body == target_body_part and entry_cond == target_condition:
                if not first_report_date or entry_time < first_report_date:
                    first_report_date = entry_time
                    
                if (now - entry_time) <= timedelta(days=7):
                    weekly += 1
                if (now - entry_time) <= timedelta(days=30):
                    monthly += 1
                    
        except Exception as e:
            print(f"Error processing entry: {e}")
            continue
            
    return {
        'weekly': weekly,
        'monthly': monthly,
        'show_monthly': (now - first_report_date).days >= 7 if first_report_date else False
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
    try:
        # Validate input
        if not all(k in data for k in ["body_part", "condition", "severity", "age", "user_id"]):
            raise HTTPException(400, "Missing required fields")

        # Get user data
        user_ref = db.collection("users").document(data["user_id"])
        doc = await user_ref.get()
        user_data = doc.to_dict() if doc.exists else {}

        # Check if consultation was completed
        pain_key = f"{data['body_part'].lower().replace(' ', '_')}_{data['condition'].lower().replace(' ', '_')}"
        threshold_data = user_data.get("thresholds", {}).get(pain_key, {})
        
        is_cleared = threshold_data.get("cleared", False) and \
                    (not threshold_data.get("expires_at") or \
                    datetime.now(timezone.utc) < threshold_data.get("expires_at"))

        # Only count recurrences if not cleared
        if not is_cleared:
            counts = count_recurrences(
                data.get("history", []),
                data["body_part"],
                data["condition"],
                threshold_data.get("cleared_at")
            )
        else:
            counts = {'weekly': 0, 'monthly': 0, 'show_monthly': False}

        thresholds = get_pain_threshold(data["condition"])
        
        # Prepare response
        if counts['weekly'] >= thresholds['weekly'] and not is_cleared:
            return {
                "threshold_crossed": True,
                "weekly_reports": counts['weekly'],
                "monthly_reports": counts['monthly'],
                "threshold": thresholds['weekly'],
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
                "weekly_reports": counts['weekly'],
                "monthly_reports": counts['monthly'],
                "threshold": thresholds['weekly'],
                "threshold_crossed": False,
                "is_cleared": is_cleared
            }

    except Exception as e:
        print("Prediction error:", str(e))
        raise HTTPException(400, str(e))
    
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

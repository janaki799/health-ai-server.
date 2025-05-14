from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta, timezone
from google.cloud import firestore
from firebase_admin import credentials, firestore
import os
import firebase_admin
app = FastAPI()
cred = credentials.ApplicationDefault()
if "RENDER" in os.environ:
    cred = credentials.Certificate({
        "type": os.environ.get("TYPE"),
        "project_id": os.environ.get("PROJECT_ID"),
        "private_key_id": os.environ.get("private_key_id"),
        "private_key": os.environ.get("private_key"),
        "client_email": os.environ.get( "client_email"),
        "client_id": os.environ.get("client_id"),
        "auth_uri": os.environ.get("auth_uri"),
        "token_uri": os.environ.get("token_uri"),
        "auth_provider_x509_cert_url": os.environ.get("auth_provider_x509_cert_url"),
        "client_x509_cert_url": os.environ.get("client_x509_cert_url"),
        "universe_domain": os.environ.get("universe_domain"),
        
    })
else:
    cred = credentials.Certificate("medication-provider-firebase-adminsdk-fbsvc-ee3c9059f0.json")
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
        # Initialize defaults
        is_cleared = False
        pain_key = f"{data['body_part']}_{data['condition']}".lower().replace(" ", "_")

        # Get user document
        user_ref = db.collection("users").document(data["user_id"])
        user_doc = user_ref.get()

        # Check clearance status if user exists
        if user_doc.exists:
            user_data = user_doc.to_dict()
            threshold_data = user_data.get("thresholds", {}).get(pain_key, {})
            expires_at = threshold_data.get("expires_at")
            
            if isinstance(expires_at, datetime):
                is_cleared = threshold_data.get("cleared", False) and expires_at > datetime.now(timezone.utc)
            else:
                is_cleared = threshold_data.get("cleared", False)

        # Threshold check
        counts = count_recurrences(data["history"], data["body_part"], data["condition"])
        
        if counts["weekly"] >= 3 and not is_cleared:
            return {
                "emergency": True,
                "medication": "CONSULT_DOCTOR_FIRST",
                "consultation_required": True
            }

        # Normal response
        medication, warnings = calculate_dosage(
            data["condition"],
            data["age"],
            data.get("weight"),
            data.get("existing_conditions", [])
        )
        return {
            "risk_score": data["severity"] * 10,
            "advice": "Medication advised",
            "medication": medication,
            "warnings": warnings
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@app.post("/verify-consultation")
async def verify_consultation(data: dict):
    try:
        # Validate required fields
        if "user_id" not in data or "pain_type" not in data:
            raise HTTPException(status_code=400, detail="Missing user_id or pain_type")
        
        # Update Firestore
        pain_key = data["pain_type"].lower().replace(" ", "_")
        user_ref = db.collection("users").document(data["user_id"])
        
        await user_ref.set({
            "thresholds": {
                pain_key: {
                    "cleared": True,
                    "cleared_at": firestore.SERVER_TIMESTAMP,
                    "expires_at": firestore.SERVER_TIMESTAMP + timedelta(days=30)  # 30-day validity
                }
            }
        }, merge=True)
        
        return {"status": "success", "message": "Consultation verified"}
        
    except Exception as e:
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

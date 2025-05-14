from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta, timezone
from google.cloud import firestore
from firebase_admin import credentials, firestore
import os
import json  # Add this with your other imports
import firebase_admin
app = FastAPI()
cred = credentials.ApplicationDefault()
def init_firebase():
    if "RENDER" in os.environ:
        # Render.com environment
        cred_dict = {
        "type": os.environ.get("service_account"),
        "project_id": os.environ.get("medication-provider"),
        "private_key_id": os.environ.get("ee3c9059f02e7ecbe99dea3c5c68e01b65af6247"),
        "private_key": os.environ.get("-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDbmXVD2g2N0H81\n7L1ROLKE28mrvHqeh+DIKmpqc6LJYqSujyMmGSO8qDqoE9dYn91HGtS+mtFNPa0Y\naF4ktqgCcw6FN5sQ1MUp9XJTPxNHiXUiCc8KIvVTieucwgQIC06aqniZftoyvgmW\n5N24KrnuF4z/LMn7D2ObPvcj1ojfQOE7NRllnceoeNC58AmrfZEaxZCPJUa2HAi6\nsdRLwqvU/k0IV8gdYUMHV8UdbshDd+uwAqbKfcUYuC1rukkCzwakFMSO4Dx5t3Jn\nP/ucbNd+OZhj4ZD9Sg5PdbY0zBDu9HJF+cE/Mw0YSFZY8CbmUCQmc/6fh2C+62wi\nxBX8xrrVAgMBAAECggEAE7S0oi8aEkTIdZVV88jrtCJo+YFDW6CD2lJ8FCtmSz4P\n2x47IDsXSuGpydVl+Kz31V6iAqyv5YeIVe1frVm6v+WFQw0XXC5LtxUweinp1/yM\nx04sBxPWAfYZb4q1g+dH2Xc8tUF94RnOkHzfLJyg7K2uWGOziFT8Mj03Pj8NL0Nf\npDxk9RMZcvSavKZv04wLwr+EmZpNYVx60glYNU3oC+9f9M5IXT+YAUz/gpL5xrTU\nGxqLvZLDLNRHzcw8JCzO9q8cyNhtQE1FVMcWutQ1dxJqfR9l/kDv72D0LBhyU7lK\nd6kl82MzVkrd06s4qr5Gs2U3F8cs0wPRuR65cFWz7QKBgQDwBbKwUILax8JsnAeH\nw+2hYfFvrJNCS1l9oiGbEwgIp+bzhy1BpTzFgem36AF/nEb5li32KdQ+yfn7pROa\nk0UvvjaF7zYjof3z7vl2TVp32DnCk4oT0AWb7cftmi77FO/clo4vdKefXDqx9iF/\nSl8Rhsx0CS5EJ5JRNqMe39Qd9wKBgQDqN7pWj9BV6c7TJptO2DOjrxv7OfB6ZeQC\nkDheisczyiw0iiqa3JyUHi0zOqEc4DBueBalCx1ec64as6B1kVHluGA/lUuLr8jr\nbF+djwUgsRrMpiqEdiO/X1VDW0AhYTH6anEdXl2wyvmoGzLCVo6s86vJOi7yy0t9\n3mW356kqkwKBgQCDIrnT9sjne0hQSpcaqANGrtpYJzN1fvFv4Ir3zNgQ0pst5mbl\nfL/NMQNehRV8gQeOCW0nFwdtHrDDuhcR1vBv+z6SwnUT1seG5MPKzMxmue4kzrMb\nzAWkga8/s4ODjpbWMDOS3etO9/bhkBYRE7MJQlql8vYiKnSYhn9suOGNVQKBgHl6\nU+wnhQ+6R6peYLkBC69+2A1yHJbvF9Z4hLQMWIs09b5+VuChQZjVGe5zHzMB2DzD\njkMlw6LEbu2scrHnoEl8Wnc/8MHPd28bc3AdyLQPB25TVMQFHj9Yq7lWr6lgZvKR\nmH95/S//5oLZMHd5O2DatSOWSNlmtY3f9nPu9F9/AoGAKvn7r8NsEtv66GGnYv7/\nVDUFlxGovUoPuIw2rK2nkeqfCIsLSzEcHsC0Qj5/cUGrm9ID0ckEMvhEHBDe96cB\niRt1TsjX0jHCx0VFKxMaIe8VzMCerW0FWy/orCcnH51EZmikTejhpT5tCp9kVkAo\npXBH7ZUGclEy7c6MVorMAng=\n-----END PRIVATE KEY-----\n"),
        "client_email": os.environ.get( "firebase-adminsdk-fbsvc@medication-provider.iam.gserviceaccount.com"),
        "client_id": os.environ.get("107089371620653630986"),
        "auth_uri": os.environ.get("https://accounts.google.com/o/oauth2/auth"),
        "token_uri": os.environ.get("https://oauth2.googleapis.com/token"),
        "auth_provider_x509_cert_url": os.environ.get("https://www.googleapis.com/oauth2/v1/certs"),
        "client_x509_cert_url":os.environ.get("https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk-fbsvc%40medication-provider.iam.gserviceaccount.com"),
        "universe_domain": os.environ.get("googleapis.com"),
        
    }
    else:
        # Local development
        with open("medication-provider-firebase-adminsdk-fbsvc-ee3c9059f0.json") as f:
            cred_dict = json.load(f)
    
        return credentials.Certificate(cred_dict)

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

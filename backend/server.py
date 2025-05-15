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
def init_firebase():
    if "RENDER" in os.environ:
        # Render.com environment
        cred_dict = {
        "type": os.environ.get("service_account"),
        "project_id": os.environ.get("medication-provider"),
        "private_key_id": os.environ.get( "4c37b920e75d3519598f0152197c3a0a83bcdc43"),
        "private_key": os.environ.get( "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDBdyFwnNguLzbb\n6PqWZyKDggdBqUHr3STrnCA32I8UrBRhwXljT5gMWykdicYEtF3UGei6ozgK8+V9\n/MY9gChraZpIT3ZqvqPIXrjlykN1lTN9NFz+sjrX6RdwY3Ys8uNw8IsgoeEeWBZC\nEAIS57HBKbKsgN8CZGSfsKYCT1PentsRO/DEizFnusruJ1V348WQa2rTaCPEJHPH\nPpMsPcOIRviksdCO/nf/+o5ZKwqW47c+hBtUh3OeGeXV6bPnfri9N/7vUM0WHKQG\nUX2N4Av5d/6516ThSwLKFsmdkFDoF7O85LulV9z1SbS52g4KYundM2gaz1RHjKuf\nr5BgMlkrAgMBAAECggEAIahBk49d1q8VGq4OBmN78CgLbiNtmgSXmzvGqSCOR9jm\nFNmtbhcXSzMC1KY24nOkjTVStUGXCuTCjKgQrvtgTMuK8UCNx+VRphbAkQ2erdKe\nqg4VjaPhM9XT45QSJ6C769aVRcCT4w0NFkIlsjdHx+SitnsXERn5HYUEZIt7elOY\nL8snaXYMeiP2sOV+QWqi7PrN4uimzc246hJ7DtrrXqzMFWcMCJv8d+Gb0ashwU1a\nd20vx0O4F/slznAys/SXaPcXv+I9kJlHljz9EbK9uYRGcXxu6sBPF60fCeXpPNCH\nyt0d3/tn2q2lNci0oVzMQULwQGLZV5JZfMSxWzpCXQKBgQDkjzlhrqP3yrGh/iyO\n5GV18k0RAI3nkHCFEb6p/Pzbhhzavn2gRNOH7bxANkTTyEU8peaPDv+EggvKhpJd\nNO7n2ebsYPEwSnrd2COW0HRxhY+SBcF2mjYE1eCxZh7d+OKpZj2iUzPP6enZkQIN\nwpgJ7AiptlGN/r54zgyMxd72PQKBgQDYsUnr+MhGVDLwFs7o9DliHdDeMQ3RC45U\nZ3GJtMK8nZTruR1sKzoO6eeNhtQKOlA2V+nCu5+i9IJ2v6QDW+tn0SbpbCTR6Xyn\npMZ8fLypO36JSq7UuA+1MdoK/cA2MYcjV60n6ciJEu4Q26EPYPEQpEWNctNOCcOL\nC8lWv69rhwKBgFwh5+2aanpOeMBmJywKoWOkIrDB2nIH5XOerY70bjFHpIYA178t\nP1/B02rG9YOxbUd/UKtGTnXpvjsLeCCeX9eSHOYYReFDhLe8kswOh4HjZvZj35Kh\nozjbxlF8auDrnOLQVfQDOhWLozqSm5NUZ9lIDk3rMoDcuYcU+DYe5Tu5AoGAZhUP\nOAVZhBhCbuyvyPrU1a4qKaJ+Wc7R3F1nFXJ8kxLBh1ML01uB3GjA1uF/ntnd09wS\nmdR93ezGUV7yy0pQWfYkGK8DoYgXW3q6rwasciU+9Tqjpj6X18qGZ8sm8+DdQv8Y\n6cau3DR4xqRQ+ce3iRl6UqqXdRoQbr68uQtQfp0CgYEAzTwdLsC44VlOo7T66Jiw\n0w7A2CtFQOM9wiJzhriUSj1gzyhKWwNA7mKJmQSXXLvG1ZOLgUr6axx+LZqiEnp6\n5BXgeSy4n3Y/eb17/nzIYZMUOOwuOHDxj4QA+yvOlT8sf5yUqsHZPOebjT4q8wr/\nacIw8UAkcqvJr38gSTrCdak=\n-----END PRIVATE KEY-----\n"),
        "client_email": os.environ.get( "firebase-adminsdk-fbsvc@medication-provider.iam.gserviceaccount.com"),
        "client_id": os.environ.get("107089371620653630986"),
        "auth_uri": os.environ.get("https://accounts.google.com/o/oauth2/auth"),
        "token_uri": os.environ.get("https://oauth2.googleapis.com/token"),
        "auth_provider_x509_cert_url": os.environ.get("https://www.googleapis.com/oauth2/v1/certs"),
        "client_x509_cert_url":os.environ.get("https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk-fbsvc%40medication-provider.iam.gserviceaccount.com"),
        "universe_domain": os.environ.get("googleapis.com"),
        
    }
        return credentials.Certificate(cred_dict)
    else:
        # Local development
        with open("firebase-prod.json") as f:
            cred_dict = json.load(f)
    
        return credentials.Certificate(cred_dict)

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

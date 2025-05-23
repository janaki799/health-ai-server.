from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta, timezone
import os

app = FastAPI()

PORT = int(os.getenv("PORT", 10000))

def count_recurrences(history: list, target_body_part: str, target_condition: str) -> dict:
    now = datetime.now(timezone.utc)
    weekly = 0
    monthly = 0
    first_report_date = None
    
    for entry in history:
         # Skip entries marked as "consulted"
        if entry.get("consultedDoctor"):
            continue
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
    required_fields = ["body_part", "condition", "severity", "age"]
    for field in required_fields:
        if field not in data:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

    # Set defaults
    data["history"] = data.get("history", [])
    data["existing_conditions"] = data.get("existing_conditions", [])

    try:
        # Define thresholds
        emergency_thresholds = {
            "Nerve Pain": 3,
            "Muscle Strain": 4
        }
        emergency_threshold = emergency_thresholds.get(data["condition"], 3)

        # Calculate recurrence
        counts = count_recurrences(
            data["history"],
            data["body_part"],
            data["condition"]
        )

        # Dynamic scoring
        base_score = data["severity"] * 10
        age = int(data["age"])
        
        # Age multipliers
        if age < 12: base_score *= 1.3
        elif age > 65: base_score *= 1.4
        
        # Condition multipliers
        if data["condition"] == "Nerve Pain": base_score *= 1.5
        elif data["condition"] == "Muscle Strain": base_score *= 1.2

        # Emergency check
        if counts["weekly"] >= emergency_threshold:
            medication, warnings = calculate_dosage(
                data["condition"],
                age,
                data.get("weight"),
                data["existing_conditions"]
            )
            return {
        "risk_score": 100,
        "advice": f"🚨 EMERGENCY: {data['condition']} occurred {counts['weekly']}x this week",
        "medication": "CONSULT DOCTOR IMMEDIATELY - DO NOT SELF-MEDICATE",  # Critical change
        "warnings": ["Stop all current medications until examined"],
        "threshold_crossed": True,  # New flag
        "reports_this_week": counts["weekly"],  # Add count
        "threshold_limit": emergency_threshold  # Add threshold
    }
        # Standard response
        medication, warnings = calculate_dosage(
            data["condition"],
            age,
            data.get("weight"),
            data["existing_conditions"]
        )
        return {
            "risk_score": min(100, base_score),
            "advice": "Medication advised" if base_score >= 50 else "Home care recommended",
            "medication": medication,
            "warnings": warnings,
            "timeframe": "week_warning" if counts["weekly"] > 0 else "new"
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

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

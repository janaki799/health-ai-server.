from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta, timezone
import os

app = FastAPI()

PORT = int(os.getenv("PORT", 10000))

# Helper Functions
def count_recurrences(history: list, target_body_part: str, target_condition: str) -> dict:
    now = datetime.now(timezone.utc)
    weekly = 0
    monthly = 0
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
                
            if (body_part == target_body_part and 
                condition == target_condition and
                (now - entry_time) <= timedelta(days=7)):
                weekly += 1
                
        except Exception as e:
            print(f"Error parsing timestamp: {e}")
            continue
            
    return {
        "weekly": weekly,
        "monthly": monthly,
        "is_emergency": (  # Add threshold logic
            (target_condition == "Nerve Pain" and weekly >= 3) or
            (target_condition != "Nerve Pain" and weekly >= 5)
        )
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
@app.api_route("/", methods=["GET", "HEAD"])
async def root(request: Request):
    if request.method == "HEAD":
        return {"message": "OK"}
    return {"message": "AI Server is running"}
    
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/predict")
async def predict_risk(data: dict):
    # Input validation
    required_fields = ["body_part", "condition", "severity", "age"]
    for field in required_fields:
        if field not in data:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
          # Mock AI processing (replace with real logic)
     # Mock AI processing (replace with real logic)
        ai_response = {
        "risk_score": 75,
        "advice": "Medication advised",
        "medication": "Ibuprofen 400mg",
        "warnings": [],
        "timeframe": "new"
    }

        return ai_response  # FastAPI auto-sends 200 status for successful returns
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
        "advice": f"🚨 EMERGENCY: {data['condition']} occurred {counts['weekly']}x this week - CONSULT DOCTOR IMMEDIATELY",
        "medication": "DO NOT SELF-MEDICATE - Requires professional evaluation",  # Critical change
        "warnings": ["Stop all current medications until examined"],
        "timeframe": "week_emergency",
        "requires_emergency_care": True,  # New flag for frontend
        "threshold_crossed": counts["is_emergency"],
        "reports_this_week": counts["weekly"],
        "threshold_limit": 3 if data["condition"] == "Nerve Pain" else 5,
        "show_normal_recommendation": not counts["is_emergency"]
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

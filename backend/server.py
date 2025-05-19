from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta, timezone
from fastapi import Request
from typing import Dict, Any
import os
import json  # Added for JSON handling

app = FastAPI()

PORT = int(os.getenv("PORT", 10000))

threshold_resets: Dict[str, Dict[str, Any]] = {}

@app.post("/reset-threshold")
async def reset_threshold(request: Request):
    data = await request.json()
    user_id = data.get("userId")
    body_part = data.get("bodyPart")
    condition = data.get("condition")

    if not all([user_id, body_part, condition]):
        raise HTTPException(status_code=400, detail="Missing required fields")

    key = f"{user_id}_{body_part}_{condition}"
    threshold_resets[key] = {
        "reset_at": datetime.now(timezone.utc),
        "count": 0
    }

    return {
        "success": True,
        "reset_at": threshold_resets[key]["reset_at"].isoformat(),
        "new_count": 0

    }

# Modify the count_recurrences function:
def count_recurrences(history: list, target_body_part: str, target_condition: str, user_id: str) -> dict:
    now = datetime.now(timezone.utc)
    weekly = 0
    monthly = 0
    first_report_date = None
    
    # Get reset time if exists
    reset_key = f"{user_id}_{target_body_part}_{target_condition}"
    reset_time = threshold_resets.get(reset_key, {}).get("reset_at")
    
    # Sort history by timestamp (newest first)
    sorted_history = sorted(
        [h for h in history if h.get('timestamp')],
        key=lambda x: x['timestamp'],
        reverse=True
    )
    
    for entry in sorted_history:
        body_part = entry.get("body_part") or entry.get("bodyPart", "")
        condition = entry.get("condition", "")
        timestamp = entry.get("timestamp")
        
        if not all([body_part, condition, timestamp]):
            continue
            
        try:
            if isinstance(timestamp, str):
                entry_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            elif hasattr(timestamp, 'isoformat'):
                entry_time = timestamp.replace(tzinfo=timezone.utc)
            else:
                continue
                
            # Skip entries before reset if reset exists
            if reset_time and entry_time <= reset_time:
                continue
                
            if body_part == target_body_part and condition == target_condition:
                if not first_report_date or entry_time < first_report_date:
                    first_report_date = entry_time
                    
                if (now - entry_time) <= timedelta(days=7):
                    weekly += 1
                if (now - entry_time) <= timedelta(days=30):
                    monthly += 1
                    
        except Exception:
            continue
    
    days_since_first_report = (now - first_report_date).days if first_report_date else 0
    
    return {
        "weekly": weekly,
        "monthly": monthly,
        "show_monthly": days_since_first_report >= 7,
        "was_reset": bool(reset_time)
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

@app.post("/predict")
async def predict_risk(request: Request):
    try:
        data = await request.json()
        
        # Set defaults and validate
        data.setdefault("history", [])
        data.setdefault("existing_conditions", [])
        data.setdefault("has_consulted_doctor", False)
        data.setdefault("weight", None)
        data.setdefault("userId", "anonymous")
        data.setdefault("age", 30)  # Default age if not provided
        
        # Validate required fields
        required_fields = ["body_part", "condition", "severity"]
        for field in required_fields:
            if field not in data:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Missing required field: {field}"
                )
            
        # Validate history entries
        for entry in data["history"]:
            entry.setdefault("body_part", "")
            entry.setdefault("condition", "")
            entry.setdefault("severity", 0)
            entry.setdefault("timestamp", datetime.now(timezone.utc).isoformat())

        # Set thresholds
        emergency_thresholds = {
            "Nerve Pain": 3,
            "Muscle Strain": 4
        }
        emergency_threshold = emergency_thresholds.get(data["condition"], 3)

        # Get counts (this now properly handles resets)
        counts = count_recurrences(
            data["history"],
            data["body_part"],
            data["condition"],
            data["userId"]
        )

        # Calculate base risk score
        base_score = data["severity"] * 10
        age = int(data["age"])
        
        # Apply modifiers
        if age < 12: base_score *= 1.3
        elif age > 65: base_score *= 1.4
        
        if data["condition"] == "Nerve Pain": base_score *= 1.5
        elif data["condition"] == "Muscle Strain": base_score *= 1.2

        # Prepare base response
        response = {
            "risk_score": min(100, base_score),
            "reports_this_week": counts["weekly"],
            "reports_this_month": counts["monthly"],
            "threshold_limit": emergency_threshold,
            "threshold_crossed": counts["weekly"] >= emergency_threshold,
            "was_reset": counts["was_reset"],
            "show_monthly": counts["show_monthly"]
        }

        # Emergency case
        if response["threshold_crossed"] and not data["has_consulted_doctor"]:
            response.update({
                "advice": f"🚨 EMERGENCY: {data['condition']} occurred {counts['weekly']}x this week",
                "medication": "CONSULT DOCTOR IMMEDIATELY - DO NOT SELF-MEDICATE",
                "warnings": ["Stop all current medications until examined"]
            })
            return response

        # Normal case - get medication recommendations
        medication, warnings = calculate_dosage(
            data["condition"],
            age,
            data.get("weight"),
            data["existing_conditions"]
        )

        response.update({
            "advice": "Medication advised" if base_score >= 50 else "Home care recommended",
            "medication": medication,
            "warnings": warnings,
            "threshold_warning": counts["weekly"] >= emergency_threshold - 1
        })

        # If user has consulted doctor, ensure UI shows proper count
        if data["has_consulted_doctor"]:
            response.update({
                "reports_this_week": 1,
                "threshold_crossed": False,
                "threshold_warning": False
            })

        return response

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)

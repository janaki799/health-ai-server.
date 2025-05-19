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
    key = f"{user_id}_{target_body_part}_{target_condition}"
    reset_data = threshold_resets.get(key, {})
    reset_time = reset_data.get("reset_at") if reset_data else None

    now = datetime.now(timezone.utc)
    weekly = 0
    monthly = 0
    first_report_date = None
    
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
        "was_reset": bool(reset_data),
        "first_report_days_ago": days_since_first_report,
        "show_monthly": days_since_first_report >= 7
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
        
        # Validate required fields
        required_fields = ["body_part", "condition", "severity"]
        for field in required_fields:
            if field not in data:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Missing required field: {field}"
                )
        
        # Set default age if not provided
        if "age" not in data:
            data["age"] = 30
            
        # Validate history entries
        for entry in data["history"]:
            entry.setdefault("body_part", "")
            entry.setdefault("condition", "")
            entry.setdefault("severity", 0)
            entry.setdefault("timestamp", datetime.now(timezone.utc).isoformat())

        emergency_thresholds = {
            "Nerve Pain": 3,
            "Muscle Strain": 4
        }
        emergency_threshold = emergency_thresholds.get(data["condition"], 3)

        counts = count_recurrences(
            data["history"],
            data["body_part"],
            data["condition"],
            data["userId"]
        )

        base_score = data["severity"] * 10
        age = int(data["age"])
        
        if age < 12: base_score *= 1.3
        elif age > 65: base_score *= 1.4
        
        if data["condition"] == "Nerve Pain": base_score *= 1.5
        elif data["condition"] == "Muscle Strain": base_score *= 1.2

        if counts["weekly"] >= emergency_threshold and not data.get("has_consulted_doctor"):
            return {
                "risk_score": 100,
                "advice": f"🚨 EMERGENCY: {data['condition']} occurred {counts['weekly']}x this week",
                "medication": "CONSULT DOCTOR IMMEDIATELY - DO NOT SELF-MEDICATE",
                "warnings": ["Stop all current medications until examined"],
                "threshold_crossed": True,
                "reports_this_week": counts["weekly"],
                "threshold_limit": emergency_threshold
            }

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
            "timeframe": "week_warning" if counts["weekly"] > 0 else "new",
            "threshold_crossed": False,
            "override_threshold": data.get("has_consulted_doctor", False)
        }

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)

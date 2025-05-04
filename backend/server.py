from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone  # Add timezone import
import os

app = FastAPI()

PORT = int(os.getenv("PORT", 10000))

# Pain-type danger thresholds
PAIN_RULES = {
    "Nerve Pain": {"weekly": 3, "monthly": 3},
    "Muscle Strain": {"weekly": 4, "monthly": 4},
    "Headache": {"weekly": 10, "monthly": 10}
}

def count_recurrences(history: list, target_body_part: str, target_condition: str) -> dict:
    """Counts recurrences in last 7/30 days from CURRENT TIME"""
    now = datetime.now(timezone.utc)  # Make this offset-aware
    
    weekly = monthly = total = 0

    for entry in history:
        # Skip if not the same body part AND condition
        if (entry["body_part"] != target_body_part or 
            entry["condition"] != target_condition):
            continue
        try:
            # Ensure timestamp is properly parsed as offset-aware
            entry_time = datetime.fromisoformat(entry["timestamp"])
            if entry_time.tzinfo is None:
                entry_time = entry_time.replace(tzinfo=timezone.utc)
                
            if now - entry_time > timedelta(days=30):
                continue

            total += 1
            if now - entry_time <= timedelta(days=7):
                weekly += 1
            monthly += 1
        except (ValueError, TypeError) as e:
            print(f"Error parsing timestamp {entry['timestamp']}: {str(e)}")
            continue

    return {"weekly": weekly, "monthly": monthly, "total": total}

@app.get("/")
async def root():
    return {"message": "AI Server is running"}
    
@app.post("/predict")
async def predict_risk(data: dict):
    print("Received data:", data)
    required_fields = ["body_part", "condition", "severity", "history"]
    for field in required_fields:
        if field not in data:
            raise HTTPException(
                status_code=400, 
                detail=f"Missing required field: {field}"
            )
    try:

        validated_history = []
        for entry in data["history"]:
            if not all(k in entry for k in ["body_part", "condition", "timestamp"]):
                continue  # Skip invalid entries
                
            # Convert timestamp to ISO format if needed
            if "T" not in entry["timestamp"]:
                try:
                    entry["timestamp"] = datetime.fromisoformat(entry["timestamp"]).isoformat()
                except:
                    continue
            
            validated_history.append(entry)

            counts = count_recurrences(
            validated_history,
            data["body_part"],
            data["condition"]
        )
        print("Counted recurrences:", counts)  
        condition = data["condition"]
        rules = PAIN_RULES.get(condition, {"weekly": 3, "monthly": 5})  # Default thresholds
        
        # 1. Weekly emergency check
        if counts["weekly"] >= rules["weekly"]:
            return {
                "risk_score": 100,
                "advice": f"🚨 EMERGENCY: {condition} repeated {counts['weekly']}x this week. CONSULT DOCTOR NOW.",
                "timeframe": "week_emergency",
                "recurrence_count": counts["weekly"]
            }
            
        # 2. Weekly warning (approaching threshold)
        remaining_weekly = rules["weekly"] - counts["weekly"]
        if remaining_weekly == 1 and counts["weekly"] > 0:
            return {
                "risk_score": 80,
                "advice": f"⚠️ WARNING: {condition} repeated {counts['weekly']}x this week. "
                         f"If it happens 1 more time, consult a doctor immediately.",
                "timeframe": "week_warning",
                "recurrence_count": counts["weekly"]
            }
            
        # 3. Monthly threshold
        if counts["monthly"] >= rules["monthly"]:
            return {
                "risk_score": 70,
                "advice": f"⚠️ {condition} repeated {counts['monthly']}x this month. Monitor closely.",
                "timeframe": "month_warning",
                "recurrence_count": counts["monthly"]
            }
            
        # 4. Recurring but below thresholds
        if counts["total"] > 0:
            return {
                "risk_score": min(30 + (counts["total"] * 10), 70),
                "advice": f"ℹ️ You've had {condition} {counts['total']}x recently. "
                         f"Limit is {rules['weekly']}x/week for doctor consultation.",
                "timeframe": "recurring",
                "recurrence_count": counts["total"]
            }
            
        # 5. First-time report
        return {
            "risk_score": min(data["severity"] * 10, 70),
            "advice": "Take medication" if data["severity"] >= 5 else "Rest at home",
            "timeframe": "new",
            "recurrence_count": 0
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# CORS setup
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

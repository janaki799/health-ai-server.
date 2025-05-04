from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timedelta
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
    now = datetime.utcnow()
    weekly = monthly = total = 0

    for entry in history:
        # Skip if not the same body part AND condition
        if (entry["body_part"] != target_body_part or 
            entry["condition"] != target_condition):
            continue
            
        entry_time = datetime.fromisoformat(entry["timestamp"])
        if now - entry_time > timedelta(days=30):
            continue

        total += 1
        if now - entry_time <= timedelta(days=7):
            weekly += 1
        monthly += 1

    return {"weekly": weekly, "monthly": monthly, "total": total}

@app.post("/predict")
async def predict_risk(data: dict):
    print("Received data:", data)
    try:
        counts = count_recurrences(
            data["history"],
            data["body_part"],
            data["condition"]
        )
        print("Counted recurrences:", counts)  
        condition = data["condition"]
        rules = PAIN_RULES.get(condition)
        
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

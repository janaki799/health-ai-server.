from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
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
    """Count symptom recurrences in last 7/30 days"""
    now = datetime.now(timezone.utc)
    weekly = monthly = total = 0

    for entry in history:
        # Skip if not matching the current symptom
        if (entry["body_part"] != target_body_part or 
            entry["condition"] != target_condition):
            continue
            
        try:
            # Parse timestamp (handle both with/without timezone)
            entry_time = datetime.fromisoformat(entry["timestamp"])
            if entry_time.tzinfo is None:
                entry_time = entry_time.replace(tzinfo=timezone.utc)

            # Skip if older than 30 days
            if now - entry_time > timedelta(days=30):
                continue

            total += 1
            if now - entry_time <= timedelta(days=7):
                weekly += 1
            monthly += 1
            
        except (ValueError, TypeError) as e:
            print(f"Error parsing timestamp {entry['timestamp']}: {str(e)}")
            continue

    return {
        "weekly": weekly,
        "monthly": monthly,
        "total": total
    }

def calculate_risk_score(condition, severity, history_counts):
    base_score = severity * 10
    
    # Apply recurrence multipliers
    if history_counts["weekly"] > 0:
        base_score *= 1 + (history_counts["weekly"] * 0.2)
    
    # Condition-specific adjustments
    risk_factors = {
        "Nerve Pain": 1.5,
        "Muscle Strain": 1.3,
        "Headache": 1.2
    }
    
    return min(100, base_score * risk_factors.get(condition, 1.0))

def generate_advice(condition, risk_score, history):
    advice_templates = {
        "high": f"🚨 Seek medical attention within {'24 hours' if 'Pain' in condition else '3 days'}",
        "medium": "⚠️ Schedule a doctor visit if symptoms persist",
        "low": "ℹ️ Rest and monitor. Consider {remedy}"
    }
    
    remedies = {
        "Nerve Pain": "applying heat",
        "Muscle Strain": "ice pack",
        "Headache": "OTC pain relievers"
    }
    
    if risk_score > 80:
        return advice_templates["high"]
    elif risk_score > 50:
        patterns = detect_symptom_patterns(history)
        if patterns:
            return f"Recurring pattern detected. " + advice_templates["medium"]
        return advice_templates["medium"]
    else:
        return advice_templates["low"].format(
            remedy=remedies.get(condition, "rest")
        )

def detect_symptom_patterns(history):
    patterns = {}
    for entry in history:
        key = f"{entry['body_part']}-{entry['condition']}"
        patterns[key] = patterns.get(key, 0) + 1
    return {k: v for k, v in patterns.items() if v >= 2}

@app.get("/")
async def root():
    return {"message": "AI Server is running"}

@app.get("/version")
async def version():
    return {"version": "2.0", "features": ["AI Symptom Analysis"]}
    
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
        # Data validation and preprocessing
        validated_history = []
        for entry in data["history"]:
            if not all(k in entry for k in ["body_part", "condition", "timestamp"]):
                continue
                
            try:
                entry["timestamp"] = datetime.fromisoformat(entry["timestamp"]).isoformat()
            except:
                continue
            
            validated_history.append(entry)

        # Calculate risk score
        counts = count_recurrences(
            validated_history,
            data["body_part"],
            data["condition"]
        )
        
        risk_score = calculate_risk_score(
            data["condition"],
            data["severity"],
            counts
        )

        # Generate personalized advice
        advice = generate_advice(
            data["condition"],
            risk_score,
            validated_history
        )

        return {
            "risk_score": min(100, risk_score),
            "advice": advice,
            "timeframe": "week_emergency" if risk_score > 80 else 
                        "week_warning" if risk_score > 50 else "normal",
            "recurrence_count": counts["total"]
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

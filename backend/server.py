from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import numpy as np
import os

app = FastAPI()

PORT = int(os.getenv("PORT", 10000))

# Update your server.py CORS settings to:
# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins (for development only)
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

class SymptomData(BaseModel):
    user_id: str
    body_part: str
    condition: str
    severity: int
    history: list  # Past symptoms from Firestore

@app.get("/")
async def root():
    return {"message": "AI Server is running"}

    @app.options("/predict")
async def options_handler():
    return {"message": "OK"}

@app.post("/predict")
async def predict_risk(data: SymptomData):
    try:
        # Mock AI logic (replace with real model)
        risk_score = np.random.uniform(0, 1)  # Placeholder
        return {
            "risk_score": risk_score,
            "advice": "Monitor symptoms for 48 hours" if risk_score < 0.5 
                     else "Consult a doctor soon"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)  # Use PORT variable here
import React, { useState, useEffect } from 'react';
import { doc, getDoc, setDoc, serverTimestamp } from "firebase/firestore";
import { db } from "../firebase";

const AdviceDisplay = ({ 
  isConsulted,
  setIsConsulted,
  prediction, 
  userId, 
  painType, 
  bodyPart,  // Add this prop
  onConsultationSuccess,
  refreshKey // Add this prop
}) => {
  const [isLoading, setIsLoading] = useState(false);
  const [consultationError, setConsultationError] = useState(null);
  const [localConsulted, setLocalConsulted] = useState(false); // Add this line

// Update the handleConsultationConfirm function:
// In AdviceDisplay.js
const handleConsultationConfirm = async () => {
  setIsLoading(true);
  setConsultationError(null);

  try {
    const painKey = `${bodyPart.toLowerCase().replace(/ /g, '_')}_${painType.toLowerCase().replace(/ /g, '_')}`;
    const expiresAt = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000);
    
    // 1. First update Firestore
    await setDoc(
      doc(db, "users", userId), 
      {
        [`thresholds.${painKey}`]: {
          cleared: true,
          cleared_at: serverTimestamp(),
          expires_at: expiresAt,
          weekly_reports: 0,  // Add this
          monthly_reports: 0   // Add this
        }
      }, 
      { merge: true }
    );
    
          await onConsultationSuccess();
    
  } catch (error) {
    console.error("Consultation error:", error);
    setConsultationError("Failed to confirm consultation. Please try again.");
    // Reset consulted state on error
    setLocalConsulted(false);
    setIsConsulted(false);
  }
};
// In AdviceDisplay.js, enhance error handling:

// Update useEffect to use checkConsultationStatus
  useEffect(() => {
    const checkConsultation = async () => {
      if (!userId || !painType || !bodyPart) return;
      
      const painKey = `${bodyPart.toLowerCase().replace(/ /g, '_')}_${painType.toLowerCase().replace(/ /g, '_')}`;
      const docSnap = await getDoc(doc(db, "users", userId));
      
      if (docSnap.exists()) {
        const thresholdData = docSnap.data().thresholds?.[painKey];
        if (thresholdData?.cleared) {
          const now = new Date();
          let expiresAt = thresholdData.expires_at?.toDate?.() || thresholdData.expires_at;
          setLocalConsulted(!expiresAt || new Date(expiresAt) > now);
          setIsConsulted(!expiresAt || new Date(expiresAt) > now);
        }
      }
    };
    
    checkConsultation();
  }, [userId, bodyPart, painType, refreshKey, setIsConsulted]);
 // Add checkConsultationStatus
  useEffect(() => {
  console.log("AdviceDisplay state update:", {
    isConsulted,
    isLoading,
    prediction,
    bodyPart,
    painType
  });
}, [isConsulted, isLoading, prediction, bodyPart, painType]);
if (isLoading) {
  return <div style={{padding: '20px', textAlign: 'center'}}>
    <div className="spinner"></div>
    <p>Updating consultation status...</p>
  </div>;
}
// Only show warning if threshold crossed and not consulted
if (prediction?.threshold_crossed && !(localConsulted || prediction?.is_cleared)) {
  return (
    <div style={{ 
      borderLeft: `4px solid ${isConsulted ? 'green' : 'red'}`, 
      padding: '15px',
      margin: '20px 0'
    }}>
      {isConsulted ? (
        <div style={{ color: 'green' }}>
          ✓ Doctor consultation confirmed. Medication unlocked.
        </div>
      ) : (
        <>
          <h4>🚨 Doctor Consultation Required</h4>
          <p>You've reported this {prediction.weekly_reports}/{prediction.threshold} times.</p>
          {consultationError && <p style={{ color: 'red' }}>{consultationError}</p>}
          <button 
          onClick={handleConsultationConfirm}
          disabled={isLoading}
        style={{
           padding: '8px 16px',
    backgroundColor: '#1976d2',
    color: 'white',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    marginTop: '10px',
    position: 'relative',
    opacity: isLoading ? 0.8 : 1,
    transition: 'opacity 0.3s ease'
        }}
      >
         {isLoading ? (
    <>
      <span style={{ visibility: 'hidden' }}>I've Consulted a Doctor</span>
      <div style={{
        position: 'absolute',
        top: '50%',
        left: '50%',
        transform: 'translate(-50%, -50%)',
        width: '16px',
        height: '16px',
        border: '2px solid rgba(255,255,255,0.3)',
        borderTopColor: 'white',
        borderRadius: '50%',
        animation: 'spin 1s linear infinite'
      }}></div>
    </>
  ) : "I've Consulted a Doctor"}
</button>
        </>
      )}
    </div>
  );
}

// Show medication if not blocked or already consulted
return (
  <div>
    {prediction?.medication && prediction.medication !== "CONSULT_DOCTOR_FIRST" && (
      <div style={{ borderLeft: '4px solid green', padding: '15px', margin: '20px 0' }}>
        <h4>Recommended Medication</h4>
        <p>{prediction.medication}</p>
        {prediction.warnings?.map((warning, i) => (
          <p key={i} style={{ color: 'orange' }}>⚠️ {warning}</p>
        ))}
      </div>
    )}
  </div>
);
}

export default AdviceDisplay;  

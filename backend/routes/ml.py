from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict
import joblib
import json
from pathlib import Path
import pandas as pd
from datetime import datetime

router = APIRouter(prefix="/api/ml", tags=["ML"])

MODEL_DIR = Path('/app/models')
model = None
metadata = None

# Chargement du modèle au démarrage
try:
    model = joblib.load(MODEL_DIR / 'lgb_model.pkl')
    with open(MODEL_DIR / 'metadata.json') as f:
        metadata = json.load(f)
    print(f"✅ Modèle ML chargé v{metadata['version']}")
except Exception as e:
    print(f"⚠️  Modèle ML non disponible: {e}")

class ScoringRequest(BaseModel):
    biens: List[Dict]

class ScoringResult(BaseModel):
    id_bien: str
    score_vente_6m: float
    niveau_priorite: str
    raisons: List[str]

@router.get("/health")
async def health():
    """Santé du modèle ML"""
    if model is None:
        raise HTTPException(503, "Modèle non chargé")
    return {
        "status": "ok",
        "version": metadata.get('version'),
        "features": len(metadata.get('features', []))
    }

@router.post("/score", response_model=List[ScoringResult])
async def score_biens(req: ScoringRequest):
    """Score des biens pour prédire probabilité de vente"""
    if model is None:
        raise HTTPException(503, "Modèle non chargé")
    
    try:
        df = pd.DataFrame(req.biens)
        features = metadata['features']
        
        # Ajouter colonnes manquantes
        for col in features:
            if col not in df.columns:
                df[col] = 0
        
        X = df[features].fillna(0)
        scores = model.predict(X)
        
        results = []
        for idx, score in enumerate(scores):
            bien = req.biens[idx]
            
            # Niveau de priorité
            if score > 0.7:
                priorite = "TRÈS HAUTE"
            elif score > 0.5:
                priorite = "HAUTE"
            elif score > 0.3:
                priorite = "MOYENNE"
            else:
                priorite = "FAIBLE"
            
            # Raisons
            raisons = []
            tenure = bien.get('tenure_days', 0)
            if tenure > 2555:
                raisons.append(f"Détention longue ({tenure//365} ans)")
            elif tenure > 1825:
                raisons.append(f"Détention moyenne ({tenure//365} ans)")
            
            if bien.get('repeat_sale_flag', 0) == 1:
                raisons.append("Bien déjà revendu")
            
            if not raisons:
                raisons = ["Score basé sur analyse multi-critères"]
            
            results.append(ScoringResult(
                id_bien=bien.get('id_bien', f'bien_{idx}'),
                score_vente_6m=float(score),
                niveau_priorite=priorite,
                raisons=raisons[:3]
            ))
        
        return sorted(results, key=lambda x: x.score_vente_6m, reverse=True)
        
    except Exception as e:
        raise HTTPException(500, f"Erreur: {str(e)}")

@router.get("/model/info")
async def model_info():
    """Informations sur le modèle"""
    if model is None or metadata is None:
        raise HTTPException(503, "Modèle non chargé")
    return metadata

"""
Route : /api/analyze/{code_postal}
Retourne les biens d'un CP triés par probabilité de revente P6 (prob_sell_6m).
Utilise le modèle LightGBM (AUC=0.88) pour scorer chaque bien.
"""

import logging
import math
import pickle
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
from fastapi import APIRouter, Query, HTTPException
from sqlalchemy import text

router = APIRouter(prefix="/api", tags=["analyze"])
logger = logging.getLogger(__name__)

# ── Chargement du modèle LightGBM (une seule fois au démarrage) ──────────────
_MODEL = None
_MODEL_PATH = Path("/app/models/lgb_model.pkl")

def _load_model():
    global _MODEL
    if _MODEL is None:
        try:
            with open(_MODEL_PATH, "rb") as f:
                _MODEL = pickle.load(f)
            logger.info("✅ Modèle LightGBM chargé depuis lgb_model.pkl")
        except Exception as e:
            logger.error(f"❌ Impossible de charger lgb_model.pkl : {e}")
    return _MODEL

# ── Calcul des features ───────────────────────────────────────────────────────
def _build_features(row) -> list:
    tenure_days = (row.duree_detention_estimee or 0) * 365.25
    prix = row.valeur_fonciere or 0
    surface = row.surface_reelle or 1
    prix_m2 = prix / surface if surface > 0 else 0
    is_maison = 1 if row.type_local == "Maison" else 0
    is_appart = 1 if row.type_local == "Appartement" else 0
    try:
        if row.date_mutation:
            if isinstance(row.date_mutation, str):
                month = datetime.fromisoformat(row.date_mutation).month
            else:
                month = row.date_mutation.month
        else:
            month = 6
    except Exception:
        month = 6
    month_sin = math.sin(2 * math.pi * month / 12)
    month_cos = math.cos(2 * math.pi * month / 12)
    return [tenure_days, 0, prix, prix_m2, surface,
            row.nombre_pieces or 0, is_maison, is_appart, month_sin, month_cos]

def _score_to_priority(prob: float) -> str:
    if prob >= 0.70: return "URGENT"
    elif prob >= 0.50: return "HIGH"
    elif prob >= 0.30: return "MEDIUM"
    elif prob >= 0.15: return "LOW"
    return "NONE"

def _priority_label(prob: float) -> str:
    if prob >= 0.70: return "Très forte probabilité de revente"
    elif prob >= 0.50: return "Forte probabilité de revente"
    elif prob >= 0.30: return "Probabilité modérée de revente"
    elif prob >= 0.15: return "Faible probabilité de revente"
    return "Pas de signal de vente"

# ── Endpoint principal ────────────────────────────────────────────────────────
@router.get("/analyze/{code_postal}")
async def analyze_by_cp(
    code_postal: str,
    type_local: Optional[str] = Query(None, description="Maison | Appartement | ..."),
    surface_min: Optional[float] = Query(None),
    surface_max: Optional[float] = Query(None),
    priorite: Optional[str] = Query(None, description="URGENT | HIGH | MEDIUM | LOW"),
    min_p6: float = Query(0.0, ge=0.0, le=1.0, description="Probabilité P6 minimale [0-1]"),
    limit: int = Query(300, le=500),
):
    from database import SessionLocal
    db = SessionLocal()
    try:
        conditions = ["code_postal = :cp"]
        params: dict = {"cp": code_postal, "limit": limit * 4}

        if type_local:
            conditions.append("type_local = :type_local")
            params["type_local"] = type_local
        if surface_min is not None:
            conditions.append("surface_reelle >= :surface_min")
            params["surface_min"] = surface_min
        if surface_max is not None:
            conditions.append("surface_reelle <= :surface_max")
            params["surface_max"] = surface_max

        where_clause = " AND ".join(conditions)
        sql = text(f"""
            SELECT id, adresse, code_postal, commune, type_local,
                   surface_reelle, nombre_pieces, valeur_fonciere,
                   date_mutation, duree_detention_estimee,
                   propensity_score, propensity_raisons,
                   classe_dpe, latitude, longitude, derniere_analyse_propension
            FROM transactions_dvf
            WHERE {where_clause}
            ORDER BY date_mutation DESC
            LIMIT :limit
        """)

        rows = db.execute(sql, params).fetchall()

        model = _load_model()
        if model is not None and len(rows) > 0:
            X = np.array([_build_features(r) for r in rows], dtype=float)
            try:
                probs = model.predict_proba(X)[:, 1]
            except AttributeError:
                probs = model.predict(X)
            model_used = "lightgbm"
        else:
            probs = [(r.propensity_score or 0) / 100.0 for r in rows]
            model_used = "rule-based"

        biens = []
        for row, prob in zip(rows, probs):
            prob = float(prob)
            if prob < min_p6:
                continue
            priority = _score_to_priority(prob)
            if priorite and priority != priorite.upper():
                continue

            prix = row.valeur_fonciere
            surface = row.surface_reelle
            prix_m2 = round(prix / surface, 0) if prix and surface and surface > 0 else None

            biens.append({
                "id": row.id,
                "adresse": row.adresse,
                "code_postal": row.code_postal,
                "commune": row.commune,
                "type_local": row.type_local,
                "surface": surface,
                "pieces": row.nombre_pieces,
                "prix": prix,
                "prix_m2": prix_m2,
                "date_mutation": str(row.date_mutation) if row.date_mutation else None,
                "duree_detention": row.duree_detention_estimee,
                "propensity_score": round(prob * 100),
                "prob_sell_6m": round(prob, 4),
                "contact_priority": priority,
                "propensity_timeframe": _priority_label(prob),
                "propensity_raisons": row.propensity_raisons or [],
                "classe_dpe": row.classe_dpe,
                "latitude": row.latitude,
                "longitude": row.longitude,
                "derniere_analyse": str(row.derniere_analyse_propension) if row.derniere_analyse_propension else None,
            })

        biens.sort(key=lambda b: b["prob_sell_6m"], reverse=True)
        biens = biens[:limit]

        stats = {
            "urgent": sum(1 for b in biens if b["contact_priority"] == "URGENT"),
            "high":   sum(1 for b in biens if b["contact_priority"] == "HIGH"),
            "medium": sum(1 for b in biens if b["contact_priority"] == "MEDIUM"),
            "low":    sum(1 for b in biens if b["contact_priority"] == "LOW"),
            "avec_coords": sum(1 for b in biens if b["latitude"] and b["longitude"]),
            "scoring_ok":  sum(1 for b in biens if b["propensity_score"] > 0),
        }

        logger.info(f"✅ [{model_used}] CP={code_postal} → {len(biens)} biens (URGENT={stats['urgent']}, HIGH={stats['high']})")
        return {"code_postal": code_postal, "total": len(biens), "stats": stats, "biens": biens, "model": model_used}

    except Exception as e:
        logger.error(f"❌ Erreur analyze CP={code_postal}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.post("/recompute-model")
async def recompute_model(
    score_min: int = Query(0),
    limit: int = Query(5000),
):
    from database import SessionLocal
    from services.propensity_predictor import PropensityToSellPredictor
    db = SessionLocal()
    try:
        logger.info(f"🔄 Recompute P6 lancé (score_min={score_min}, limit={limit})")
        predictor = PropensityToSellPredictor(db)
        result = predictor.analyze_batch(score_min=score_min, limit=limit)
        return {"success": True, "message": f"Recalcul terminé : {result.get('analyzed', 0)} biens analysés", **result}
    except Exception as e:
        logger.error(f"❌ Erreur recompute: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.get("/health")
async def health():
    model = _load_model()
    return {"status": "ok", "service": "prospectscore-pro", "model": "lightgbm" if model else "unavailable"}

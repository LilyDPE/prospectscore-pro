"""
Route : /api/analyze/{code_postal}
- LightGBM AUC=0.88 + repeat_sale_flag correct
- Priorité relative au CP
- market_context : dynamisme du secteur
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

_MODEL = None
_MODEL_PATH = Path("/app/models/lgb_model.pkl")

def _load_model():
    global _MODEL
    if _MODEL is None:
        try:
            with open(_MODEL_PATH, "rb") as f:
                _MODEL = pickle.load(f)
            logger.info("✅ Modèle LightGBM chargé")
        except Exception as e:
            logger.error(f"❌ lgb_model.pkl : {e}")
    return _MODEL

def _build_features(row) -> list:
    tenure_days = (row.duree_detention_estimee or 0) * 365.25
    prix = row.valeur_fonciere or 0
    surface = row.surface_reelle or 1
    prix_m2 = prix / surface if surface > 0 else 0
    is_maison = 1 if row.type_local == "Maison" else 0
    is_appart = 1 if row.type_local == "Appartement" else 0
    repeat = int(row.repeat_sale_flag) if hasattr(row, 'repeat_sale_flag') and row.repeat_sale_flag else 0
    try:
        month = row.date_mutation.month if row.date_mutation and not isinstance(row.date_mutation, str) \
                else (datetime.fromisoformat(str(row.date_mutation)).month if row.date_mutation else 6)
    except Exception:
        month = 6
    return [
        tenure_days, repeat, prix, prix_m2, surface,
        row.nombre_pieces or 0, is_maison, is_appart,
        math.sin(2 * math.pi * month / 12),
        math.cos(2 * math.pi * month / 12),
    ]

def _assign_relative_priorities(biens: list) -> list:
    n = len(biens)
    if n == 0:
        return biens
    for i, bien in enumerate(biens):
        pct = i / n
        if n < 3:
            p = bien["prob_sell_6m"]
            if p >= 0.30:   priority, label = "URGENT", "Très forte probabilité de revente"
            elif p >= 0.15: priority, label = "HIGH",   "Forte probabilité de revente"
            elif p >= 0.08: priority, label = "MEDIUM", "Probabilité modérée"
            else:           priority, label = "LOW",    "Faible probabilité de revente"
        elif pct < 0.15:
            priority = "URGENT"
            label = f"Top 15% du secteur · score {round(bien['prob_sell_6m']*100)}%"
        elif pct < 0.35:
            priority = "HIGH"
            label = f"Top 35% du secteur · score {round(bien['prob_sell_6m']*100)}%"
        elif pct < 0.65:
            priority = "MEDIUM"
            label = f"Médiane du secteur · score {round(bien['prob_sell_6m']*100)}%"
        elif pct < 0.90:
            priority = "LOW"
            label = f"Bas du classement · score {round(bien['prob_sell_6m']*100)}%"
        else:
            priority = "NONE"
            label = "Pas de signal de vente"
        bien["contact_priority"] = priority
        bien["propensity_timeframe"] = label
        bien["rang_cp"] = f"{i + 1}/{n}"
    return biens

def _market_heat_label(tx_12m: int, duree_moy: float) -> dict:
    """Calcule le dynamisme du marché local."""
    if tx_12m >= 80:
        heat, emoji = "Très actif", "🔥🔥"
    elif tx_12m >= 40:
        heat, emoji = "Actif", "🔥"
    elif tx_12m >= 15:
        heat, emoji = "Modéré", "〰️"
    elif tx_12m >= 5:
        heat, emoji = "Calme", "❄️"
    else:
        heat, emoji = "Très calme", "❄️❄️"

    if duree_moy and duree_moy <= 3:
        rotation = "Rotation rapide (< 3 ans)"
    elif duree_moy and duree_moy <= 7:
        rotation = "Rotation normale (3-7 ans)"
    elif duree_moy:
        rotation = f"Rotation lente ({round(duree_moy, 1)} ans en moy.)"
    else:
        rotation = "Rotation inconnue"

    return {"chaleur": heat, "emoji": emoji, "rotation": rotation}

@router.get("/analyze/{code_postal}")
async def analyze_by_cp(
    code_postal: str,
    type_local: Optional[str] = Query(None),
    surface_min: Optional[float] = Query(None),
    surface_max: Optional[float] = Query(None),
    priorite: Optional[str] = Query(None),
    min_p6: float = Query(0.0, ge=0.0, le=1.0),
    limit: int = Query(300, le=500),
):
    from database import SessionLocal
    db = SessionLocal()
    try:
        # ── Contexte marché du CP ─────────────────────────────────────────────
        market_sql = text("""
            SELECT
                COUNT(*) as transactions_total,
                COUNT(CASE WHEN date_mutation >= NOW() - INTERVAL '12 months' THEN 1 END) as transactions_12m,
                COUNT(CASE WHEN date_mutation >= NOW() - INTERVAL '36 months' THEN 1 END) as transactions_36m,
                ROUND(AVG(duree_detention_estimee)::numeric, 1) as duree_moy_ans,
                ROUND(MIN(duree_detention_estimee)::numeric, 1) as duree_min_ans,
                ROUND(MAX(duree_detention_estimee)::numeric, 1) as duree_max_ans,
                COUNT(CASE WHEN adresse IN (
                    SELECT adresse FROM transactions_dvf t2
                    WHERE t2.code_postal = :cp GROUP BY adresse HAVING COUNT(*) > 1
                ) THEN 1 END) as biens_revendus
            FROM transactions_dvf
            WHERE code_postal = :cp
        """)
        mkt = db.execute(market_sql, {"cp": code_postal}).fetchone()

        tx_12m = int(mkt.transactions_12m or 0)
        tx_36m = int(mkt.transactions_36m or 0)
        duree_moy = float(mkt.duree_moy_ans) if mkt.duree_moy_ans else None
        heat_info = _market_heat_label(tx_12m, duree_moy)

        market_context = {
            "transactions_total": int(mkt.transactions_total or 0),
            "transactions_12m": tx_12m,
            "transactions_36m": tx_36m,
            "duree_moy_detention_ans": duree_moy,
            "duree_min_ans": float(mkt.duree_min_ans) if mkt.duree_min_ans else None,
            "duree_max_ans": float(mkt.duree_max_ans) if mkt.duree_max_ans else None,
            "biens_revendus_plusieurs_fois": int(mkt.biens_revendus or 0),
            "chaleur_marche": heat_info["chaleur"],
            "chaleur_emoji": heat_info["emoji"],
            "rotation": heat_info["rotation"],
            "alerte": tx_12m < 5,
            "alerte_message": "⚠️ Marché très peu actif — peu de données disponibles" if tx_12m < 5 else None,
        }

        # ── Biens avec repeat_sale_flag calculé ───────────────────────────────
        conditions = ["t.code_postal = :cp"]
        params: dict = {"cp": code_postal}

        if type_local:
            conditions.append("t.type_local = :type_local")
            params["type_local"] = type_local
        if surface_min is not None:
            conditions.append("t.surface_reelle >= :surface_min")
            params["surface_min"] = surface_min
        if surface_max is not None:
            conditions.append("t.surface_reelle <= :surface_max")
            params["surface_max"] = surface_max

        sql = text(f"""
            SELECT * FROM (
                SELECT DISTINCT ON (t.adresse, t.code_postal)
                    t.id, t.adresse, t.code_postal, t.commune, t.type_local,
                    t.surface_reelle, t.nombre_pieces, t.valeur_fonciere,
                    t.date_mutation, t.duree_detention_estimee,
                    t.propensity_score, t.propensity_raisons,
                    t.classe_dpe, t.latitude, t.longitude,
                    t.derniere_analyse_propension,
                    CASE WHEN nb_ventes.nb > 1 THEN 1 ELSE 0 END AS repeat_sale_flag,
                    nb_ventes.nb AS nb_ventes_adresse
                FROM transactions_dvf t
                LEFT JOIN (
                    SELECT adresse, code_postal, COUNT(*) as nb
                    FROM transactions_dvf
                    WHERE code_postal = :cp
                    GROUP BY adresse, code_postal
                ) nb_ventes ON nb_ventes.adresse = t.adresse
                    AND nb_ventes.code_postal = t.code_postal
                WHERE {" AND ".join(conditions)}
                ORDER BY t.adresse, t.code_postal, t.date_mutation DESC
            ) sub
            ORDER BY sub.duree_detention_estimee DESC NULLS LAST
            LIMIT 1000
        """)

        rows = db.execute(sql, params).fetchall()

        # ── Scoring LightGBM ──────────────────────────────────────────────────
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

        # ── Construction biens ────────────────────────────────────────────────
        biens = []
        for row, prob in zip(rows, probs):
            prob = float(prob)
            if prob < min_p6:
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
                "repeat_sale": bool(row.repeat_sale_flag),
                "nb_ventes_adresse": int(row.nb_ventes_adresse) if row.nb_ventes_adresse else 1,
                "propensity_score": round(prob * 100),
                "prob_sell_6m": round(prob, 4),
                "contact_priority": "NONE",
                "propensity_timeframe": "",
                "rang_cp": "",
                "propensity_raisons": row.propensity_raisons or [],
                "classe_dpe": row.classe_dpe,
                "latitude": row.latitude,
                "longitude": row.longitude,
                "derniere_analyse": str(row.derniere_analyse_propension) if row.derniere_analyse_propension else None,
            })

        biens.sort(key=lambda b: b["prob_sell_6m"], reverse=True)
        biens = _assign_relative_priorities(biens)

        if priorite:
            biens = [b for b in biens if b["contact_priority"] == priorite.upper()]

        biens = biens[:limit]

        stats = {
            "urgent": sum(1 for b in biens if b["contact_priority"] == "URGENT"),
            "high":   sum(1 for b in biens if b["contact_priority"] == "HIGH"),
            "medium": sum(1 for b in biens if b["contact_priority"] == "MEDIUM"),
            "low":    sum(1 for b in biens if b["contact_priority"] == "LOW"),
            "avec_coords": sum(1 for b in biens if b["latitude"] and b["longitude"]),
            "repeat_sales": sum(1 for b in biens if b["repeat_sale"]),
            "scoring_ok": sum(1 for b in biens if b["propensity_score"] > 0),
        }

        logger.info(f"✅ [{model_used}] CP={code_postal} → {len(biens)} biens "
                    f"(URGENT={stats['urgent']}, marché={heat_info['chaleur']})")

        return {
            "code_postal": code_postal,
            "total": len(biens),
            "stats": stats,
            "market_context": market_context,
            "biens": biens,
            "model": model_used,
            "scoring": "relatif-au-cp + repeat_sale_flag",
        }

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
        predictor = PropensityToSellPredictor(db)
        result = predictor.analyze_batch(score_min=score_min, limit=limit)
        return {"success": True, "message": f"Recalcul : {result.get('analyzed', 0)} biens", **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.get("/health")
async def health():
    model = _load_model()
    return {"status": "ok", "service": "prospectscore-pro",
            "model": "lightgbm" if model else "unavailable",
            "scoring": "relatif-au-cp + repeat_sale_flag"}

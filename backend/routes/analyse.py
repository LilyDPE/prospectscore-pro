"""
Route : /api/analyze/{code_postal}
Retourne les biens d'un CP triés par probabilité de revente P6 (prob_sell_6m).

GET  /api/analyze/{code_postal}  → liste scorée
POST /api/recompute-model        → recalcul à la demande (admin)
GET  /api/health                 → healthcheck
"""

import logging
from typing import Optional

from fastapi import APIRouter, Query, HTTPException
from sqlalchemy import text

router = APIRouter(prefix="/api", tags=["analyze"])
logger = logging.getLogger(__name__)


@router.get("/analyze/{code_postal}")
async def analyze_by_cp(
    code_postal: str,
    type_local: Optional[str] = Query(None, description="Maison | Appartement | Local industriel..."),
    surface_min: Optional[float] = Query(None, description="Surface minimum en m²"),
    surface_max: Optional[float] = Query(None, description="Surface maximum en m²"),
    priorite: Optional[str] = Query(None, description="URGENT | HIGH | MEDIUM | LOW"),
    min_p6: float = Query(0.0, ge=0.0, le=1.0, description="Probabilité P6 minimale [0-1]"),
    limit: int = Query(300, le=500, description="Nombre max de résultats"),
):
    """
    Retourne les biens d'un code postal classés par probabilité de revente dans les 6 mois.

    prob_sell_6m = propensity_score / 100  (normalisé [0,1])

    Filtres disponibles : type_local, surface_min, surface_max, priorite, min_p6.
    """
    from database import SessionLocal

    db = SessionLocal()
    try:
        # Construction dynamique de la clause WHERE
        conditions = ["code_postal = :cp"]
        params: dict = {
            "cp": code_postal,
            "min_p6_int": int(min_p6 * 100),
            "limit": limit,
        }

        conditions.append("propensity_score >= :min_p6_int")

        if type_local:
            conditions.append("type_local = :type_local")
            params["type_local"] = type_local

        if surface_min is not None:
            conditions.append("surface_reelle >= :surface_min")
            params["surface_min"] = surface_min

        if surface_max is not None:
            conditions.append("surface_reelle <= :surface_max")
            params["surface_max"] = surface_max

        if priorite:
            conditions.append("contact_priority = :priorite")
            params["priorite"] = priorite.upper()

        where_clause = " AND ".join(conditions)

        sql = text(f"""
            SELECT
                id,
                adresse,
                code_postal,
                commune,
                type_local,
                surface_reelle,
                nombre_pieces,
                valeur_fonciere,
                date_mutation,
                duree_detention_estimee,
                propensity_score,
                ROUND(propensity_score::numeric / 100, 2) AS prob_sell_6m,
                contact_priority,
                propensity_timeframe,
                propensity_raisons,
                classe_dpe,
                latitude,
                longitude,
                derniere_analyse_propension
            FROM transactions_dvf
            WHERE {where_clause}
            ORDER BY propensity_score DESC, date_mutation DESC
            LIMIT :limit
        """)

        result = db.execute(sql, params)
        rows = result.fetchall()

        biens = []
        for row in rows:
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
                "propensity_score": row.propensity_score,
                "prob_sell_6m": float(row.prob_sell_6m) if row.prob_sell_6m is not None else 0.0,
                "contact_priority": row.contact_priority or "NONE",
                "propensity_timeframe": row.propensity_timeframe,
                "propensity_raisons": row.propensity_raisons or [],
                "classe_dpe": row.classe_dpe,
                "latitude": row.latitude,
                "longitude": row.longitude,
                "derniere_analyse": str(row.derniere_analyse_propension) if row.derniere_analyse_propension else None,
            })

        # Stats rapides
        stats = {
            "urgent": sum(1 for b in biens if b["contact_priority"] == "URGENT"),
            "high": sum(1 for b in biens if b["contact_priority"] == "HIGH"),
            "medium": sum(1 for b in biens if b["contact_priority"] == "MEDIUM"),
            "low": sum(1 for b in biens if b["contact_priority"] == "LOW"),
            "avec_coords": sum(1 for b in biens if b["latitude"] and b["longitude"]),
            "scoring_ok": sum(1 for b in biens if b["propensity_score"] and b["propensity_score"] > 0),
        }

        logger.info(f"✅ Analyze CP={code_postal} → {len(biens)} biens (URGENT={stats['urgent']}, HIGH={stats['high']})")

        return {
            "code_postal": code_postal,
            "total": len(biens),
            "stats": stats,
            "biens": biens,
        }

    except Exception as e:
        logger.error(f"❌ Erreur analyze CP={code_postal}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.post("/recompute-model")
async def recompute_model(
    score_min: int = Query(0, description="Score DPE minimum pour inclure dans le batch"),
    limit: int = Query(5000, description="Nombre max de biens à recalculer"),
):
    """
    Recalcul à la demande du modèle P6 (propensity score).
    Utilise le PropensityToSellPredictor existant.
    Réservé aux admins — protéger via middleware auth si besoin.
    """
    from database import SessionLocal
    from services.propensity_predictor import PropensityToSellPredictor

    db = SessionLocal()
    try:
        logger.info(f"🔄 Recompute P6 lancé à la demande (score_min={score_min}, limit={limit})")
        predictor = PropensityToSellPredictor(db)
        result = predictor.analyze_batch(score_min=score_min, limit=limit)
        logger.info(f"✅ Recompute terminé : {result}")
        return {
            "success": True,
            "message": f"Recalcul terminé : {result.get('analyzed', 0)} biens analysés",
            **result,
        }
    except Exception as e:
        logger.error(f"❌ Erreur recompute P6: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.get("/health")
async def health():
    """Healthcheck endpoint."""
    return {"status": "ok", "service": "prospectscore-pro"}

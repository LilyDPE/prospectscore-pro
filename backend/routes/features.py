"""
Routes pour les features ML et le scoring de propension
Endpoints pour accéder aux features contextuelles calculées sur les biens
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from sqlalchemy import desc, asc, func
from database import SessionLocal
from models.bien_univers import BienUnivers

router = APIRouter(prefix="/api/features", tags=["features"])

# ==================== SCHEMAS ====================

class BienFeaturesResponse(BaseModel):
    """Réponse pour les features d'un bien"""
    id_bien: int
    adresse: str
    code_postal: str
    commune: str
    type_local: str
    surface_reelle: Optional[float]
    nombre_pieces: Optional[int]
    last_price: Optional[float]

    features: Dict[str, Any]
    propensity: Dict[str, Any]
    metadata: Dict[str, Any]

class StatsResponse(BaseModel):
    """Statistiques sur les features calculées"""
    total_biens: int
    biens_avec_features: int
    pourcentage_features: float

    repartition_zone_type: Dict[str, int]
    repartition_propensity: Dict[str, int]

    stats_turnover: Dict[str, Any]
    stats_density: Dict[str, Any]

# ==================== ENDPOINTS ====================

@router.get("/", response_model=Dict[str, Any])
async def features_info():
    """
    Informations sur l'API Features
    """
    return {
        "name": "ProspectScore Pro - Features ML API",
        "version": "1.0.0",
        "description": "API pour accéder aux features contextuelles ML calculées sur les biens immobiliers",
        "features_disponibles": [
            "zone_type: Classification RURAL_ISOLE / RURAL / PERIURBAIN / URBAIN",
            "local_turnover_12m: Nombre de ventes dans 500m sur 12 mois",
            "sale_density_12m: Densité de ventes corrigée (0-0.935)",
            "avg_local_price: Prix moyen dans la zone",
            "local_price_evolution: Évolution des prix sur 12 mois",
            "propensity_score: Score de propension à vendre (0-100)"
        ],
        "endpoints": {
            "GET /api/features/{id_bien}": "Récupérer les features d'un bien spécifique",
            "GET /api/features/search": "Rechercher des biens par features",
            "GET /api/features/stats": "Statistiques sur les features calculées",
            "GET /api/features/by-zone/{zone_type}": "Biens par zone type",
            "GET /api/features/by-postal-code/{code_postal}": "Biens par code postal"
        }
    }

@router.get("/{id_bien}", response_model=BienFeaturesResponse)
async def get_bien_features(id_bien: int):
    """
    Récupérer les features ML d'un bien spécifique

    Args:
        id_bien: Identifiant unique du bien

    Returns:
        Features ML calculées pour ce bien
    """
    db = SessionLocal()
    try:
        bien = db.query(BienUnivers).filter(BienUnivers.id_bien == id_bien).first()

        if not bien:
            raise HTTPException(status_code=404, detail=f"Bien {id_bien} non trouvé")

        if not bien.features_calculated:
            raise HTTPException(
                status_code=404,
                detail=f"Features non calculées pour le bien {id_bien}"
            )

        return bien.to_dict()

    finally:
        db.close()

@router.get("/search", response_model=List[BienFeaturesResponse])
async def search_biens_by_features(
    zone_type: Optional[str] = Query(None, description="RURAL_ISOLE, RURAL, PERIURBAIN, URBAIN"),
    code_postal: Optional[str] = Query(None, description="Code postal (5 chiffres)"),
    type_local: Optional[str] = Query(None, description="Maison, Appartement, etc."),
    min_turnover: Optional[int] = Query(None, description="Turnover local minimum (12m)"),
    max_turnover: Optional[int] = Query(None, description="Turnover local maximum (12m)"),
    min_density: Optional[float] = Query(None, description="Densité minimum (0-1)"),
    max_density: Optional[float] = Query(None, description="Densité maximum (0-1)"),
    min_propensity: Optional[int] = Query(None, description="Score propension minimum (0-100)"),
    max_propensity: Optional[int] = Query(None, description="Score propension maximum (0-100)"),
    sort_by: str = Query("propensity_score", description="Champ de tri"),
    sort_order: str = Query("desc", description="Ordre de tri (asc/desc)"),
    limit: int = Query(50, description="Nombre max de résultats", le=1000),
    offset: int = Query(0, description="Offset pour pagination")
):
    """
    Rechercher des biens en filtrant par features ML

    Permet de filtrer par:
    - Zone type (rural, urbain, etc.)
    - Code postal
    - Type de local
    - Turnover local (activité du marché)
    - Densité de ventes
    - Score de propension
    """
    db = SessionLocal()
    try:
        # Query de base : uniquement les biens avec features calculées
        query = db.query(BienUnivers).filter(BienUnivers.features_calculated == True)

        # Filtres
        if zone_type:
            query = query.filter(BienUnivers.zone_type == zone_type.upper())

        if code_postal:
            # Support recherche partielle (ex: "76" pour tous les codes 76xxx)
            if len(code_postal) < 5:
                query = query.filter(BienUnivers.code_postal.like(f"{code_postal}%"))
            else:
                query = query.filter(BienUnivers.code_postal == code_postal)

        if type_local:
            query = query.filter(BienUnivers.type_local == type_local)

        if min_turnover is not None:
            query = query.filter(BienUnivers.local_turnover_12m >= min_turnover)

        if max_turnover is not None:
            query = query.filter(BienUnivers.local_turnover_12m <= max_turnover)

        if min_density is not None:
            query = query.filter(BienUnivers.sale_density_12m >= min_density)

        if max_density is not None:
            query = query.filter(BienUnivers.sale_density_12m <= max_density)

        if min_propensity is not None:
            query = query.filter(BienUnivers.propensity_score >= min_propensity)

        if max_propensity is not None:
            query = query.filter(BienUnivers.propensity_score <= max_propensity)

        # Tri
        sort_column = getattr(BienUnivers, sort_by, BienUnivers.propensity_score)
        if sort_order == "asc":
            query = query.order_by(asc(sort_column))
        else:
            query = query.order_by(desc(sort_column))

        # Pagination
        total = query.count()
        biens = query.offset(offset).limit(limit).all()

        return [bien.to_dict() for bien in biens]

    finally:
        db.close()

@router.get("/by-zone/{zone_type}", response_model=List[BienFeaturesResponse])
async def get_biens_by_zone_type(
    zone_type: str,
    limit: int = Query(100, description="Nombre max de résultats", le=1000),
    offset: int = Query(0, description="Offset pour pagination")
):
    """
    Récupérer tous les biens d'une zone type spécifique

    Args:
        zone_type: RURAL_ISOLE, RURAL, PERIURBAIN, ou URBAIN
        limit: Nombre maximum de résultats
        offset: Offset pour pagination
    """
    db = SessionLocal()
    try:
        zone_type_upper = zone_type.upper()

        # Validation du zone_type
        valid_zones = ["RURAL_ISOLE", "RURAL", "PERIURBAIN", "URBAIN"]
        if zone_type_upper not in valid_zones:
            raise HTTPException(
                status_code=400,
                detail=f"Zone type invalide. Valeurs acceptées: {', '.join(valid_zones)}"
            )

        biens = db.query(BienUnivers).filter(
            BienUnivers.zone_type == zone_type_upper,
            BienUnivers.features_calculated == True
        ).order_by(desc(BienUnivers.propensity_score)).offset(offset).limit(limit).all()

        return [bien.to_dict() for bien in biens]

    finally:
        db.close()

@router.get("/by-postal-code/{code_postal}", response_model=List[BienFeaturesResponse])
async def get_biens_by_postal_code(
    code_postal: str,
    limit: int = Query(100, description="Nombre max de résultats", le=1000),
    offset: int = Query(0, description="Offset pour pagination")
):
    """
    Récupérer tous les biens d'un code postal

    Args:
        code_postal: Code postal (5 chiffres) ou préfixe (ex: "76" pour Seine-Maritime)
        limit: Nombre maximum de résultats
        offset: Offset pour pagination
    """
    db = SessionLocal()
    try:
        # Support recherche partielle
        if len(code_postal) < 5:
            biens = db.query(BienUnivers).filter(
                BienUnivers.code_postal.like(f"{code_postal}%"),
                BienUnivers.features_calculated == True
            ).order_by(desc(BienUnivers.propensity_score)).offset(offset).limit(limit).all()
        else:
            biens = db.query(BienUnivers).filter(
                BienUnivers.code_postal == code_postal,
                BienUnivers.features_calculated == True
            ).order_by(desc(BienUnivers.propensity_score)).offset(offset).limit(limit).all()

        if not biens:
            raise HTTPException(
                status_code=404,
                detail=f"Aucun bien trouvé pour le code postal {code_postal}"
            )

        return [bien.to_dict() for bien in biens]

    finally:
        db.close()

@router.get("/stats", response_model=StatsResponse)
async def get_features_stats():
    """
    Statistiques sur les features ML calculées

    Returns:
        - Nombre total de biens
        - Nombre de biens avec features calculées
        - Répartition par zone type
        - Répartition par catégorie de propension
        - Statistiques sur turnover et densité
    """
    db = SessionLocal()
    try:
        # Total
        total_biens = db.query(func.count(BienUnivers.id_bien)).scalar()
        biens_avec_features = db.query(func.count(BienUnivers.id_bien)).filter(
            BienUnivers.features_calculated == True
        ).scalar()

        pourcentage = round((biens_avec_features / total_biens * 100), 2) if total_biens > 0 else 0

        # Répartition par zone type
        zone_repartition = db.query(
            BienUnivers.zone_type,
            func.count(BienUnivers.id_bien).label('count')
        ).filter(
            BienUnivers.features_calculated == True
        ).group_by(BienUnivers.zone_type).all()

        repartition_zone = {zone: count for zone, count in zone_repartition if zone}

        # Répartition par propensity
        propensity_repartition = db.query(
            BienUnivers.propensity_category,
            func.count(BienUnivers.id_bien).label('count')
        ).filter(
            BienUnivers.features_calculated == True
        ).group_by(BienUnivers.propensity_category).all()

        repartition_propensity = {cat: count for cat, count in propensity_repartition if cat}

        # Stats turnover
        turnover_stats = db.query(
            func.avg(BienUnivers.local_turnover_12m).label('avg'),
            func.min(BienUnivers.local_turnover_12m).label('min'),
            func.max(BienUnivers.local_turnover_12m).label('max')
        ).filter(BienUnivers.features_calculated == True).first()

        # Stats density
        density_stats = db.query(
            func.avg(BienUnivers.sale_density_12m).label('avg'),
            func.min(BienUnivers.sale_density_12m).label('min'),
            func.max(BienUnivers.sale_density_12m).label('max')
        ).filter(BienUnivers.features_calculated == True).first()

        return {
            "total_biens": total_biens,
            "biens_avec_features": biens_avec_features,
            "pourcentage_features": pourcentage,
            "repartition_zone_type": repartition_zone,
            "repartition_propensity": repartition_propensity,
            "stats_turnover": {
                "avg": round(turnover_stats.avg, 2) if turnover_stats.avg else 0,
                "min": turnover_stats.min or 0,
                "max": turnover_stats.max or 0
            },
            "stats_density": {
                "avg": round(density_stats.avg, 4) if density_stats.avg else 0,
                "min": round(density_stats.min, 4) if density_stats.min else 0,
                "max": round(density_stats.max, 4) if density_stats.max else 0
            }
        }

    finally:
        db.close()

@router.get("/top-propensity", response_model=List[BienFeaturesResponse])
async def get_top_propensity_biens(
    zone_type: Optional[str] = Query(None, description="Filtrer par zone type"),
    code_postal: Optional[str] = Query(None, description="Filtrer par code postal"),
    limit: int = Query(100, description="Nombre max de résultats", le=500)
):
    """
    Récupérer les biens avec les scores de propension les plus élevés

    Utile pour identifier les meilleures opportunités de prospection
    """
    db = SessionLocal()
    try:
        query = db.query(BienUnivers).filter(
            BienUnivers.features_calculated == True,
            BienUnivers.propensity_score > 0
        )

        if zone_type:
            query = query.filter(BienUnivers.zone_type == zone_type.upper())

        if code_postal:
            if len(code_postal) < 5:
                query = query.filter(BienUnivers.code_postal.like(f"{code_postal}%"))
            else:
                query = query.filter(BienUnivers.code_postal == code_postal)

        biens = query.order_by(desc(BienUnivers.propensity_score)).limit(limit).all()

        return [bien.to_dict() for bien in biens]

    finally:
        db.close()

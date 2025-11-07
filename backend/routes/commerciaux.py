"""
Routes pour la gestion des commerciaux et assignation de prospects
Accessible uniquement aux administrateurs
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr
from sqlalchemy import desc, asc, func, and_, or_
from datetime import datetime, timedelta
from database import SessionLocal
from models.commercial import Commercial, ProspectAssignment
from models.bien_univers import BienUnivers

router = APIRouter(prefix="/api/admin/commerciaux", tags=["commerciaux"])

# ==================== SCHEMAS ====================

class CommercialCreate(BaseModel):
    nom: str
    prenom: str
    email: EmailStr
    telephone: Optional[str] = None
    codes_postaux_assignes: List[str] = []
    departements_assignes: List[str] = []
    communes_assignees: List[str] = []
    capacite_max_prospects: int = 100
    min_propensity_score: int = 60
    notes: Optional[str] = None

class CommercialUpdate(BaseModel):
    nom: Optional[str] = None
    prenom: Optional[str] = None
    email: Optional[EmailStr] = None
    telephone: Optional[str] = None
    codes_postaux_assignes: Optional[List[str]] = None
    departements_assignes: Optional[List[str]] = None
    communes_assignees: Optional[List[str]] = None
    capacite_max_prospects: Optional[int] = None
    min_propensity_score: Optional[int] = None
    actif: Optional[bool] = None
    notes: Optional[str] = None

class AssignmentUpdate(BaseModel):
    statut: Optional[str] = None
    priorite: Optional[str] = None
    notes_commercial: Optional[str] = None
    date_rdv: Optional[datetime] = None
    date_mandat: Optional[datetime] = None
    valeur_mandat: Optional[float] = None
    raison_perte: Optional[str] = None

class AssignProspectsRequest(BaseModel):
    commercial_id: int
    nombre_prospects: int = 10
    force_reassign: bool = False  # Réassigner même si déjà assigné à un autre

# ==================== ENDPOINTS COMMERCIAUX ====================

@router.get("/", response_model=List[Dict[str, Any]])
async def list_commerciaux(
    actif_seulement: bool = Query(True, description="Filtrer uniquement les commerciaux actifs"),
    tri_par: str = Query("nom", description="Champ de tri"),
    limit: int = Query(100, le=500)
):
    """
    Lister tous les commerciaux
    """
    db = SessionLocal()
    try:
        query = db.query(Commercial)

        if actif_seulement:
            query = query.filter(Commercial.actif == True)

        # Tri
        if hasattr(Commercial, tri_par):
            query = query.order_by(getattr(Commercial, tri_par))

        commerciaux = query.limit(limit).all()

        return [c.to_dict() for c in commerciaux]

    finally:
        db.close()

@router.post("/", response_model=Dict[str, Any])
async def create_commercial(commercial: CommercialCreate):
    """
    Créer un nouveau commercial

    Args:
        commercial: Données du commercial à créer

    Returns:
        Commercial créé avec son ID
    """
    db = SessionLocal()
    try:
        # Vérifier si l'email existe déjà
        existing = db.query(Commercial).filter(Commercial.email == commercial.email).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"Un commercial avec l'email {commercial.email} existe déjà")

        # Créer le commercial
        new_commercial = Commercial(
            nom=commercial.nom,
            prenom=commercial.prenom,
            email=commercial.email,
            telephone=commercial.telephone,
            codes_postaux_assignes=commercial.codes_postaux_assignes,
            departements_assignes=commercial.departements_assignes,
            communes_assignees=commercial.communes_assignees,
            capacite_max_prospects=commercial.capacite_max_prospects,
            min_propensity_score=commercial.min_propensity_score,
            notes=commercial.notes,
            actif=True
        )

        db.add(new_commercial)
        db.commit()
        db.refresh(new_commercial)

        return {
            "message": f"Commercial {new_commercial.prenom} {new_commercial.nom} créé avec succès",
            "commercial": new_commercial.to_dict()
        }

    finally:
        db.close()

@router.get("/{commercial_id}", response_model=Dict[str, Any])
async def get_commercial(commercial_id: int):
    """
    Récupérer les détails d'un commercial
    """
    db = SessionLocal()
    try:
        commercial = db.query(Commercial).filter(Commercial.id == commercial_id).first()

        if not commercial:
            raise HTTPException(status_code=404, detail=f"Commercial {commercial_id} non trouvé")

        return commercial.to_dict()

    finally:
        db.close()

@router.put("/{commercial_id}", response_model=Dict[str, Any])
async def update_commercial(commercial_id: int, update: CommercialUpdate):
    """
    Mettre à jour un commercial
    """
    db = SessionLocal()
    try:
        commercial = db.query(Commercial).filter(Commercial.id == commercial_id).first()

        if not commercial:
            raise HTTPException(status_code=404, detail=f"Commercial {commercial_id} non trouvé")

        # Mettre à jour les champs fournis
        update_data = update.dict(exclude_unset=True)

        for field, value in update_data.items():
            setattr(commercial, field, value)

        commercial.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(commercial)

        # Recalculer les stats si nécessaire
        update_commercial_stats(db, commercial_id)

        return {
            "message": f"Commercial {commercial.prenom} {commercial.nom} mis à jour",
            "commercial": commercial.to_dict()
        }

    finally:
        db.close()

@router.delete("/{commercial_id}")
async def delete_commercial(commercial_id: int, supprimer_definitivement: bool = False):
    """
    Supprimer ou désactiver un commercial

    Args:
        commercial_id: ID du commercial
        supprimer_definitivement: Si True, supprime définitivement. Sinon, désactive seulement.
    """
    db = SessionLocal()
    try:
        commercial = db.query(Commercial).filter(Commercial.id == commercial_id).first()

        if not commercial:
            raise HTTPException(status_code=404, detail=f"Commercial {commercial_id} non trouvé")

        if supprimer_definitivement:
            # Supprimer définitivement
            db.delete(commercial)
            message = f"Commercial {commercial.prenom} {commercial.nom} supprimé définitivement"
        else:
            # Désactiver seulement
            commercial.actif = False
            commercial.updated_at = datetime.utcnow()
            message = f"Commercial {commercial.prenom} {commercial.nom} désactivé"

        db.commit()

        return {"message": message}

    finally:
        db.close()

# ==================== ASSIGNATION DE PROSPECTS ====================

@router.post("/{commercial_id}/assign-prospects")
async def assign_prospects_to_commercial(
    commercial_id: int,
    request: Optional[AssignProspectsRequest] = None,
    nombre_prospects: int = Query(10, description="Nombre de prospects à assigner", le=100)
):
    """
    Assigner automatiquement des prospects à un commercial

    Sélectionne les meilleurs prospects (forte propension) dans les zones du commercial
    qui ne sont pas encore assignés ou dont le commercial a atteint sa capacité max.

    Args:
        commercial_id: ID du commercial
        nombre_prospects: Nombre de prospects à assigner
    """
    db = SessionLocal()
    try:
        commercial = db.query(Commercial).filter(Commercial.id == commercial_id).first()

        if not commercial:
            raise HTTPException(status_code=404, detail=f"Commercial {commercial_id} non trouvé")

        if not commercial.actif:
            raise HTTPException(status_code=400, detail=f"Commercial {commercial.prenom} {commercial.nom} est inactif")

        # Vérifier la capacité
        if commercial.nombre_prospects_assignes >= commercial.capacite_max_prospects:
            raise HTTPException(
                status_code=400,
                detail=f"Commercial {commercial.prenom} {commercial.nom} a atteint sa capacité maximale ({commercial.capacite_max_prospects})"
            )

        # Calculer combien on peut assigner
        capacite_restante = commercial.capacite_max_prospects - commercial.nombre_prospects_assignes
        nombre_a_assigner = min(nombre_prospects, capacite_restante)

        # Rechercher les biens dans les zones du commercial
        query = db.query(BienUnivers).filter(
            BienUnivers.features_calculated == True,
            BienUnivers.propensity_score >= commercial.min_propensity_score
        )

        # Filtrer par zones assignées
        zone_filters = []

        if commercial.codes_postaux_assignes:
            zone_filters.append(BienUnivers.code_postal.in_(commercial.codes_postaux_assignes))

        if commercial.departements_assignes:
            zone_filters.append(BienUnivers.departement.in_(commercial.departements_assignes))

        if zone_filters:
            query = query.filter(or_(*zone_filters))
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Aucune zone assignée au commercial {commercial.prenom} {commercial.nom}"
            )

        # Exclure les biens déjà assignés
        deja_assignes = db.query(ProspectAssignment.bien_id).filter(
            ProspectAssignment.statut.in_(["NOUVEAU", "EN_COURS", "CONTACTE", "RDV_PRIS", "INTERESSE"])
        ).subquery()

        query = query.filter(~BienUnivers.id_bien.in_(deja_assignes))

        # Trier par propensity score décroissant
        biens = query.order_by(desc(BienUnivers.propensity_score)).limit(nombre_a_assigner).all()

        if not biens:
            raise HTTPException(
                status_code=404,
                detail=f"Aucun prospect disponible dans les zones de {commercial.prenom} {commercial.nom}"
            )

        # Créer les assignations
        assignments_created = []

        for bien in biens:
            assignment = ProspectAssignment(
                commercial_id=commercial_id,
                bien_id=bien.id_bien,
                propensity_score_at_assignment=bien.propensity_score,
                zone_type=bien.zone_type,
                statut="NOUVEAU",
                priorite="HAUTE" if bien.propensity_score >= 80 else "MOYENNE" if bien.propensity_score >= 60 else "BASSE",
                date_assignation=datetime.utcnow()
            )

            db.add(assignment)
            assignments_created.append({
                "bien_id": bien.id_bien,
                "adresse": bien.adresse,
                "code_postal": bien.code_postal,
                "propensity_score": bien.propensity_score
            })

        # Mettre à jour les stats du commercial
        commercial.nombre_prospects_assignes += len(assignments_created)
        commercial.derniere_assignation = datetime.utcnow()
        commercial.updated_at = datetime.utcnow()

        db.commit()

        return {
            "message": f"{len(assignments_created)} prospects assignés à {commercial.prenom} {commercial.nom}",
            "commercial": commercial.to_dict(),
            "prospects_assignes": assignments_created
        }

    finally:
        db.close()

@router.get("/{commercial_id}/prospects")
async def get_commercial_prospects(
    commercial_id: int,
    statut: Optional[str] = Query(None, description="Filtrer par statut"),
    priorite: Optional[str] = Query(None, description="Filtrer par priorité"),
    limit: int = Query(100, le=500)
):
    """
    Récupérer tous les prospects assignés à un commercial
    """
    db = SessionLocal()
    try:
        query = db.query(ProspectAssignment).filter(
            ProspectAssignment.commercial_id == commercial_id
        )

        if statut:
            query = query.filter(ProspectAssignment.statut == statut)

        if priorite:
            query = query.filter(ProspectAssignment.priorite == priorite)

        assignments = query.order_by(desc(ProspectAssignment.propensity_score_at_assignment)).limit(limit).all()

        # Enrichir avec les infos du bien
        results = []
        for assignment in assignments:
            bien = db.query(BienUnivers).filter(BienUnivers.id_bien == assignment.bien_id).first()

            if bien:
                result = assignment.to_dict()
                result["bien"] = {
                    "adresse": bien.adresse,
                    "code_postal": bien.code_postal,
                    "commune": bien.commune,
                    "type_local": bien.type_local,
                    "surface_reelle": bien.surface_reelle,
                    "nombre_pieces": bien.nombre_pieces,
                    "last_price": bien.last_price
                }
                results.append(result)

        return {
            "commercial_id": commercial_id,
            "total": len(results),
            "prospects": results
        }

    finally:
        db.close()

@router.put("/{commercial_id}/prospects/{assignment_id}")
async def update_prospect_status(
    commercial_id: int,
    assignment_id: int,
    update: AssignmentUpdate
):
    """
    Mettre à jour le statut d'un prospect assigné
    """
    db = SessionLocal()
    try:
        assignment = db.query(ProspectAssignment).filter(
            ProspectAssignment.id == assignment_id,
            ProspectAssignment.commercial_id == commercial_id
        ).first()

        if not assignment:
            raise HTTPException(status_code=404, detail=f"Assignment {assignment_id} non trouvé")

        # Mettre à jour les champs
        update_data = update.dict(exclude_unset=True)

        for field, value in update_data.items():
            setattr(assignment, field, value)

        # Mettre à jour les dates selon le statut
        now = datetime.utcnow()

        if update.statut == "CONTACTE" and not assignment.date_premier_contact:
            assignment.date_premier_contact = now
            assignment.nombre_tentatives_contact += 1

        if update.statut in ["CONTACTE", "EN_COURS"]:
            assignment.date_dernier_contact = now

        assignment.updated_at = now

        db.commit()

        # Recalculer les stats du commercial
        update_commercial_stats(db, commercial_id)

        return {
            "message": "Prospect mis à jour",
            "assignment": assignment.to_dict()
        }

    finally:
        db.close()

# ==================== DASHBOARD ADMIN ====================

@router.get("/dashboard/stats")
async def get_dashboard_stats():
    """
    Statistiques globales pour le dashboard admin
    """
    db = SessionLocal()
    try:
        # Commerciaux
        total_commerciaux = db.query(func.count(Commercial.id)).scalar()
        commerciaux_actifs = db.query(func.count(Commercial.id)).filter(Commercial.actif == True).scalar()

        # Prospects
        total_prospects_assignes = db.query(func.count(ProspectAssignment.id)).scalar()

        prospects_par_statut = db.query(
            ProspectAssignment.statut,
            func.count(ProspectAssignment.id).label('count')
        ).group_by(ProspectAssignment.statut).all()

        # Répartition par commercial
        prospects_par_commercial = db.query(
            Commercial.id,
            Commercial.prenom,
            Commercial.nom,
            func.count(ProspectAssignment.id).label('count')
        ).join(
            ProspectAssignment, Commercial.id == ProspectAssignment.commercial_id
        ).group_by(Commercial.id, Commercial.prenom, Commercial.nom).all()

        # Performance globale
        total_mandats = db.query(func.count(ProspectAssignment.id)).filter(
            ProspectAssignment.statut == "MANDAT_OBTENU"
        ).scalar()

        return {
            "commerciaux": {
                "total": total_commerciaux,
                "actifs": commerciaux_actifs,
                "inactifs": total_commerciaux - commerciaux_actifs
            },
            "prospects": {
                "total_assignes": total_prospects_assignes,
                "par_statut": {statut: count for statut, count in prospects_par_statut},
                "par_commercial": [
                    {
                        "commercial_id": id,
                        "nom": f"{prenom} {nom}",
                        "nombre_prospects": count
                    }
                    for id, prenom, nom, count in prospects_par_commercial
                ]
            },
            "performance": {
                "total_mandats": total_mandats,
                "taux_conversion_global": round(total_mandats / total_prospects_assignes * 100, 2) if total_prospects_assignes > 0 else 0
            }
        }

    finally:
        db.close()

# ==================== FONCTIONS HELPER ====================

def update_commercial_stats(db, commercial_id: int):
    """
    Recalculer les statistiques d'un commercial
    """
    commercial = db.query(Commercial).filter(Commercial.id == commercial_id).first()

    if not commercial:
        return

    # Nombre de prospects par statut
    commercial.nombre_prospects_assignes = db.query(func.count(ProspectAssignment.id)).filter(
        ProspectAssignment.commercial_id == commercial_id,
        ProspectAssignment.statut.in_(["NOUVEAU", "EN_COURS", "CONTACTE", "RDV_PRIS", "INTERESSE"])
    ).scalar()

    commercial.nombre_prospects_contactes = db.query(func.count(ProspectAssignment.id)).filter(
        ProspectAssignment.commercial_id == commercial_id,
        ProspectAssignment.date_premier_contact.isnot(None)
    ).scalar()

    commercial.nombre_rdv_obtenus = db.query(func.count(ProspectAssignment.id)).filter(
        ProspectAssignment.commercial_id == commercial_id,
        ProspectAssignment.date_rdv.isnot(None)
    ).scalar()

    commercial.nombre_mandats_obtenus = db.query(func.count(ProspectAssignment.id)).filter(
        ProspectAssignment.commercial_id == commercial_id,
        ProspectAssignment.statut == "MANDAT_OBTENU"
    ).scalar()

    # Taux de conversion
    total_assignes = db.query(func.count(ProspectAssignment.id)).filter(
        ProspectAssignment.commercial_id == commercial_id
    ).scalar()

    if total_assignes > 0:
        commercial.taux_conversion_contact = (commercial.nombre_prospects_contactes / total_assignes) * 100
        commercial.taux_conversion_rdv = (commercial.nombre_rdv_obtenus / total_assignes) * 100
        commercial.taux_conversion_mandat = (commercial.nombre_mandats_obtenus / total_assignes) * 100

    commercial.updated_at = datetime.utcnow()

    db.commit()

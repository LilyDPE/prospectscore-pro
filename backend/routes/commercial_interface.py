"""
Routes pour l'interface des commerciaux
Chaque commercial peut voir et gérer ses prospects assignés
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from sqlalchemy import desc, func
from datetime import datetime
from database import SessionLocal
from models.commercial import Commercial, ProspectAssignment
from models.bien_univers import BienUnivers

router = APIRouter(prefix="/api/commercial", tags=["commercial"])

# ==================== SCHEMAS ====================

class ActionCommerciale(BaseModel):
    type_action: str  # APPEL, SMS, EMAIL, VISITE, RDV, AUTRE
    notes: str
    date_action: Optional[datetime] = None

class UpdateProspectCommercial(BaseModel):
    statut: Optional[str] = None
    notes_commercial: Optional[str] = None
    action: Optional[ActionCommerciale] = None
    date_rdv: Optional[datetime] = None

# ==================== ENDPOINTS ====================

@router.get("/me/{commercial_id}")
async def get_mon_profil(commercial_id: int):
    """
    Récupérer le profil du commercial connecté
    """
    db = SessionLocal()
    try:
        commercial = db.query(Commercial).filter(Commercial.id == commercial_id).first()

        if not commercial:
            raise HTTPException(status_code=404, detail="Commercial non trouvé")

        return commercial.to_dict()

    finally:
        db.close()

@router.get("/mes-prospects/{commercial_id}")
async def get_mes_prospects(
    commercial_id: int,
    statut: Optional[str] = Query(None, description="Filtrer par statut"),
    priorite: Optional[str] = Query(None, description="Filtrer par priorité"),
    tri: str = Query("propensity_score", description="Champ de tri"),
    ordre: str = Query("desc", description="Ordre de tri (asc/desc)"),
    limit: int = Query(50, le=200)
):
    """
    Récupérer tous mes prospects assignés

    Statuts possibles:
    - NOUVEAU: Vient d'être assigné
    - EN_COURS: En cours de prospection
    - CONTACTE: Contact établi
    - RDV_PRIS: Rendez-vous planifié
    - INTERESSE: Intéressé par une vente
    - MANDAT_OBTENU: Mandat signé
    - PERDU: Prospect perdu
    - ABANDONNE: Prospection abandonnée
    """
    db = SessionLocal()
    try:
        commercial = db.query(Commercial).filter(Commercial.id == commercial_id).first()

        if not commercial:
            raise HTTPException(status_code=404, detail="Commercial non trouvé")

        query = db.query(ProspectAssignment).filter(
            ProspectAssignment.commercial_id == commercial_id
        )

        # Filtres
        if statut:
            query = query.filter(ProspectAssignment.statut == statut)

        if priorite:
            query = query.filter(ProspectAssignment.priorite == priorite)

        # Tri
        if tri == "propensity_score":
            sort_col = ProspectAssignment.propensity_score_at_assignment
        elif tri == "date":
            sort_col = ProspectAssignment.date_assignation
        else:
            sort_col = ProspectAssignment.id

        if ordre == "asc":
            query = query.order_by(sort_col)
        else:
            query = query.order_by(desc(sort_col))

        assignments = query.limit(limit).all()

        # Enrichir avec les infos du bien
        results = []
        for assignment in assignments:
            bien = db.query(BienUnivers).filter(BienUnivers.id_bien == assignment.bien_id).first()

            if bien:
                result = assignment.to_dict()
                result["bien"] = bien.to_dict()
                results.append(result)

        # Stats rapides
        stats = {
            "total": len(results),
            "nouveau": len([r for r in results if r["statut"] == "NOUVEAU"]),
            "en_cours": len([r for r in results if r["statut"] == "EN_COURS"]),
            "contacte": len([r for r in results if r["statut"] == "CONTACTE"]),
            "rdv_pris": len([r for r in results if r["statut"] == "RDV_PRIS"]),
            "mandat_obtenu": len([r for r in results if r["statut"] == "MANDAT_OBTENU"])
        }

        return {
            "commercial": {
                "id": commercial.id,
                "nom": f"{commercial.prenom} {commercial.nom}"
            },
            "stats": stats,
            "prospects": results
        }

    finally:
        db.close()

@router.get("/mes-prospects/{commercial_id}/nouveau")
async def get_mes_nouveaux_prospects(commercial_id: int):
    """
    Récupérer uniquement les nouveaux prospects à traiter
    """
    return await get_mes_prospects(
        commercial_id=commercial_id,
        statut="NOUVEAU",
        tri="propensity_score",
        ordre="desc",
        limit=50
    )

@router.get("/mes-prospects/{commercial_id}/urgent")
async def get_mes_prospects_urgents(commercial_id: int):
    """
    Récupérer les prospects urgents (haute priorité + RDV à venir)
    """
    db = SessionLocal()
    try:
        # Prospects haute priorité non encore contactés
        query = db.query(ProspectAssignment).filter(
            ProspectAssignment.commercial_id == commercial_id,
            ProspectAssignment.priorite == "HAUTE",
            ProspectAssignment.statut.in_(["NOUVEAU", "EN_COURS"])
        )

        assignments = query.order_by(desc(ProspectAssignment.propensity_score_at_assignment)).limit(20).all()

        # Enrichir
        results = []
        for assignment in assignments:
            bien = db.query(BienUnivers).filter(BienUnivers.id_bien == assignment.bien_id).first()

            if bien:
                result = assignment.to_dict()
                result["bien"] = bien.to_dict()
                results.append(result)

        return {
            "message": f"{len(results)} prospects urgents à traiter",
            "prospects": results
        }

    finally:
        db.close()

@router.put("/mes-prospects/{commercial_id}/{assignment_id}")
async def update_mon_prospect(
    commercial_id: int,
    assignment_id: int,
    update: UpdateProspectCommercial
):
    """
    Mettre à jour un de mes prospects

    Exemples de mise à jour:
    - Marquer comme contacté
    - Ajouter des notes
    - Planifier un RDV
    - Enregistrer une action commerciale
    """
    db = SessionLocal()
    try:
        # Vérifier que le prospect appartient bien au commercial
        assignment = db.query(ProspectAssignment).filter(
            ProspectAssignment.id == assignment_id,
            ProspectAssignment.commercial_id == commercial_id
        ).first()

        if not assignment:
            raise HTTPException(
                status_code=404,
                detail="Prospect non trouvé ou vous n'avez pas accès"
            )

        now = datetime.utcnow()

        # Mettre à jour le statut
        if update.statut:
            assignment.statut = update.statut

            # Mettre à jour les dates selon le statut
            if update.statut == "CONTACTE" and not assignment.date_premier_contact:
                assignment.date_premier_contact = now

            if update.statut in ["CONTACTE", "EN_COURS"]:
                assignment.date_dernier_contact = now
                assignment.nombre_tentatives_contact += 1

        # Ajouter les notes
        if update.notes_commercial:
            if assignment.notes_commercial:
                assignment.notes_commercial += f"\n\n[{now}] {update.notes_commercial}"
            else:
                assignment.notes_commercial = f"[{now}] {update.notes_commercial}"

        # Enregistrer l'action
        if update.action:
            if not assignment.historique_actions:
                assignment.historique_actions = []

            action_data = {
                "date": update.action.date_action.isoformat() if update.action.date_action else now.isoformat(),
                "type": update.action.type_action,
                "notes": update.action.notes
            }

            assignment.historique_actions.append(action_data)

        # RDV
        if update.date_rdv:
            assignment.date_rdv = update.date_rdv
            assignment.statut = "RDV_PRIS"

        assignment.updated_at = now

        db.commit()
        db.refresh(assignment)

        # Recalculer les stats du commercial
        from routes.commerciaux import update_commercial_stats
        update_commercial_stats(db, commercial_id)

        return {
            "message": "Prospect mis à jour avec succès",
            "assignment": assignment.to_dict()
        }

    finally:
        db.close()

@router.post("/mes-prospects/{commercial_id}/{assignment_id}/marquer-contacte")
async def marquer_contacte(
    commercial_id: int,
    assignment_id: int,
    notes: str = Query(..., description="Notes sur le contact")
):
    """
    Raccourci pour marquer un prospect comme contacté
    """
    return await update_mon_prospect(
        commercial_id=commercial_id,
        assignment_id=assignment_id,
        update=UpdateProspectCommercial(
            statut="CONTACTE",
            notes_commercial=notes,
            action=ActionCommerciale(
                type_action="APPEL",
                notes=notes
            )
        )
    )

@router.post("/mes-prospects/{commercial_id}/{assignment_id}/prendre-rdv")
async def prendre_rdv(
    commercial_id: int,
    assignment_id: int,
    date_rdv: datetime,
    notes: str = Query(..., description="Notes sur le RDV")
):
    """
    Raccourci pour planifier un rendez-vous
    """
    return await update_mon_prospect(
        commercial_id=commercial_id,
        assignment_id=assignment_id,
        update=UpdateProspectCommercial(
            statut="RDV_PRIS",
            date_rdv=date_rdv,
            notes_commercial=f"RDV planifié le {date_rdv}: {notes}",
            action=ActionCommerciale(
                type_action="RDV",
                notes=notes,
                date_action=date_rdv
            )
        )
    )

@router.get("/mes-stats/{commercial_id}")
async def get_mes_stats(commercial_id: int):
    """
    Mes statistiques de performance
    """
    db = SessionLocal()
    try:
        commercial = db.query(Commercial).filter(Commercial.id == commercial_id).first()

        if not commercial:
            raise HTTPException(status_code=404, detail="Commercial non trouvé")

        # Stats détaillées
        total_prospects = db.query(func.count(ProspectAssignment.id)).filter(
            ProspectAssignment.commercial_id == commercial_id
        ).scalar()

        prospects_par_statut = db.query(
            ProspectAssignment.statut,
            func.count(ProspectAssignment.id).label('count')
        ).filter(
            ProspectAssignment.commercial_id == commercial_id
        ).group_by(ProspectAssignment.statut).all()

        # Prospects cette semaine
        from datetime import timedelta
        date_semaine = datetime.utcnow() - timedelta(days=7)

        nouveaux_cette_semaine = db.query(func.count(ProspectAssignment.id)).filter(
            ProspectAssignment.commercial_id == commercial_id,
            ProspectAssignment.date_assignation >= date_semaine
        ).scalar()

        # RDV à venir
        rdv_a_venir = db.query(func.count(ProspectAssignment.id)).filter(
            ProspectAssignment.commercial_id == commercial_id,
            ProspectAssignment.statut == "RDV_PRIS",
            ProspectAssignment.date_rdv >= datetime.utcnow()
        ).scalar()

        return {
            "commercial": commercial.to_dict(),
            "periode_actuelle": {
                "total_prospects": total_prospects,
                "nouveaux_cette_semaine": nouveaux_cette_semaine,
                "rdv_a_venir": rdv_a_venir
            },
            "repartition_statuts": {statut: count for statut, count in prospects_par_statut},
            "objectifs": {
                "capacite_max": commercial.capacite_max_prospects,
                "prospects_actifs": commercial.nombre_prospects_assignes,
                "places_disponibles": commercial.capacite_max_prospects - commercial.nombre_prospects_assignes
            }
        }

    finally:
        db.close()

@router.get("/mes-zones/{commercial_id}")
async def get_mes_zones(commercial_id: int):
    """
    Mes zones géographiques assignées et opportunités disponibles
    """
    db = SessionLocal()
    try:
        commercial = db.query(Commercial).filter(Commercial.id == commercial_id).first()

        if not commercial:
            raise HTTPException(status_code=404, detail="Commercial non trouvé")

        # Compter les opportunités par zone
        opportunites_par_cp = []

        if commercial.codes_postaux_assignes:
            for cp in commercial.codes_postaux_assignes:
                # Compter les biens disponibles (pas encore assignés)
                count = db.query(func.count(BienUnivers.id_bien)).filter(
                    BienUnivers.code_postal == cp,
                    BienUnivers.features_calculated == True,
                    BienUnivers.propensity_score >= commercial.min_propensity_score,
                    ~BienUnivers.id_bien.in_(
                        db.query(ProspectAssignment.bien_id).filter(
                            ProspectAssignment.statut.in_(["NOUVEAU", "EN_COURS", "CONTACTE", "RDV_PRIS", "INTERESSE"])
                        )
                    )
                ).scalar()

                if count > 0:
                    opportunites_par_cp.append({
                        "code_postal": cp,
                        "opportunites_disponibles": count
                    })

        return {
            "commercial": {
                "id": commercial.id,
                "nom": f"{commercial.prenom} {commercial.nom}"
            },
            "zones_assignees": {
                "codes_postaux": commercial.codes_postaux_assignes or [],
                "departements": commercial.departements_assignes or []
            },
            "opportunites": {
                "par_code_postal": opportunites_par_cp,
                "total_disponible": sum(o["opportunites_disponibles"] for o in opportunites_par_cp)
            }
        }

    finally:
        db.close()

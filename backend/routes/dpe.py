from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from datetime import datetime, date

router = APIRouter(prefix="/api/dpe", tags=["dpe"])

# Modèles Pydantic pour l'API
class DPEImport(BaseModel):
    numero_dpe: str
    adresse: str
    code_postal: str
    commune: str
    latitude: float | None = None
    longitude: float | None = None
    classe_dpe: str
    consommation_energie: float | None = None
    emission_ges: float | None = None
    type_batiment: str | None = None
    annee_construction: int | None = None
    surface_habitable: float | None = None
    date_etablissement_dpe: str | None = None
    statut: str = "nouveau"
    notes: str | None = None
    vu_par: str | None = None

class DPEImportResponse(BaseModel):
    success: bool
    imported: int
    skipped: int
    errors: List[str] = []

@router.post("/import", response_model=DPEImportResponse)
async def import_dpe_from_dpe_pro(dpe_list: List[DPEImport]):
    """
    Reçoit les DPE collectés depuis DPE Pro
    """
    from models.dpe import DPECollecte
    from main import SessionLocal
    
    db = SessionLocal()
    imported = 0
    skipped = 0
    errors = []
    
    try:
        for dpe_data in dpe_list:
            try:
                # Vérifier si le DPE existe déjà
                existing = db.query(DPECollecte).filter(
                    DPECollecte.numero_dpe == dpe_data.numero_dpe
                ).first()
                
                if existing:
                    # Mettre à jour le statut si changé
                    if existing.statut != dpe_data.statut:
                        existing.statut = dpe_data.statut
                        existing.notes = dpe_data.notes
                        existing.vu_par = dpe_data.vu_par
                        existing.updated_at = datetime.utcnow()
                        db.commit()
                    skipped += 1
                    continue
                
                # Créer nouveau DPE
                dpe = DPECollecte(
                    numero_dpe=dpe_data.numero_dpe,
                    adresse=dpe_data.adresse,
                    code_postal=dpe_data.code_postal,
                    commune=dpe_data.commune,
                    latitude=dpe_data.latitude,
                    longitude=dpe_data.longitude,
                    classe_dpe=dpe_data.classe_dpe,
                    consommation_energie=dpe_data.consommation_energie,
                    emission_ges=dpe_data.emission_ges,
                    type_batiment=dpe_data.type_batiment,
                    annee_construction=dpe_data.annee_construction,
                    surface_habitable=dpe_data.surface_habitable,
                    date_etablissement_dpe=datetime.strptime(dpe_data.date_etablissement_dpe, "%Y-%m-%d").date() if dpe_data.date_etablissement_dpe else None,
                    statut=dpe_data.statut,
                    notes=dpe_data.notes,
                    vu_par=dpe_data.vu_par
                )
                
                db.add(dpe)
                imported += 1
                
                if imported % 100 == 0:
                    db.commit()
                
            except Exception as e:
                errors.append(f"Erreur DPE {dpe_data.numero_dpe}: {str(e)}")
                continue
        
        db.commit()
        
        return DPEImportResponse(
            success=True,
            imported=imported,
            skipped=skipped,
            errors=errors
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@router.get("/stats")
async def get_dpe_stats():
    """
    Statistiques des DPE collectés
    """
    from models.dpe import DPECollecte
    from main import SessionLocal
    from sqlalchemy import func
    
    db = SessionLocal()
    
    try:
        total = db.query(func.count(DPECollecte.id)).scalar()
        
        by_classe = db.query(
            DPECollecte.classe_dpe,
            func.count(DPECollecte.id)
        ).group_by(DPECollecte.classe_dpe).all()
        
        by_statut = db.query(
            DPECollecte.statut,
            func.count(DPECollecte.id)
        ).group_by(DPECollecte.statut).all()
        
        return {
            "total": total,
            "par_classe": {classe: count for classe, count in by_classe},
            "par_statut": {statut: count for statut, count in by_statut}
        }
    finally:
        db.close()

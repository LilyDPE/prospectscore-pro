from fastapi import APIRouter
from typing import Optional
from pydantic import BaseModel

router = APIRouter(prefix="/api/public", tags=["public"])

@router.get("/departements")
async def get_departements():
    from models.dvf import TransactionDVF
    from database import SessionLocal
    from sqlalchemy import func
    
    db = SessionLocal()
    try:
        departements = db.query(
            TransactionDVF.departement,
            func.count(TransactionDVF.id).label('count')
        ).group_by(TransactionDVF.departement).all()
        
        return {"departements": [{"code": d.departement, "count": d.count} for d in departements]}
    finally:
        db.close()

@router.get("/stats")
async def get_stats():
    from models.dvf import TransactionDVF
    from database import SessionLocal
    from sqlalchemy import func
    
    db = SessionLocal()
    try:
        total = db.query(func.count(TransactionDVF.id)).scalar()
        by_dept = db.query(TransactionDVF.departement, func.count(TransactionDVF.id)).group_by(TransactionDVF.departement).all()
        by_type = db.query(TransactionDVF.type_local, func.count(TransactionDVF.id)).group_by(TransactionDVF.type_local).all()
        avg_price = db.query(func.avg(TransactionDVF.valeur_fonciere)).scalar()
        
        return {
            "total": total,
            "par_departement": {d: c for d, c in by_dept},
            "par_type": {t: c for t, c in by_type},
            "prix_moyen": round(avg_price, 2) if avg_price else 0
        }
    finally:
        db.close()

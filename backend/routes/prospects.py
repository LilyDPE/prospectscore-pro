from fastapi import APIRouter
from typing import Optional, List
from pydantic import BaseModel

router = APIRouter(prefix="/api/prospects", tags=["prospects"])

class ProspectFilter(BaseModel):
    departements: Optional[List[str]] = None
    communes: Optional[List[str]] = None
    codes_postaux: Optional[List[str]] = None
    type_local: Optional[str] = None
    score_min: Optional[int] = None
    score_max: Optional[int] = None
    surface_min: Optional[float] = None
    surface_max: Optional[float] = None
    prix_min: Optional[float] = None
    prix_max: Optional[float] = None
    date_avant: Optional[str] = None
    date_apres: Optional[str] = None
    limit: int = 50
    offset: int = 0
    sort_by: str = "score"
    sort_order: str = "desc"

class RadiusSearch(BaseModel):
    latitude: float
    longitude: float
    radius_km: float = 10
    limit: int = 500
    sort_by: str = "score"

@router.post("/search")
async def search_prospects(filters: ProspectFilter):
    from models.dvf import TransactionDVF
    from database import SessionLocal
    from sqlalchemy import desc, asc
    
    db = SessionLocal()
    try:
        query = db.query(TransactionDVF)
        
        if filters.departements:
            query = query.filter(TransactionDVF.departement.in_(filters.departements))
        if filters.communes:
            query = query.filter(TransactionDVF.commune.in_(filters.communes))
        if filters.codes_postaux:
            query = query.filter(TransactionDVF.code_postal.in_(filters.codes_postaux))
        if filters.type_local:
            query = query.filter(TransactionDVF.type_local == filters.type_local)
        if filters.score_min:
            query = query.filter(TransactionDVF.score >= filters.score_min)
        if filters.score_max:
            query = query.filter(TransactionDVF.score <= filters.score_max)
        if filters.surface_min:
            query = query.filter(TransactionDVF.surface_reelle >= filters.surface_min)
        if filters.surface_max:
            query = query.filter(TransactionDVF.surface_reelle <= filters.surface_max)
        if filters.prix_min:
            query = query.filter(TransactionDVF.valeur_fonciere >= filters.prix_min)
        if filters.prix_max:
            query = query.filter(TransactionDVF.valeur_fonciere <= filters.prix_max)
        if filters.date_avant:
            query = query.filter(TransactionDVF.date_mutation <= filters.date_avant)
        if filters.date_apres:
            query = query.filter(TransactionDVF.date_mutation >= filters.date_apres)
        
        total = query.count()
        sort_column = getattr(TransactionDVF, filters.sort_by, TransactionDVF.score)
        if filters.sort_order == "desc":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))
        
        prospects = query.offset(filters.offset).limit(filters.limit).all()
        
        return {
            "total": total,
            "count": len(prospects),
            "offset": filters.offset,
            "limit": filters.limit,
            "prospects": [{
                "id": p.id,
                "adresse": p.adresse,
                "code_postal": p.code_postal,
                "commune": p.commune,
                "departement": p.departement,
                "type": p.type_local,
                "surface": p.surface_reelle,
                "pieces": p.nombre_pieces,
                "valeur": p.valeur_fonciere,
                "score": p.score,
                "date_mutation": str(p.date_mutation),
                "classe_dpe": p.classe_dpe,
                "valeur_dpe": p.valeur_dpe,
                "duree_detention": p.duree_detention_estimee,
                "proprietaire_type": p.proprietaire_type,
                "proprietaire_nom": p.proprietaire_nom
            } for p in prospects]
        }
    finally:
        db.close()

@router.post("/search-radius")
async def search_by_radius(params: RadiusSearch):
    """Recherche par rayon géographique (en km)"""
    from models.dvf import TransactionDVF
    from database import SessionLocal
    from sqlalchemy import text
    
    db = SessionLocal()
    try:
        order_clause = "score DESC, distance_km ASC" if params.sort_by == "score" else "distance_km ASC, score DESC"
        
        sql = text(f"""
            SELECT id, adresse, commune, code_postal, departement, type_local, 
                   surface_reelle, nombre_pieces, valeur_fonciere, score, 
                   date_mutation, latitude, longitude, classe_dpe, valeur_dpe,
                   duree_detention_estimee, proprietaire_type, proprietaire_nom,
                   (6371 * acos(
                       cos(radians(:lat)) * cos(radians(latitude)) * 
                       cos(radians(longitude) - radians(:lon)) + 
                       sin(radians(:lat)) * sin(radians(latitude))
                   )) AS distance_km
            FROM transactions_dvf
            WHERE latitude IS NOT NULL 
              AND longitude IS NOT NULL
              AND (6371 * acos(
                       cos(radians(:lat)) * cos(radians(latitude)) * 
                       cos(radians(longitude) - radians(:lon)) + 
                       sin(radians(:lat)) * sin(radians(latitude))
                   )) <= :radius
            ORDER BY {order_clause}
            LIMIT :limit
        """)
        
        result = db.execute(sql, {
            'lat': params.latitude,
            'lon': params.longitude,
            'radius': params.radius_km,
            'limit': params.limit
        })
        
        prospects = []
        for row in result:
            prospects.append({
                "id": row.id,
                "adresse": row.adresse,
                "commune": row.commune,
                "code_postal": row.code_postal,
                "departement": row.departement,
                "type": row.type_local,
                "surface": row.surface_reelle,
                "pieces": row.nombre_pieces,
                "valeur": row.valeur_fonciere,
                "score": row.score,
                "date_mutation": str(row.date_mutation) if row.date_mutation else None,
                "classe_dpe": row.classe_dpe,
                "valeur_dpe": row.valeur_dpe,
                "duree_detention": row.duree_detention_estimee,
                "proprietaire_type": row.proprietaire_type,
                "proprietaire_nom": row.proprietaire_nom,
                "distance_km": round(row.distance_km, 2)
            })
        
        return {
            "total": len(prospects),
            "prospects": prospects
        }
    finally:
        db.close()

@router.get("/communes")
async def get_communes(departement: Optional[str] = None):
    from models.dvf import TransactionDVF
    from database import SessionLocal
    from sqlalchemy import func
    
    db = SessionLocal()
    try:
        query = db.query(
            TransactionDVF.commune,
            TransactionDVF.code_postal,
            func.count(TransactionDVF.id).label('count')
        )
        if departement:
            query = query.filter(TransactionDVF.departement == departement)
        
        communes = query.group_by(
            TransactionDVF.commune,
            TransactionDVF.code_postal
        ).order_by(TransactionDVF.commune).all()
        
        return {"communes": [{"commune": c.commune, "code_postal": c.code_postal, "count": c.count} for c in communes]}
    finally:
        db.close()

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

@router.get("/export/csv")
async def export_csv(
    departement: Optional[str] = None,
    score_min: Optional[int] = 50,
    proprietaire_type: Optional[str] = None,
    limit: int = 1000
):
    from models.dvf import TransactionDVF
    from database import SessionLocal
    from fastapi.responses import StreamingResponse
    import csv
    import io
    
    db = SessionLocal()
    try:
        query = db.query(TransactionDVF).filter(TransactionDVF.score >= score_min)
        if departement:
            query = query.filter(TransactionDVF.departement == departement)
        if proprietaire_type:
            query = query.filter(TransactionDVF.proprietaire_type == proprietaire_type)
        
        prospects = query.order_by(TransactionDVF.score.desc()).limit(limit).all()
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Adresse', 'Code Postal', 'Commune', 'Type', 'Surface', 'Pièces', 'Prix', 'Score', 'Date', 'Propriétaire'])
        
        for p in prospects:
            writer.writerow([
                p.adresse, p.code_postal, p.commune, p.type_local,
                p.surface_reelle, p.nombre_pieces, p.valeur_fonciere,
                p.score, p.date_mutation, p.proprietaire_nom or 'Particulier'
            ])
        
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=prospects_{departement or 'all'}.csv"}
        )
    finally:
        db.close()


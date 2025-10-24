from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

router = APIRouter(prefix="/api/collaboration", tags=["collaboration"])

class StartSession(BaseModel):
    transaction_id: int
    commercial: str

class TrackConsultation(BaseModel):
    transaction_id: int
    commercial: str
    duree_consultation: Optional[int] = None
    action: str = "vue"  # "vue", "appel", "email"

@router.post("/start-session")
async def start_session(session: StartSession):
    """Démarrer une session de travail sur un prospect"""
    from database import SessionLocal
    from sqlalchemy import text
    
    db = SessionLocal()
    try:
        # Vérifier si quelqu'un d'autre travaille dessus
        active = db.execute(text("""
            SELECT commercial, debut_session 
            FROM sessions_actives 
            WHERE transaction_id = :tid 
              AND commercial != :comm
              AND derniere_activite > NOW() - INTERVAL '10 minutes'
        """), {"tid": session.transaction_id, "comm": session.commercial}).fetchone()
        
        if active:
            return {
                "success": False,
                "warning": f"⚠️ {active.commercial} travaille dessus depuis {active.debut_session.strftime('%H:%M')}",
                "commercial_actif": active.commercial
            }
        
        # Enregistrer la session
        db.execute(text("""
            INSERT INTO sessions_actives (transaction_id, commercial)
            VALUES (:tid, :comm)
            ON CONFLICT (transaction_id, commercial) 
            DO UPDATE SET derniere_activite = NOW()
        """), {"tid": session.transaction_id, "comm": session.commercial})
        
        db.commit()
        
        return {"success": True, "message": "Session démarrée"}
    finally:
        db.close()

@router.post("/end-session")
async def end_session(session: StartSession):
    """Terminer une session de travail"""
    from database import SessionLocal
    from sqlalchemy import text
    
    db = SessionLocal()
    try:
        db.execute(text("""
            DELETE FROM sessions_actives 
            WHERE transaction_id = :tid AND commercial = :comm
        """), {"tid": session.transaction_id, "comm": session.commercial})
        
        db.commit()
        
        return {"success": True}
    finally:
        db.close()

@router.post("/track-consultation")
async def track_consultation(consult: TrackConsultation):
    """Enregistrer qu'un commercial a consulté un prospect"""
    from database import SessionLocal
    from sqlalchemy import text
    
    db = SessionLocal()
    try:
        db.execute(text("""
            INSERT INTO consultations_prospects 
                (transaction_id, commercial, duree_consultation, action)
            VALUES 
                (:tid, :comm, :duree, :action)
        """), {
            "tid": consult.transaction_id,
            "comm": consult.commercial,
            "duree": consult.duree_consultation,
            "action": consult.action
        })
        
        db.commit()
        
        return {"success": True}
    finally:
        db.close()

@router.get("/prospect-history/{transaction_id}")
async def get_prospect_history(transaction_id: int):
    """Historique complet des consultations d'un prospect"""
    from database import SessionLocal
    from sqlalchemy import text
    
    db = SessionLocal()
    try:
        # Historique des consultations
        consultations = db.execute(text("""
            SELECT 
                commercial,
                date_consultation,
                action,
                duree_consultation
            FROM consultations_prospects
            WHERE transaction_id = :tid
            ORDER BY date_consultation DESC
            LIMIT 50
        """), {"tid": transaction_id}).fetchall()
        
        # Notes et actions
        notes = db.execute(text("""
            SELECT 
                commercial,
                statut,
                note,
                date_action,
                date_rappel
            FROM notes_prospection
            WHERE transaction_id = :tid
        """), {"tid": transaction_id}).fetchone()
        
        # Sessions actives
        actifs = db.execute(text("""
            SELECT commercial, debut_session, derniere_activite
            FROM sessions_actives
            WHERE transaction_id = :tid
              AND derniere_activite > NOW() - INTERVAL '10 minutes'
        """), {"tid": transaction_id}).fetchall()
        
        return {
            "success": True,
            "consultations": [dict(row._mapping) for row in consultations],
            "note": dict(notes._mapping) if notes else None,
            "commerciaux_actifs": [dict(row._mapping) for row in actifs]
        }
    finally:
        db.close()

@router.get("/team-activity")
async def get_team_activity():
    """Activité de l'équipe en temps réel"""
    from database import SessionLocal
    from sqlalchemy import text
    
    db = SessionLocal()
    try:
        # Stats par commercial
        stats = db.execute(text("SELECT * FROM stats_par_commercial")).fetchall()
        
        # Activité en cours
        sessions = db.execute(text("""
            SELECT 
                s.commercial,
                t.adresse,
                t.commune,
                t.propensity_score,
                s.debut_session,
                EXTRACT(EPOCH FROM (NOW() - s.debut_session))::integer as duree_sec
            FROM sessions_actives s
            JOIN transactions_dvf t ON s.transaction_id = t.id
            WHERE s.derniere_activite > NOW() - INTERVAL '10 minutes'
            ORDER BY s.debut_session DESC
        """)).fetchall()
        
        # Consultations du jour
        consultations_jour = db.execute(text("""
            SELECT 
                commercial,
                COUNT(*) as nb_vues,
                COUNT(DISTINCT transaction_id) as nb_prospects_uniques
            FROM consultations_prospects
            WHERE date_consultation >= CURRENT_DATE
            GROUP BY commercial
            ORDER BY nb_vues DESC
        """)).fetchall()
        
        return {
            "success": True,
            "stats_commerciaux": [dict(row._mapping) for row in stats],
            "sessions_actives": [dict(row._mapping) for row in sessions],
            "activite_du_jour": [dict(row._mapping) for row in consultations_jour]
        }
    finally:
        db.close()

@router.get("/my-prospects/{commercial}")
async def get_my_prospects(commercial: str):
    """Mes prospects consultés récemment"""
    from database import SessionLocal
    from sqlalchemy import text
    
    db = SessionLocal()
    try:
        prospects = db.execute(text("""
            SELECT DISTINCT ON (t.id)
                t.id,
                t.adresse,
                t.commune,
                t.code_postal,
                t.type_local,
                t.surface_reelle,
                t.valeur_fonciere,
                t.propensity_score,
                c.date_consultation as ma_derniere_vue,
                n.statut as mon_statut,
                n.note as ma_note,
                (SELECT COUNT(*) FROM consultations_prospects 
                 WHERE transaction_id = t.id AND commercial != :comm) as nb_autres_commerciaux
            FROM transactions_dvf t
            JOIN consultations_prospects c ON t.id = c.transaction_id
            LEFT JOIN notes_prospection n ON t.id = n.transaction_id AND n.commercial = :comm
            WHERE c.commercial = :comm
            ORDER BY t.id, c.date_consultation DESC
            LIMIT 50
        """), {"comm": commercial}).fetchall()
        
        return {
            "success": True,
            "count": len(prospects),
            "prospects": [dict(row._mapping) for row in prospects]
        }
    finally:
        db.close()


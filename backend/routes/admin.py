from middleware.auth import verify_admin_key
from fastapi import Depends, File, UploadFile
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
import logging

router = APIRouter(prefix="/api/admin", tags=["admin"])
logger = logging.getLogger(__name__)

class ImportDVFRequest(BaseModel):
    departements: List[str] = ["76", "80"]  # Seine-Maritime et Somme par défaut
    years: List[int] = [2024, 2023]

class ImportDVFResponse(BaseModel):
    success: bool
    message: str
    results: dict

@router.post("/import-dvf", response_model=ImportDVFResponse)
async def import_dvf(
    request: ImportDVFRequest,
    background_tasks: BackgroundTasks
):
    """
    Import les données DVF (transactions immobilières) pour les départements demandés

    Départements disponibles : 76 (Seine-Maritime), 80 (Somme), 27 (Eure), 14 (Calvados), etc.
    ⚠️ ATTENTION : L'API data.gouv.fr ne propose que 2023-2025
    Pour les années antérieures, utilisez /import-dvf-file avec upload manuel
    """
    from services.dvf_importer import DVFImporter
    from database import SessionLocal

    db = SessionLocal()

    try:
        logger.info(f"🚀 Lancement import DVF: {request.departements} - {request.years}")

        importer = DVFImporter(db)
        results = importer.run_import(
            departements=request.departements,
            years=request.years
        )

        return ImportDVFResponse(
            success=True,
            message=f"Import terminé : {results['global_imported']} transactions importées",
            results=results
        )

    except Exception as e:
        logger.error(f"❌ Erreur import DVF: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@router.post("/import-dvf-file")
async def import_dvf_from_file(file: UploadFile = File(...)):
    """
    Import DVF depuis un fichier uploadé

    Utilisez cette route pour importer des fichiers DVF historiques (2014-2019)
    téléchargés depuis data.gouv.fr

    Formats acceptés: CSV, TXT, CSV.GZ, TXT.GZ
    """
    from services.dvf_importer import DVFImporter
    from database import SessionLocal
    import pandas as pd
    import gzip
    import io

    db = SessionLocal()

    try:
        logger.info(f"📥 Upload fichier DVF: {file.filename}")

        # Lire le fichier
        content = await file.read()

        # Décompresser si .gz
        if file.filename.endswith('.gz'):
            content = gzip.decompress(content)

        # Parser CSV/TXT avec détection automatique du format
        # Les fichiers DVF peuvent avoir différents séparateurs: |, ,, ; ou \t
        df = None
        parsing_errors = []

        # Liste des configurations à essayer
        configs = [
            {'sep': '|', 'encoding': 'utf-8', 'on_bad_lines': 'skip'},
            {'sep': ',', 'encoding': 'utf-8', 'on_bad_lines': 'skip'},
            {'sep': ';', 'encoding': 'utf-8', 'on_bad_lines': 'skip'},
            {'sep': '|', 'encoding': 'iso-8859-1', 'on_bad_lines': 'skip'},
            {'sep': ',', 'encoding': 'iso-8859-1', 'on_bad_lines': 'skip'},
        ]

        for config in configs:
            try:
                df = pd.read_csv(io.BytesIO(content), low_memory=False, **config)
                # Vérifier que le DataFrame a des colonnes valides
                if len(df.columns) > 10:  # DVF a normalement 40+ colonnes
                    logger.info(f"✅ Parsing réussi avec sep='{config['sep']}', encoding={config['encoding']}")
                    break
                else:
                    df = None
            except Exception as e:
                parsing_errors.append(f"{config['sep']}/{config['encoding']}: {str(e)[:50]}")
                continue

        if df is None or df.empty:
            error_msg = "Impossible de parser le fichier. Erreurs:\n" + "\n".join(parsing_errors)
            logger.error(error_msg)
            raise HTTPException(status_code=400, detail=error_msg)

        logger.info(f"📊 {len(df)} lignes, {len(df.columns)} colonnes dans le fichier")

        # Utiliser l'importer existant
        importer = DVFImporter(db)

        logger.info(f"🔍 AVANT clean_and_filter_data: {len(df)} lignes")
        df_clean = importer.clean_and_filter_data(df)
        logger.info(f"🔍 APRÈS clean_and_filter_data: {len(df_clean)} lignes")

        imported = importer.import_to_database(df_clean)
        logger.info(f"🔍 APRÈS import_to_database: {imported}")

        db.commit()

        return {
            "success": True,
            "message": f"Import réussi : {imported} transactions",
            "filename": file.filename,
            "total_lines": len(df),
            "filtered_lines": len(df_clean),
            "imported": imported
        }

    except Exception as e:
        logger.error(f"❌ Erreur import fichier: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@router.get("/dvf/stats")
async def get_dvf_stats():
    """Statistiques des transactions DVF importées"""
    from models.dvf import TransactionDVF
    from database import SessionLocal
    from sqlalchemy import func
    
    db = SessionLocal()
    
    try:
        total = db.query(func.count(TransactionDVF.id)).scalar()
        
        by_dept = db.query(
            TransactionDVF.departement,
            func.count(TransactionDVF.id)
        ).group_by(TransactionDVF.departement).all()
        
        by_type = db.query(
            TransactionDVF.type_local,
            func.count(TransactionDVF.id)
        ).group_by(TransactionDVF.type_local).all()
        
        avg_price = db.query(func.avg(TransactionDVF.valeur_fonciere)).scalar()
        avg_score = db.query(func.avg(TransactionDVF.score)).scalar()
        
        return {
            "total_transactions": total,
            "par_departement": {dep: count for dep, count in by_dept},
            "par_type": {type_: count for type_, count in by_type},
            "prix_moyen": round(avg_price, 2) if avg_price else 0,
            "score_moyen": round(avg_score, 1) if avg_score else 0
        }
    finally:
        db.close()

@router.get("/prospects/top")
async def get_top_prospects(limit: int = 50):
    """Liste des meilleurs prospects (score le plus élevé)"""
    from models.dvf import TransactionDVF
    from database import SessionLocal
    
    db = SessionLocal()
    
    try:
        prospects = db.query(TransactionDVF).order_by(
            TransactionDVF.score.desc()
        ).limit(limit).all()
        
        return {
            "count": len(prospects),
            "prospects": [
                {
                    "id": p.id,
                    "adresse": p.adresse,
                    "code_postal": p.code_postal,
                    "commune": p.commune,
                    "type": p.type_local,
                    "surface": p.surface_reelle,
                    "valeur": p.valeur_fonciere,
                    "score": p.score,
                    "date_mutation": str(p.date_mutation)
                }
                for p in prospects
            ]
        }
    finally:
        db.close()

@router.post("/geocode")
async def geocode_transactions(limit: int = 1000):
    """Géocode les transactions sans coordonnées"""
    from database import SessionLocal
    from services.geocoder import Geocoder
    
    db = SessionLocal()
    try:
        geocoder = Geocoder(db)
        count = geocoder.geocode_all_transactions(limit)
        return {"success": True, "geocoded": count}
    finally:
        db.close()

@router.post("/enrich-pappers")
async def enrich_with_pappers(score_min: int = 50, limit: int = 100):
    """Enrichit les meilleurs prospects avec les données Pappers"""
    from database import SessionLocal
    from services.pappers_enricher import PappersEnricher
    import os
    
    api_key = os.getenv("PAPPERS_API_KEY", "020b0e8749ac34abbfbba54e1e195ba8db4d59a72c0ba7f3")
    
    db = SessionLocal()
    try:
        enricher = PappersEnricher(api_key, db)
        count = enricher.enrich_best_prospects(score_min, limit)
        return {"success": True, "enriched": count}
    finally:
        db.close()

@router.post("/enrich-sirene")
async def enrich_with_sirene(score_min: int = 50, limit: int = 100):
    """Enrichit les meilleurs prospects avec SIRENE (API gratuite INSEE)"""
    from database import SessionLocal
    from services.sirene_enricher import SireneEnricher
    
    db = SessionLocal()
    try:
        enricher = SireneEnricher(db)
        result = enricher.enrich_best_prospects(score_min, limit)
        return {"success": True, **result}
    finally:
        db.close()

@router.post("/enrich-sirene")
async def enrich_with_sirene(score_min: int = 50, limit: int = 100):
    """Enrichit avec SIRENE (API gratuite INSEE)"""
    from database import SessionLocal
    from services.sirene_enricher import SireneEnricher
    
    db = SessionLocal()
    try:
        enricher = SireneEnricher(db)
        result = enricher.enrich_best_prospects(score_min, limit)
        return {"success": True, **result}
    finally:
        db.close()

@router.post("/enrich-bodacc")
async def enrich_with_bodacc(score_min: int = 50, limit: int = 1000):
    """Enrichit avec BODACC (100% gratuit, données publiques)"""
    from database import SessionLocal
    from services.bodacc_enricher import BodaccEnricher
    
    db = SessionLocal()
    try:
        enricher = BodaccEnricher(db)
        result = enricher.enrich_from_bodacc(score_min, limit)
        return {"success": True, **result}
    finally:
        db.close()

@router.post("/enrich-smart")
async def enrich_smart(score_min: int = 50, limit: int = 100):
    """Enrichissement intelligent multi-sources (100% gratuit)"""
    from database import SessionLocal
    from services.smart_enricher import SmartEnricher
    
    db = SessionLocal()
    try:
        enricher = SmartEnricher(db)
        result = enricher.enrich_transactions(score_min, limit)
        return {"success": True, **result}
    finally:
        db.close()

@router.post("/analyze-propensity")
async def analyze_propensity(score_min: int = 40, limit: int = 1000):
    """Analyse la propension à vendre - LE GAME CHANGER"""
    from database import SessionLocal
    from services.propensity_predictor import PropensityToSellPredictor
    
    db = SessionLocal()
    try:
        predictor = PropensityToSellPredictor(db)
        result = predictor.analyze_batch(score_min, limit)
        return {"success": True, **result}
    finally:
        db.close()

@router.get("/prospects-hot")
async def get_hot_prospects(limit: int = 50):
    """Récupère les prospects HOT (score >75) à contacter en priorité"""
    from database import SessionLocal
    from sqlalchemy import text
    
    db = SessionLocal()
    try:
        result = db.execute(text(f"SELECT * FROM prospects_hot LIMIT {limit}"))
        prospects = [dict(row._mapping) for row in result]
        return {"success": True, "count": len(prospects), "prospects": prospects}
    finally:
        db.close()

@router.get("/prospects-summary", dependencies=[Depends(verify_admin_key)])
async def get_prospects_summary():
    """Dashboard : agrégats et KPIs du système de propension"""
    from database import SessionLocal
    from sqlalchemy import text, func
    
    db = SessionLocal()
    try:
        # Stats globales
        stats = db.execute(text("""
            SELECT 
                COUNT(*) as total_prospects,
                COUNT(*) FILTER (WHERE propensity_score >= 90) as urgent,
                COUNT(*) FILTER (WHERE propensity_score >= 75) as hot,
                COUNT(*) FILTER (WHERE propensity_score >= 60) as medium,
                COUNT(*) FILTER (WHERE propensity_score >= 40) as low,
                ROUND(AVG(propensity_score), 1) as avg_score,
                COUNT(*) FILTER (WHERE turnover_regulier = true) as investisseurs_actifs,
                COUNT(*) FILTER (WHERE classe_dpe IN ('F', 'G')) as passoires_thermiques,
                COUNT(*) FILTER (WHERE cohorte_vente_active = true) as cohorte_active,
                COUNT(*) FILTER (WHERE next_contact_date <= CURRENT_DATE + INTERVAL '7 days') as a_contacter_cette_semaine
            FROM transactions_dvf
            WHERE propensity_score > 0
        """)).fetchone()
        
        # Top 10 communes HOT
        top_communes = db.execute(text("""
            SELECT 
                commune,
                COUNT(*) as nb_prospects,
                ROUND(AVG(propensity_score), 1) as score_moyen,
                COUNT(*) FILTER (WHERE propensity_score >= 75) as nb_hot
            FROM transactions_dvf
            WHERE propensity_score >= 60
            GROUP BY commune
            ORDER BY nb_hot DESC, score_moyen DESC
            LIMIT 10
        """)).fetchall()
        
        # Distribution par timeframe
        timeframes = db.execute(text("""
            SELECT 
                propensity_timeframe,
                COUNT(*) as count
            FROM transactions_dvf
            WHERE propensity_score >= 60
            GROUP BY propensity_timeframe
            ORDER BY count DESC
        """)).fetchall()
        
        # Prochaines actions (cette semaine)
        next_actions = db.execute(text("""
            SELECT 
                next_contact_date::date,
                contact_priority,
                COUNT(*) as nb_contacts
            FROM transactions_dvf
            WHERE next_contact_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '7 days'
            GROUP BY next_contact_date, contact_priority
            ORDER BY next_contact_date, contact_priority
        """)).fetchall()
        
        return {
            "success": True,
            "stats": dict(stats._mapping) if stats else {},
            "top_communes": [dict(row._mapping) for row in top_communes],
            "timeframes": [dict(row._mapping) for row in timeframes],
            "next_actions": [dict(row._mapping) for row in next_actions]
        }
    finally:
        db.close()

@router.get("/prospects-to-contact-today", dependencies=[Depends(verify_admin_key)])
async def get_prospects_to_contact_today():
    """Liste des prospects à contacter AUJOURD'HUI"""
    from database import SessionLocal
    from sqlalchemy import text
    from datetime import datetime

    db = SessionLocal()
    try:
        prospects = db.execute(text("""
            SELECT
                id, adresse, code_postal, commune,
                type_local, surface_reelle, valeur_fonciere,
                propensity_score, propensity_timeframe, contact_priority,
                propensity_raisons, next_contact_date,
                duree_detention_estimee, classe_dpe
            FROM transactions_dvf
            WHERE next_contact_date = CURRENT_DATE
            ORDER BY propensity_score DESC, contact_priority
            LIMIT 50
        """)).fetchall()

        return {
            "success": True,
            "date": str(datetime.now().date()),
            "count": len(prospects),
            "prospects": [dict(row._mapping) for row in prospects]
        }
    finally:
        db.close()

# ==================== AUTO-LEARNING ENDPOINTS ====================

class FeedbackRequest(BaseModel):
    prospect_id: int
    statut_final: int  # 0=Pas vendu/Refus, 1=Vendu, 2=En négociation
    feedback_agent: Optional[str] = None
    prix_vente_reel: Optional[float] = None
    contacted: bool = True

@router.post("/feedback")
async def submit_agent_feedback(feedback: FeedbackRequest):
    """
    Permet aux agents de soumettre un feedback sur un prospect
    C'est le feedback RAPIDE qui nourrit l'IA immédiatement
    """
    from database import SessionLocal
    from models.dvf import TransactionDVF
    from datetime import datetime

    db = SessionLocal()
    try:
        prospect = db.query(TransactionDVF).filter(
            TransactionDVF.id == feedback.prospect_id
        ).first()

        if not prospect:
            raise HTTPException(status_code=404, detail="Prospect non trouvé")

        # Calculer le délai entre prédiction et feedback
        delai = None
        if prospect.derniere_analyse_propension:
            delai = (datetime.now() - prospect.derniere_analyse_propension).days

        # Mettre à jour le statut
        prospect.statut_final = feedback.statut_final
        prospect.source_validation = "AGENT_FEEDBACK"
        prospect.date_validation = datetime.now()
        prospect.feedback_agent = feedback.feedback_agent
        prospect.prix_vente_reel = feedback.prix_vente_reel
        prospect.delai_vente_jours = delai

        if feedback.contacted:
            prospect.contacted_at = datetime.now()

        # Calculer la précision de notre prédiction
        if feedback.statut_final == 1:  # Vendu
            if prospect.propensity_score >= 75:
                prospect.precision_prediction = 1.0  # On avait raison !
            elif prospect.propensity_score >= 60:
                prospect.precision_prediction = 0.7
            else:
                prospect.precision_prediction = 0.3
        else:  # Pas vendu
            if prospect.propensity_score < 60:
                prospect.precision_prediction = 1.0  # On avait raison de ne pas trop y croire
            else:
                prospect.precision_prediction = 0.0  # Faux positif

        db.commit()

        logger.info(
            f"✅ Feedback reçu pour prospect {feedback.prospect_id}: "
            f"statut={feedback.statut_final}, délai={delai} jours"
        )

        return {
            "success": True,
            "message": "Feedback enregistré avec succès",
            "prospect_id": feedback.prospect_id,
            "precision_prediction": prospect.precision_prediction
        }
    finally:
        db.close()

@router.post("/reconcile-dvf")
async def reconcile_dvf_sales(
    min_similarity: float = 0.7,
    lookback_months: int = 18
):
    """
    Lance le rapprochement DVF pour détecter les ventes confirmées
    C'est la VÉRITÉ TERRAIN qui valide nos prédictions
    """
    from database import SessionLocal
    from services.dvf_matcher import DVFMatcher

    db = SessionLocal()
    try:
        matcher = DVFMatcher(db)
        result = matcher.reconcile_sales(
            min_similarity=min_similarity,
            lookback_months=lookback_months
        )

        return {
            "success": True,
            "message": f"{result['matches_trouves']} ventes confirmées par DVF",
            **result
        }
    finally:
        db.close()

@router.post("/train-ml-model")
async def train_ml_model(model_type: str = "random_forest"):
    """
    Entraîne le modèle ML avec toutes les données validées

    model_type: 'random_forest', 'gradient_boosting', ou 'xgboost'
    """
    from database import SessionLocal
    from services.ml_trainer import MLTrainer

    db = SessionLocal()
    try:
        trainer = MLTrainer(db)
        result = trainer.train_model(model_type=model_type)

        return {
            "success": True,
            "message": f"Modèle {model_type} entraîné avec succès",
            **result
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@router.get("/ml-training-stats")
async def get_ml_training_stats():
    """Statistiques sur les données disponibles pour l'entraînement"""
    from database import SessionLocal
    from sqlalchemy import func, text
    from models.dvf import TransactionDVF

    db = SessionLocal()
    try:
        # Compter les données validées
        total_validé = db.query(func.count(TransactionDVF.id)).filter(
            TransactionDVF.statut_final.isnot(None)
        ).scalar()

        vendus = db.query(func.count(TransactionDVF.id)).filter(
            TransactionDVF.statut_final == 1
        ).scalar()

        pas_vendus = db.query(func.count(TransactionDVF.id)).filter(
            TransactionDVF.statut_final == 0
        ).scalar()

        deja_utilisé = db.query(func.count(TransactionDVF.id)).filter(
            TransactionDVF.utilisé_pour_training == True
        ).scalar()

        nouveau_disponible = db.query(func.count(TransactionDVF.id)).filter(
            TransactionDVF.statut_final.isnot(None),
            TransactionDVF.utilisé_pour_training == False
        ).scalar()

        # Distribution par source de validation
        by_source = db.query(
            TransactionDVF.source_validation,
            func.count(TransactionDVF.id)
        ).filter(
            TransactionDVF.statut_final.isnot(None)
        ).group_by(TransactionDVF.source_validation).all()

        # Précision moyenne
        avg_precision = db.query(func.avg(TransactionDVF.precision_prediction)).filter(
            TransactionDVF.precision_prediction.isnot(None)
        ).scalar()

        return {
            "success": True,
            "total_validé": total_validé,
            "vendus": vendus,
            "pas_vendus": pas_vendus,
            "balance_classes": round(vendus / max(total_validé, 1), 3),
            "deja_utilisé_training": deja_utilisé,
            "nouveau_disponible": nouveau_disponible,
            "pret_entrainement": nouveau_disponible >= 50,
            "sources_validation": {src: count for src, count in by_source},
            "precision_moyenne": round(avg_precision, 3) if avg_precision else None
        }
    finally:
        db.close()

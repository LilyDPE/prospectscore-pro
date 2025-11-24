#!/usr/bin/env python3
"""
Script de migration vers PropensityPredictorV2

Recalcule tous les scores de propension avec la nouvelle version améliorée.

Usage:
    python migrate_to_v2.py [--score-min 0] [--batch-size 500] [--dry-run]

Options:
    --score-min: Score minimum des transactions à analyser (défaut: 0 = toutes)
    --batch-size: Taille des lots pour le traitement (défaut: 500)
    --dry-run: Test sans modification de la BDD
"""

import sys
import os
from pathlib import Path

# Ajouter le répertoire parent au PYTHONPATH
backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

import argparse
import logging
from datetime import datetime
from database import SessionLocal
from services.propensity_predictor_v2 import PropensityToSellPredictorV2
from models.dvf import TransactionDVF
from sqlalchemy import func

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'migration_v2_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def analyze_differences(db: SessionLocal, score_min: int = 40):
    """
    Analyse les différences entre V1 et V2 sur un échantillon
    """
    logger.info("\n" + "="*80)
    logger.info("📊 ANALYSE DES DIFFÉRENCES V1 vs V2")
    logger.info("="*80)

    # Récupérer un échantillon de transactions
    transactions = db.query(TransactionDVF).filter(
        TransactionDVF.score >= score_min,
        TransactionDVF.propensity_score > 0  # Déjà analysé en V1
    ).limit(100).all()

    if not transactions:
        logger.warning("Aucune transaction avec score V1 trouvée")
        return

    predictor_v2 = PropensityToSellPredictorV2(db)

    differences = {
        'ameliorations': 0,
        'degradations': 0,
        'identiques': 0,
        'changement_priorite': 0,
        'max_diff': 0,
        'examples': []
    }

    for trans in transactions[:20]:  # Analyser 20 transactions
        score_v1 = trans.propensity_score or 0
        result_v2 = predictor_v2.calculate_propensity_score(trans)
        score_v2 = result_v2['propensity_score']

        diff = score_v2 - score_v1

        if abs(diff) > abs(differences['max_diff']):
            differences['max_diff'] = diff

        if diff > 5:
            differences['ameliorations'] += 1
        elif diff < -5:
            differences['degradations'] += 1
        else:
            differences['identiques'] += 1

        # Détection changement de priorité
        priority_v1 = trans.contact_priority
        priority_v2 = result_v2['priority']

        if priority_v1 != priority_v2:
            differences['changement_priorite'] += 1

        # Garder quelques exemples significatifs
        if len(differences['examples']) < 5 and abs(diff) > 10:
            differences['examples'].append({
                'adresse': trans.adresse,
                'score_v1': score_v1,
                'score_v2': score_v2,
                'diff': diff,
                'priority_v1': priority_v1,
                'priority_v2': priority_v2,
                'nouveaux_signaux': len(result_v2['raisons']) - len(trans.propensity_raisons or [])
            })

    # Afficher les résultats
    logger.info(f"\n📈 Résultats sur {len(transactions[:20])} transactions :")
    logger.info(f"  • Améliorations (score +5) : {differences['ameliorations']}")
    logger.info(f"  • Dégradations (score -5) : {differences['degradations']}")
    logger.info(f"  • Identiques (±5) : {differences['identiques']}")
    logger.info(f"  • Changements de priorité : {differences['changement_priorite']}")
    logger.info(f"  • Différence max : {differences['max_diff']:+d}")

    if differences['examples']:
        logger.info("\n🔍 Exemples de changements significatifs :")
        for ex in differences['examples']:
            logger.info(f"\n  {ex['adresse']}")
            logger.info(f"    V1: {ex['score_v1']} ({ex['priority_v1']}) → V2: {ex['score_v2']} ({ex['priority_v2']})")
            logger.info(f"    Diff: {ex['diff']:+d} points")
            logger.info(f"    Nouveaux signaux: {ex['nouveaux_signaux']:+d}")

    logger.info("\n" + "="*80 + "\n")

def migrate_to_v2(score_min: int = 0, batch_size: int = 500, dry_run: bool = False):
    """
    Migre tous les scores vers la version 2
    """
    db = SessionLocal()

    try:
        # Statistiques initiales
        total_transactions = db.query(func.count(TransactionDVF.id)).filter(
            TransactionDVF.score >= score_min
        ).scalar()

        logger.info("\n" + "="*80)
        logger.info("🚀 MIGRATION VERS PROPENSITY PREDICTOR V2")
        logger.info("="*80)
        logger.info(f"Transactions à analyser : {total_transactions}")
        logger.info(f"Score minimum : {score_min}")
        logger.info(f"Taille des lots : {batch_size}")
        logger.info(f"Mode : {'DRY-RUN (aucune modification)' if dry_run else 'PRODUCTION'}")
        logger.info("="*80 + "\n")

        if dry_run:
            logger.info("⚠️  MODE DRY-RUN : Analyse uniquement, pas de modification\n")

        # Analyser les différences sur un échantillon
        if not dry_run:
            analyze_differences(db, score_min)

        # Créer le prédicteur V2
        predictor = PropensityToSellPredictorV2(db)

        # Traitement par lots
        offset = 0
        total_analyzed = 0
        total_hot = 0
        total_urgent = 0

        while offset < total_transactions:
            logger.info(f"\n📦 Lot {offset // batch_size + 1} : {offset} à {min(offset + batch_size, total_transactions)}")

            transactions = db.query(TransactionDVF).filter(
                TransactionDVF.score >= score_min
            ).order_by(TransactionDVF.score.desc()).offset(offset).limit(batch_size).all()

            if not transactions:
                break

            batch_hot = 0
            batch_urgent = 0

            for trans in transactions:
                result = predictor.calculate_propensity_score(trans)

                if not dry_run:
                    # Mettre à jour la transaction
                    trans.propensity_score = result['propensity_score']
                    trans.propensity_raisons = result['raisons']
                    trans.propensity_timeframe = result['timeframe']
                    trans.contact_priority = result['priority']
                    trans.cohorte_vente_active = result['cohorte_active']
                    trans.contraintes_convergentes = result['contraintes_count']
                    trans.pic_marche_local = result['pic_marche']
                    trans.derniere_analyse_propension = datetime.now()

                total_analyzed += 1

                if result['propensity_score'] >= 75:
                    batch_hot += 1
                    total_hot += 1
                    if result['priority'] == 'URGENT':
                        batch_urgent += 1
                        total_urgent += 1

                    logger.info(
                        f"  🔥 [{result['propensity_score']}] {trans.adresse} - "
                        f"{result['timeframe']} ({len(result['raisons'])} signaux)"
                    )

            if not dry_run:
                db.commit()
                logger.info(f"  ✅ Lot sauvegardé : {len(transactions)} transactions")
            else:
                logger.info(f"  ⚠️  Lot analysé (non sauvegardé) : {len(transactions)} transactions")

            logger.info(f"  📊 HOT dans ce lot : {batch_hot} | URGENT : {batch_urgent}")

            offset += batch_size

            # Progression
            progress = (total_analyzed / total_transactions * 100)
            logger.info(f"  🎯 Progression : {progress:.1f}% ({total_analyzed}/{total_transactions})")

        # Statistiques finales
        logger.info("\n" + "="*80)
        logger.info("✅ MIGRATION TERMINÉE")
        logger.info("="*80)
        logger.info(f"Total analysé : {total_analyzed}")
        logger.info(f"HOT (≥75) : {total_hot} ({total_hot/total_analyzed*100:.1f}%)")
        logger.info(f"URGENT (≥90) : {total_urgent} ({total_urgent/total_analyzed*100:.1f}%)")

        if dry_run:
            logger.info("\n⚠️  MODE DRY-RUN : Aucune modification en base")
            logger.info("   Relancez sans --dry-run pour appliquer les changements")
        else:
            logger.info("\n🎉 Tous les scores ont été mis à jour avec la V2 !")

        logger.info("="*80 + "\n")

    except Exception as e:
        logger.error(f"\n❌ ERREUR : {e}")
        if not dry_run:
            db.rollback()
        raise
    finally:
        db.close()

def main():
    parser = argparse.ArgumentParser(
        description="Migration vers PropensityPredictorV2",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--score-min',
        type=int,
        default=0,
        help='Score minimum des transactions à analyser (défaut: 0)'
    )

    parser.add_argument(
        '--batch-size',
        type=int,
        default=500,
        help='Taille des lots pour le traitement (défaut: 500)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Mode test : analyse sans modification de la BDD'
    )

    args = parser.parse_args()

    # Confirmation en mode production
    if not args.dry_run:
        logger.warning("\n⚠️  MODE PRODUCTION : Les scores seront modifiés en base")
        response = input("Confirmer ? (oui/non) : ")
        if response.lower() not in ['oui', 'yes', 'y', 'o']:
            logger.info("Migration annulée")
            return

    migrate_to_v2(
        score_min=args.score_min,
        batch_size=args.batch_size,
        dry_run=args.dry_run
    )

if __name__ == "__main__":
    main()

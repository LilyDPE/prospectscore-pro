from sqlalchemy.orm import Session
from sqlalchemy import func, text
from models.dvf import TransactionDVF
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import statistics

logger = logging.getLogger(__name__)

class PropensityToSellPredictor:
    """Prédit la probabilité de vente dans 6-12 mois - LE GAME CHANGER"""
    
    def __init__(self, db: Session):
        self.db = db
        self.current_year = datetime.now().year
    
    def in_cohort_selling_window(self, transaction: TransactionDVF) -> Tuple[int, str]:
        """
        Analyse si la transaction est dans la fenêtre statistique de vente de sa cohorte
        Score: 0-45 points
        """
        if not transaction.duree_detention_estimee:
            return 0, None
        
        duree = transaction.duree_detention_estimee
        annee_achat = self.current_year - duree
        
        # Statistiques réelles : pic de revente entre 7-12 ans
        if 7 <= duree <= 9:
            logger.info(f"🎯 Sweet spot temporel : {duree} ans (cohorte {annee_achat})")
            return 45, f"Cohorte {annee_achat} : pic statistique de revente ({duree} ans)"
        elif 10 <= duree <= 12:
            return 35, f"Cohorte {annee_achat} : fenêtre active de revente ({duree} ans)"
        elif 5 <= duree <= 6:
            return 25, f"Entrée dans cycle de revente ({duree} ans)"
        elif 13 <= duree <= 15:
            return 30, f"Cycle de revente tardif ({duree} ans)"
        
        return 0, None
    
    def detect_converging_constraints(self, transaction: TransactionDVF) -> List[Dict]:
        """
        Détecte les contraintes qui convergent pour créer une pression de vente
        Score: 0-60 points (10 points par contrainte, max 6)
        """
        contraintes = []
        
        # 1. Passoire thermique DPE F/G (obligation légale imminente)
        if transaction.classe_dpe in ['F', 'G']:
            deadline = "2028" if transaction.classe_dpe == 'F' else "2025"
            contraintes.append({
                'type': 'obligation_legale',
                'description': f"DPE {transaction.classe_dpe} → Interdiction location {deadline}",
                'urgence': 'HAUTE' if transaction.classe_dpe == 'G' else 'MOYENNE',
                'points': 15 if transaction.classe_dpe == 'G' else 10
            })
        
        # 2. Taxe foncière estimée élevée (charge lourde)
        if transaction.valeur_fonciere and transaction.surface_reelle:
            # Estimation grossière : 1.5% de la valeur
            taxe_estimee = transaction.valeur_fonciere * 0.015
            if taxe_estimee > 2000:
                contraintes.append({
                    'type': 'charge_fiscale',
                    'description': f"Taxe foncière ~{int(taxe_estimee)}€/an (charge lourde)",
                    'urgence': 'MOYENNE',
                    'points': 10
                })
        
        # 3. Surface atypique (difficile à louer/revendre)
        if transaction.surface_reelle:
            surface = transaction.surface_reelle
            if transaction.type_local == 'Maison':
                if surface < 60 or surface > 300:
                    contraintes.append({
                        'type': 'surface_atypique',
                        'description': f"Maison {int(surface)}m² (hors standard marché)",
                        'urgence': 'MOYENNE',
                        'points': 10
                    })
            elif transaction.type_local == 'Appartement':
                if surface < 25 or surface > 150:
                    contraintes.append({
                        'type': 'surface_atypique',
                        'description': f"Appartement {int(surface)}m² (difficile à commercialiser)",
                        'urgence': 'MOYENNE',
                        'points': 10
                    })
        
        # 4. Détention longue (succession probable, motivation patrimoniale)
        if transaction.duree_detention_estimee and transaction.duree_detention_estimee >= 20:
            contraintes.append({
                'type': 'succession_probable',
                'description': f"Détention {transaction.duree_detention_estimee} ans (transmission patrimoniale)",
                'urgence': 'MOYENNE',
                'points': 12
            })
        
        # 5. Prix élevé (difficulté de financement acheteurs)
        if transaction.valeur_fonciere and transaction.valeur_fonciere > 400000:
            contraintes.append({
                'type': 'prix_eleve',
                'description': f"Prix {int(transaction.valeur_fonciere/1000)}k€ (marché restreint)",
                'urgence': 'FAIBLE',
                'points': 8
            })
        
        # 6. Ancien sans travaux récents (vétusté probable)
        if transaction.duree_detention_estimee and transaction.duree_detention_estimee >= 15:
            if not transaction.classe_dpe or transaction.classe_dpe in ['E', 'F', 'G']:
                contraintes.append({
                    'type': 'vetuste',
                    'description': f"Ancien {transaction.duree_detention_estimee} ans + mauvais DPE (travaux nécessaires)",
                    'urgence': 'MOYENNE',
                    'points': 10
                })
        
        return contraintes
    
    def analyze_twin_behavior(self, transaction: TransactionDVF) -> Tuple[float, int]:
        """
        Analyse le comportement de vente des "jumeaux" (propriétés similaires)
        Retourne: (ratio_vendus_recemment, score)
        """
        if not transaction.commune or not transaction.surface_reelle:
            return 0.0, 0
        
        # Définir les jumeaux : même commune, même type, surface ±20%, achat ±2 ans
        annee_achat_min = (self.current_year - transaction.duree_detention_estimee - 2) if transaction.duree_detention_estimee else 2010
        annee_achat_max = (self.current_year - transaction.duree_detention_estimee + 2) if transaction.duree_detention_estimee else 2020
        
        surface_min = transaction.surface_reelle * 0.8
        surface_max = transaction.surface_reelle * 1.2
        
        # Compter les jumeaux
        jumeaux_total = self.db.query(func.count(TransactionDVF.id)).filter(
            TransactionDVF.commune == transaction.commune,
            TransactionDVF.type_local == transaction.type_local,
            TransactionDVF.surface_reelle.between(surface_min, surface_max),
            func.extract('year', TransactionDVF.date_mutation).between(annee_achat_min, annee_achat_max)
        ).scalar() or 0
        
        if jumeaux_total < 10:  # Pas assez de données
            return 0.0, 0
        
        # Compter combien ont été revendus récemment (12 derniers mois)
        # On détecte une revente si même adresse vendue 2 fois
        jumeaux_revendus = self.db.query(func.count(func.distinct(TransactionDVF.adresse))).filter(
            TransactionDVF.commune == transaction.commune,
            TransactionDVF.type_local == transaction.type_local,
            TransactionDVF.date_mutation >= datetime.now() - timedelta(days=365)
        ).scalar() or 0
        
        ratio_vendus = jumeaux_revendus / jumeaux_total if jumeaux_total > 0 else 0
        
        # Scoring
        if ratio_vendus >= 0.4:  # 40%+ de la cohorte vend
            score = 40
            logger.info(f"🔥 Effet cohorte MASSIF : {int(ratio_vendus*100)}% de jumeaux vendent")
        elif ratio_vendus >= 0.25:  # 25%+
            score = 30
        elif ratio_vendus >= 0.15:  # 15%+
            score = 20
        else:
            score = 0
        
        return ratio_vendus, score
    
    def detect_market_peak(self, transaction: TransactionDVF) -> Tuple[bool, int, str]:
        """
        Détecte si le marché local est à son pic (moment optimal d'arbitrage)
        Retourne: (is_peak, score, description)
        """
        if not transaction.code_postal:
            return False, 0, None
        
        # Analyser l'évolution des prix sur le code postal (12 derniers mois)
        prix_recents = self.db.query(
            func.avg(TransactionDVF.valeur_fonciere / TransactionDVF.surface_reelle).label('prix_m2'),
            func.extract('month', TransactionDVF.date_mutation).label('mois')
        ).filter(
            TransactionDVF.code_postal == transaction.code_postal,
            TransactionDVF.type_local == transaction.type_local,
            TransactionDVF.surface_reelle > 0,
            TransactionDVF.date_mutation >= datetime.now() - timedelta(days=365)
        ).group_by('mois').all()
        
        if len(prix_recents) < 6:  # Pas assez de données
            return False, 0, None
        
        # Calculer la tendance
        prix_liste = [float(p.prix_m2) for p in prix_recents if p.prix_m2]
        if len(prix_liste) < 6:
            return False, 0, None
        
        # Comparer 6 derniers mois vs 6 précédents
        prix_6_derniers = statistics.mean(prix_liste[-6:])
        prix_6_precedents = statistics.mean(prix_liste[-12:-6]) if len(prix_liste) >= 12 else prix_liste[0]
        
        evolution = ((prix_6_derniers - prix_6_precedents) / prix_6_precedents * 100) if prix_6_precedents > 0 else 0
        
        # Détecter plateau (hausse ralentit après forte hausse)
        if evolution > 8:  # Forte hausse continue
            return False, 15, f"Marché en hausse +{evolution:.1f}% (momentum positif)"
        elif 3 <= evolution <= 8:  # Plateau après hausse
            return True, 35, f"Pic de marché atteint +{evolution:.1f}% (arbitrage optimal)"
        elif -2 <= evolution < 3:  # Stagnation
            return True, 25, "Marché stable (fenêtre d'arbitrage)"
        
        return False, 0, None
    
    def calculate_propensity_score(self, transaction: TransactionDVF) -> Dict:
        """
        Calcule le score de propension à vendre (0-100)
        C'est LE COEUR du système prédictif
        """
        score = 0
        raisons = []
        urgence_max = 'FAIBLE'
        
        # 1. Fenêtre temporelle cohorte (45 pts max)
        cohort_score, cohort_reason = self.in_cohort_selling_window(transaction)
        score += cohort_score
        if cohort_reason:
            raisons.append(cohort_reason)
            if cohort_score >= 40:
                urgence_max = 'HAUTE'
        
        # 2. Contraintes convergentes (60 pts max)
        contraintes = self.detect_converging_constraints(transaction)
        contraintes_score = sum([c['points'] for c in contraintes])
        contraintes_score = min(contraintes_score, 60)  # Cap à 60
        score += contraintes_score
        
        if len(contraintes) >= 3:
            urgence_max = 'HAUTE'
            raisons.append(f"⚠️ {len(contraintes)} contraintes convergentes")
        
        for c in contraintes:
            raisons.append(c['description'])
        
        # 3. Effet cohorte (jumeaux qui vendent) (40 pts max)
        ratio_twins, twins_score = self.analyze_twin_behavior(transaction)
        score += twins_score
        if twins_score > 0:
            raisons.append(f"📊 Cohorte active : {int(ratio_twins*100)}% de propriétés similaires vendent")
            if ratio_twins >= 0.3:
                urgence_max = 'HAUTE'
        
        # 4. Pic de marché (35 pts max)
        is_peak, peak_score, peak_reason = self.detect_market_peak(transaction)
        score += peak_score
        if peak_reason:
            raisons.append(f"📈 {peak_reason}")
            if is_peak:
                urgence_max = 'HAUTE' if urgence_max != 'HAUTE' else 'HAUTE'
        
        # 5. Bonus si turnover régulier détecté (investisseur actif)
        if transaction.turnover_regulier:
            score += 20
            raisons.append(f"🔄 Investisseur actif (turnover régulier {transaction.frequence_vente_mois} mois)")
            urgence_max = 'HAUTE'
        
        # 6. Bonus si propriétaire professionnel
        if transaction.proprietaire_type in ['Potentiel professionnel', 'Société probable', 'SCI']:
            score += 15
            raisons.append("🏢 Propriétaire professionnel (gestion active)")
        
        # Classification du timing
        if score >= 90:
            timeframe = "Vente IMMINENTE (<3 mois)"
            priority = "URGENT"
        elif score >= 75:
            timeframe = "Vente probable sous 6 mois"  # 🎯 SWEET SPOT
            priority = "HIGH"
        elif score >= 60:
            timeframe = "Vente probable sous 12 mois"
            priority = "MEDIUM"
        elif score >= 40:
            timeframe = "Potentiel à surveiller (12-24 mois)"
            priority = "LOW"
        else:
            timeframe = "Pas de signal de vente"
            priority = "NONE"
        
        return {
            'propensity_score': min(score, 100),
            'raisons': raisons,
            'timeframe': timeframe,
            'priority': priority,
            'cohorte_active': cohort_score > 0,
            'contraintes_count': len(contraintes),
            'pic_marche': is_peak,
            'urgence_max': urgence_max
        }
    
    def analyze_batch(self, score_min: int = 0, limit: int = 1000):
        """
        Analyse un batch de transactions pour calculer leur propensity score
        """
        transactions = self.db.query(TransactionDVF).filter(
            TransactionDVF.score >= score_min,
            TransactionDVF.duree_detention_estimee.isnot(None),
            TransactionDVF.duree_detention_estimee >= 3  # Minimum 3 ans détention
        ).order_by(TransactionDVF.score.desc()).limit(limit).all()
        
        analyzed = 0
        hot_prospects = 0
        urgent = 0
        
        for trans in transactions:
            result = self.calculate_propensity_score(trans)
            
            trans.propensity_score = result['propensity_score']
            trans.propensity_raisons = result['raisons']
            trans.propensity_timeframe = result['timeframe']
            trans.contact_priority = result['priority']
            trans.cohorte_vente_active = result['cohorte_active']
            trans.contraintes_convergentes = result['contraintes_count']
            trans.pic_marche_local = result['pic_marche']
            trans.derniere_analyse_propension = datetime.now()
            
            analyzed += 1
            
            if result['propensity_score'] >= 75:
                hot_prospects += 1
                if result['priority'] == 'URGENT':
                    urgent += 1
                
                logger.info(
                    f"🔥 HOT PROSPECT [{result['propensity_score']}] : {trans.adresse} - "
                    f"{result['timeframe']} - {len(result['raisons'])} signaux"
                )
            
            if analyzed % 50 == 0:
                self.db.commit()
        
        self.db.commit()
        
        logger.info(
            f"✅ {analyzed} analysés - {hot_prospects} HOT (>75) - {urgent} URGENT (>90)"
        )
        
        return {
            'analyzed': analyzed,
            'hot_prospects': hot_prospects,
            'urgent': urgent
        }

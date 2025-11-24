from sqlalchemy.orm import Session
from sqlalchemy import func, text
from models.dvf import TransactionDVF
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
import statistics

logger = logging.getLogger(__name__)

class PropensityToSellPredictorV2:
    """
    Version 2 - Prédicteur de propension à vendre AMÉLIORÉ

    Améliorations :
    - Détection des VRAIES reventes (bug corrigé)
    - Calcul dynamique de la durée de détention
    - Signaux de liquidité du marché
    - Analyse de rentabilité locative (investisseurs)
    - Détection de succession
    - Saisonnalité
    - Scoring normalisé sur 100 points
    """

    def __init__(self, db: Session):
        self.db = db
        self.current_year = datetime.now().year
        self.current_month = datetime.now().month

    def calculate_holding_duration(self, transaction: TransactionDVF) -> Optional[int]:
        """
        Calcule la durée de détention RÉELLE en détectant la vente précédente
        Retourne: nombre d'années de détention
        """
        if not transaction.adresse or not transaction.date_mutation:
            return None

        # Trouver la vente précédente de cette adresse
        vente_precedente = self.db.query(TransactionDVF).filter(
            TransactionDVF.adresse == transaction.adresse,
            TransactionDVF.type_local == transaction.type_local,
            TransactionDVF.date_mutation < transaction.date_mutation
        ).order_by(TransactionDVF.date_mutation.desc()).first()

        if not vente_precedente:
            # Aucune vente antérieure dans DVF (base depuis 2014)
            # Estimer : cap à 10 ans par défaut
            annees_depuis_debut_dvf = (transaction.date_mutation.year - 2014)
            return min(annees_depuis_debut_dvf, 10)

        # Calculer durée exacte
        duree_jours = (transaction.date_mutation - vente_precedente.date_mutation).days
        duree_annees = duree_jours // 365

        logger.info(
            f"🔍 Détention calculée : {duree_annees} ans "
            f"({vente_precedente.date_mutation} → {transaction.date_mutation})"
        )

        return duree_annees

    def detect_real_resales(self, transaction: TransactionDVF) -> Tuple[int, List[Dict], bool]:
        """
        Détecte les VRAIES reventes (même adresse vendue plusieurs fois)
        Retourne: (nombre_reventes, historique, turnover_rapide)
        """
        if not transaction.adresse:
            return 0, [], False

        # Rechercher toutes les ventes de cette adresse
        ventes_historique = self.db.query(TransactionDVF).filter(
            TransactionDVF.adresse == transaction.adresse,
            TransactionDVF.type_local == transaction.type_local
        ).order_by(TransactionDVF.date_mutation).all()

        if len(ventes_historique) <= 1:
            return 0, [], False

        # Calculer historique des reventes
        historique = []
        turnover_rapide = False

        for i in range(1, len(ventes_historique)):
            vente_prev = ventes_historique[i-1]
            vente_curr = ventes_historique[i]

            duree_jours = (vente_curr.date_mutation - vente_prev.date_mutation).days
            duree_annees = duree_jours // 365

            if vente_prev.valeur_fonciere and vente_prev.valeur_fonciere > 0:
                plus_value = vente_curr.valeur_fonciere - vente_prev.valeur_fonciere
                taux_plus_value = (plus_value / vente_prev.valeur_fonciere * 100)
            else:
                plus_value = 0
                taux_plus_value = 0

            historique.append({
                'date_achat': str(vente_prev.date_mutation) if vente_prev.date_mutation else None,
                'date_vente': str(vente_curr.date_mutation) if vente_curr.date_mutation else None,
                'duree_detention': duree_annees,
                'prix_achat': vente_prev.valeur_fonciere,
                'prix_vente': vente_curr.valeur_fonciere,
                'plus_value': plus_value,
                'taux_plus_value': round(taux_plus_value, 1)
            })

            # Turnover rapide si < 5 ans
            if duree_annees < 5:
                turnover_rapide = True

        nb_reventes = len(historique)

        if nb_reventes > 0:
            logger.info(
                f"🔄 {nb_reventes} revente(s) détectée(s) - "
                f"Turnover {'RAPIDE' if turnover_rapide else 'NORMAL'}"
            )

        return nb_reventes, historique, turnover_rapide

    def in_cohort_selling_window(self, duree_detention: int) -> Tuple[int, str]:
        """
        Analyse si dans la fenêtre statistique de vente (7-12 ans)
        Score: 0-45 points
        """
        if not duree_detention:
            return 0, None

        annee_achat = self.current_year - duree_detention

        # Sweet spot : 7-12 ans
        if 7 <= duree_detention <= 9:
            logger.info(f"🎯 Sweet spot temporel : {duree_detention} ans (cohorte {annee_achat})")
            return 45, f"Cohorte {annee_achat} : pic statistique de revente ({duree_detention} ans)"
        elif 10 <= duree_detention <= 12:
            return 35, f"Cohorte {annee_achat} : fenêtre active de revente ({duree_detention} ans)"
        elif 5 <= duree_detention <= 6:
            return 25, f"Entrée dans cycle de revente ({duree_detention} ans)"
        elif 13 <= duree_detention <= 15:
            return 30, f"Cycle de revente tardif ({duree_detention} ans)"

        return 0, None

    def detect_converging_constraints(self, transaction: TransactionDVF, duree_detention: int) -> List[Dict]:
        """
        Détecte les contraintes qui créent une pression de vente
        Score: 0-60 points (10 points par contrainte, max 6)
        """
        contraintes = []

        # 1. Passoire thermique DPE F/G
        if transaction.classe_dpe in ['F', 'G']:
            deadline = "2028" if transaction.classe_dpe == 'F' else "2025"
            contraintes.append({
                'type': 'obligation_legale',
                'description': f"DPE {transaction.classe_dpe} → Interdiction location {deadline}",
                'urgence': 'HAUTE' if transaction.classe_dpe == 'G' else 'MOYENNE',
                'points': 15 if transaction.classe_dpe == 'G' else 10
            })

        # 2. Taxe foncière élevée
        if transaction.valeur_fonciere and transaction.surface_reelle:
            taxe_estimee = transaction.valeur_fonciere * 0.015
            if taxe_estimee > 2000:
                contraintes.append({
                    'type': 'charge_fiscale',
                    'description': f"Taxe foncière ~{int(taxe_estimee)}€/an (charge lourde)",
                    'urgence': 'MOYENNE',
                    'points': 10
                })

        # 3. Surface atypique
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

        # 4. Détention longue (succession probable)
        if duree_detention and duree_detention >= 20:
            contraintes.append({
                'type': 'succession_probable',
                'description': f"Détention {duree_detention} ans (transmission patrimoniale)",
                'urgence': 'MOYENNE',
                'points': 12
            })

        # 5. Prix élevé
        if transaction.valeur_fonciere and transaction.valeur_fonciere > 400000:
            contraintes.append({
                'type': 'prix_eleve',
                'description': f"Prix {int(transaction.valeur_fonciere/1000)}k€ (marché restreint)",
                'urgence': 'FAIBLE',
                'points': 8
            })

        # 6. Vétusté probable
        if duree_detention and duree_detention >= 15:
            if not transaction.classe_dpe or transaction.classe_dpe in ['E', 'F', 'G']:
                contraintes.append({
                    'type': 'vetuste',
                    'description': f"Ancien {duree_detention} ans + mauvais DPE (travaux nécessaires)",
                    'urgence': 'MOYENNE',
                    'points': 10
                })

        return contraintes

    def analyze_twin_behavior(self, transaction: TransactionDVF, duree_detention: int) -> Tuple[float, int]:
        """
        Analyse le comportement de vente des "jumeaux" (propriétés similaires)
        VERSION AMÉLIORÉE : détecte les vraies reventes
        Retourne: (ratio_vendus_recemment, score)
        """
        if not transaction.commune or not transaction.surface_reelle or not duree_detention:
            return 0.0, 0

        # Définir les jumeaux : même commune, même type, surface ±20%, achat ±2 ans
        annee_achat_min = self.current_year - duree_detention - 2
        annee_achat_max = self.current_year - duree_detention + 2

        surface_min = transaction.surface_reelle * 0.8
        surface_max = transaction.surface_reelle * 1.2

        # Compter les jumeaux (biens similaires achetés dans la même période)
        jumeaux_query = self.db.query(TransactionDVF).filter(
            TransactionDVF.commune == transaction.commune,
            TransactionDVF.type_local == transaction.type_local,
            TransactionDVF.surface_reelle.between(surface_min, surface_max),
            func.extract('year', TransactionDVF.date_mutation).between(annee_achat_min, annee_achat_max)
        )

        jumeaux_total = jumeaux_query.count()

        if jumeaux_total < 10:  # Pas assez de données
            return 0.0, 0

        # Compter combien ont été REVENDUS (même adresse, 2 ventes+)
        # On cherche les adresses qui apparaissent plusieurs fois
        reventes_query = self.db.query(
            TransactionDVF.adresse,
            func.count(TransactionDVF.id).label('nb_ventes')
        ).filter(
            TransactionDVF.commune == transaction.commune,
            TransactionDVF.type_local == transaction.type_local
        ).group_by(TransactionDVF.adresse).having(
            func.count(TransactionDVF.id) >= 2
        )

        # Parmi ces reventes, combien sont récentes (12 derniers mois)
        adresses_revendues = [r.adresse for r in reventes_query.all()]

        if not adresses_revendues:
            return 0.0, 0

        reventes_recentes = self.db.query(func.count(func.distinct(TransactionDVF.adresse))).filter(
            TransactionDVF.adresse.in_(adresses_revendues),
            TransactionDVF.commune == transaction.commune,
            TransactionDVF.type_local == transaction.type_local,
            TransactionDVF.date_mutation >= datetime.now() - timedelta(days=365)
        ).scalar() or 0

        ratio_vendus = reventes_recentes / jumeaux_total if jumeaux_total > 0 else 0

        # Scoring
        if ratio_vendus >= 0.4:  # 40%+ de la cohorte vend
            score = 40
            logger.info(f"🔥 Effet cohorte MASSIF : {int(ratio_vendus*100)}% de jumeaux revendus")
        elif ratio_vendus >= 0.25:  # 25%+
            score = 30
            logger.info(f"📊 Effet cohorte FORT : {int(ratio_vendus*100)}% de jumeaux revendus")
        elif ratio_vendus >= 0.15:  # 15%+
            score = 20
        elif ratio_vendus >= 0.05:  # 5%+
            score = 10
        else:
            score = 0

        return ratio_vendus, score

    def detect_market_peak(self, transaction: TransactionDVF) -> Tuple[bool, int, str]:
        """
        Détecte si le marché local est à son pic
        Retourne: (is_peak, score, description)
        """
        if not transaction.code_postal:
            return False, 0, None

        # Analyser évolution des prix sur 12 mois
        prix_recents = self.db.query(
            func.avg(TransactionDVF.valeur_fonciere / TransactionDVF.surface_reelle).label('prix_m2'),
            func.extract('month', TransactionDVF.date_mutation).label('mois')
        ).filter(
            TransactionDVF.code_postal == transaction.code_postal,
            TransactionDVF.type_local == transaction.type_local,
            TransactionDVF.surface_reelle > 0,
            TransactionDVF.date_mutation >= datetime.now() - timedelta(days=365)
        ).group_by('mois').all()

        if len(prix_recents) < 6:
            return False, 0, None

        prix_liste = [float(p.prix_m2) for p in prix_recents if p.prix_m2]
        if len(prix_liste) < 6:
            return False, 0, None

        # Comparer 6 derniers mois vs 6 précédents
        prix_6_derniers = statistics.mean(prix_liste[-6:])
        prix_6_precedents = statistics.mean(prix_liste[-12:-6]) if len(prix_liste) >= 12 else prix_liste[0]

        evolution = ((prix_6_derniers - prix_6_precedents) / prix_6_precedents * 100) if prix_6_precedents > 0 else 0

        # Scoring
        if evolution > 8:
            return False, 15, f"Marché en hausse +{evolution:.1f}% (momentum positif)"
        elif 3 <= evolution <= 8:
            return True, 35, f"Pic de marché atteint +{evolution:.1f}% (arbitrage optimal)"
        elif -2 <= evolution < 3:
            return True, 25, "Marché stable (fenêtre d'arbitrage)"

        return False, 0, None

    def analyze_market_liquidity(self, transaction: TransactionDVF) -> Tuple[int, str]:
        """
        🆕 Analyse la liquidité du marché local = facilité de vendre
        Retourne: (score, description)
        """
        if not transaction.code_postal:
            return 0, None

        # Volume de transactions sur 12 mois
        volume_12m = self.db.query(func.count(TransactionDVF.id)).filter(
            TransactionDVF.code_postal == transaction.code_postal,
            TransactionDVF.type_local == transaction.type_local,
            TransactionDVF.date_mutation >= datetime.now() - timedelta(days=365)
        ).scalar() or 0

        # Volume sur 3 derniers mois
        volume_3m = self.db.query(func.count(TransactionDVF.id)).filter(
            TransactionDVF.code_postal == transaction.code_postal,
            TransactionDVF.type_local == transaction.type_local,
            TransactionDVF.date_mutation >= datetime.now() - timedelta(days=90)
        ).scalar() or 0

        if volume_12m == 0:
            return 0, "Marché inactif (pas de données)"

        # Accélération du marché
        ratio_acceleration = (volume_3m * 4) / volume_12m

        # Scoring
        score = 0
        desc = ""

        if ratio_acceleration > 1.3:
            score = 30
            desc = f"Marché en accélération +{int((ratio_acceleration-1)*100)}% (liquidité forte)"
        elif ratio_acceleration > 1.1:
            score = 20
            desc = f"Marché dynamique +{int((ratio_acceleration-1)*100)}% (bonne liquidité)"
        elif ratio_acceleration > 0.9:
            score = 10
            desc = "Marché stable (liquidité normale)"
        else:
            score = 5
            desc = f"Marché ralenti -{int((1-ratio_acceleration)*100)}% (liquidité faible)"

        # Bonus si volume élevé
        if volume_12m > 50:
            score += 10
            desc += " - Volume élevé"
        elif volume_12m > 20:
            score += 5
            desc += " - Volume correct"

        return score, desc

    def estimate_rental_yield(self, transaction: TransactionDVF) -> Tuple[Optional[float], int, Optional[str]]:
        """
        🆕 Estime le rendement locatif (investisseurs)
        Retourne: (rendement_pct, score, description)
        """
        if not transaction.valeur_fonciere or not transaction.surface_reelle:
            return None, 0, None

        # Estimation loyer selon type et localisation
        if transaction.type_local == 'Appartement':
            loyer_m2_mois = 12  # Moyenne France
            if transaction.code_postal:
                if transaction.code_postal.startswith('75'):
                    loyer_m2_mois = 28  # Paris
                elif transaction.code_postal.startswith(('92', '93', '94')):
                    loyer_m2_mois = 18  # IDF
                elif transaction.code_postal.startswith(('06', '13', '69', '33')):
                    loyer_m2_mois = 15  # Grandes villes
        else:  # Maison
            loyer_m2_mois = 10
            if transaction.code_postal:
                if transaction.code_postal.startswith('75'):
                    loyer_m2_mois = 22
                elif transaction.code_postal.startswith(('92', '93', '94')):
                    loyer_m2_mois = 15
                elif transaction.code_postal.startswith(('06', '13', '69', '33')):
                    loyer_m2_mois = 12

        loyer_annuel = transaction.surface_reelle * loyer_m2_mois * 12
        rendement = (loyer_annuel / transaction.valeur_fonciere) * 100

        # Scoring uniquement si investisseur détecté
        is_investor = transaction.proprietaire_type in ['SCI', 'Société probable', 'Potentiel professionnel']

        if not is_investor:
            return rendement, 0, None

        # Scoring selon rendement
        if rendement < 2.5:
            score = 35
            desc = f"Rendement {rendement:.1f}% (très faible → arbitrage probable)"
        elif rendement < 3.5:
            score = 25
            desc = f"Rendement {rendement:.1f}% (faible → vente envisageable)"
        elif rendement < 4.5:
            score = 10
            desc = f"Rendement {rendement:.1f}% (correct)"
        else:
            score = 0
            desc = f"Rendement {rendement:.1f}% (bon → conservation probable)"

        return rendement, score, desc

    def detect_succession_signals(self, transaction: TransactionDVF, duree_detention: int) -> Tuple[int, List[str]]:
        """
        🆕 Détecte les signaux de succession = vente probable
        Retourne: (score, liste_signaux)
        """
        score = 0
        signaux = []

        # 1. Détention très longue
        if duree_detention and duree_detention >= 25:
            score += 25
            signaux.append(f"Détention {duree_detention} ans (succession probable)")
        elif duree_detention and duree_detention >= 20:
            score += 15
            signaux.append(f"Détention {duree_detention} ans (transmission envisageable)")

        # 2. Indivision (nom composé)
        if transaction.proprietaire_nom:
            nom_upper = transaction.proprietaire_nom.upper()
            if ' ET ' in nom_upper or '&' in nom_upper:
                score += 15
                signaux.append("Indivision détectée (transmission en cours)")

        # 3. Valeur élevée (IFI)
        if transaction.valeur_fonciere and transaction.valeur_fonciere > 800000:
            score += 10
            signaux.append(f"Valeur {int(transaction.valeur_fonciere/1000)}k€ (optimisation fiscale succession)")

        # 4. Bien potentiellement vacant
        if not transaction.classe_dpe and duree_detention and duree_detention >= 10:
            score += 10
            signaux.append("Pas de DPE (bien potentiellement vacant)")

        return score, signaux

    def get_seasonal_score(self) -> Tuple[int, str]:
        """
        🆕 Ajuste le score selon la saison
        Retourne: (score, description)
        """
        mois = self.current_month

        # Printemps (mars-juin) : pic de ventes
        if mois in [3, 4, 5, 6]:
            return 15, "Saison haute (printemps) - moment optimal"

        # Automne (septembre-octobre)
        elif mois in [9, 10]:
            return 10, "Saison favorable (rentrée)"

        # Été et hiver
        elif mois in [7, 8, 12, 1]:
            return 0, "Saison creuse (vacances/fêtes)"

        # Autres mois
        else:
            return 5, "Saison normale"

    def calculate_propensity_score(self, transaction: TransactionDVF) -> Dict:
        """
        🚀 VERSION 2 - Calcul du score de propension à vendre
        Total possible : 235 points → normalisé sur 100
        """
        score_brut = 0
        raisons = []
        urgence_max = 'FAIBLE'

        # Calculer durée de détention
        duree_detention = self.calculate_holding_duration(transaction)
        if duree_detention and duree_detention != transaction.duree_detention_estimee:
            # Mettre à jour si différent
            transaction.duree_detention_estimee = duree_detention

        # Détecter les reventes
        nb_reventes, historique_ventes, turnover_rapide = self.detect_real_resales(transaction)
        if nb_reventes > 0:
            transaction.historique_ventes = historique_ventes
            transaction.turnover_regulier = (nb_reventes >= 2)
            if turnover_rapide:
                transaction.frequence_vente_mois = int(statistics.mean([h['duree_detention'] * 12 for h in historique_ventes]))

        # 1. Fenêtre temporelle cohorte (45 pts max)
        cohort_score, cohort_reason = self.in_cohort_selling_window(duree_detention)
        score_brut += cohort_score
        if cohort_reason:
            raisons.append(cohort_reason)
            if cohort_score >= 40:
                urgence_max = 'HAUTE'

        # 2. Contraintes convergentes (60 pts max)
        contraintes = self.detect_converging_constraints(transaction, duree_detention)
        contraintes_score = sum([c['points'] for c in contraintes])
        contraintes_score = min(contraintes_score, 60)
        score_brut += contraintes_score

        if len(contraintes) >= 3:
            urgence_max = 'HAUTE'
            raisons.append(f"⚠️ {len(contraintes)} contraintes convergentes")

        for c in contraintes:
            raisons.append(c['description'])

        # 3. Effet cohorte - Jumeaux (40 pts max)
        ratio_twins, twins_score = self.analyze_twin_behavior(transaction, duree_detention)
        score_brut += twins_score
        if twins_score > 0:
            raisons.append(f"📊 Cohorte active : {int(ratio_twins*100)}% de jumeaux revendus récemment")
            if ratio_twins >= 0.3:
                urgence_max = 'HAUTE'

        # 4. Pic de marché (35 pts max)
        is_peak, peak_score, peak_reason = self.detect_market_peak(transaction)
        score_brut += peak_score
        if peak_reason:
            raisons.append(f"📈 {peak_reason}")
            if is_peak and peak_score >= 30:
                urgence_max = 'HAUTE' if urgence_max != 'HAUTE' else 'HAUTE'

        # 5. 🆕 Liquidité du marché (40 pts max)
        liquidity_score, liquidity_desc = self.analyze_market_liquidity(transaction)
        score_brut += liquidity_score
        if liquidity_desc:
            raisons.append(f"💧 {liquidity_desc}")

        # 6. 🆕 Rentabilité locative (35 pts max - investisseurs uniquement)
        rendement, yield_score, yield_desc = self.estimate_rental_yield(transaction)
        score_brut += yield_score
        if yield_desc:
            raisons.append(f"💰 {yield_desc}")
            if yield_score >= 25:
                urgence_max = 'HAUTE'

        # 7. 🆕 Signaux de succession (60 pts max)
        succession_score, succession_signaux = self.detect_succession_signals(transaction, duree_detention)
        score_brut += succession_score
        if succession_signaux:
            for signal in succession_signaux:
                raisons.append(f"👴 {signal}")
            if succession_score >= 30:
                urgence_max = 'HAUTE'

        # 8. 🆕 Saisonnalité (15 pts max)
        seasonal_score, seasonal_desc = self.get_seasonal_score()
        score_brut += seasonal_score
        if seasonal_desc:
            raisons.append(f"📅 {seasonal_desc}")

        # 9. Bonus turnover régulier (20 pts)
        if transaction.turnover_regulier:
            score_brut += 20
            raisons.append(f"🔄 Investisseur actif ({nb_reventes} reventes)")
            if turnover_rapide:
                score_brut += 10
                raisons.append("⚡ Turnover rapide (<5 ans)")
            urgence_max = 'HAUTE'

        # 10. Bonus propriétaire professionnel (15 pts)
        if transaction.proprietaire_type in ['Potentiel professionnel', 'Société probable', 'SCI']:
            score_brut += 15
            raisons.append("🏢 Propriétaire professionnel (gestion active)")

        # Normalisation sur 100 points
        # Total possible : 235 points → on normalise
        score_normalise = min(int((score_brut / 235) * 100), 100)

        # Classification du timing
        if score_normalise >= 90:
            timeframe = "Vente IMMINENTE (<3 mois)"
            priority = "URGENT"
        elif score_normalise >= 75:
            timeframe = "Vente probable sous 6 mois"  # 🎯 SWEET SPOT
            priority = "HIGH"
        elif score_normalise >= 60:
            timeframe = "Vente probable sous 12 mois"
            priority = "MEDIUM"
        elif score_normalise >= 40:
            timeframe = "Potentiel à surveiller (12-24 mois)"
            priority = "LOW"
        else:
            timeframe = "Pas de signal de vente"
            priority = "NONE"

        logger.info(
            f"📊 Score calculé : {score_normalise}/100 (brut: {score_brut}/235) - "
            f"Priority: {priority} - {len(raisons)} signaux"
        )

        return {
            'propensity_score': score_normalise,
            'score_brut': score_brut,
            'raisons': raisons,
            'timeframe': timeframe,
            'priority': priority,
            'cohorte_active': cohort_score > 0,
            'contraintes_count': len(contraintes),
            'pic_marche': is_peak,
            'urgence_max': urgence_max,
            'duree_detention_calculee': duree_detention,
            'nb_reventes': nb_reventes,
            'rendement_locatif': rendement
        }

    def analyze_batch(self, score_min: int = 0, limit: int = 1000):
        """
        Analyse un batch de transactions
        """
        transactions = self.db.query(TransactionDVF).filter(
            TransactionDVF.score >= score_min
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
                logger.info(f"💾 Checkpoint : {analyzed} analysés...")

        self.db.commit()

        logger.info(
            f"✅ TERMINÉ : {analyzed} analysés - "
            f"{hot_prospects} HOT (≥75) - {urgent} URGENT (≥90)"
        )

        return {
            'analyzed': analyzed,
            'hot_prospects': hot_prospects,
            'urgent': urgent
        }

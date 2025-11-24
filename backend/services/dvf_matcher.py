"""
Service de Matching DVF - Ground Truth Validation
Détecte automatiquement les ventes confirmées en comparant les nouvelles transactions DVF
avec nos prospects suivis. C'est la "vérité terrain" pour entraîner l'IA.
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from models.dvf import TransactionDVF
from datetime import datetime, timedelta
import logging
from typing import List, Dict
import re

logger = logging.getLogger(__name__)

class DVFMatcher:
    """
    Détecte les ventes confirmées en croisant nos prédictions avec les nouvelles données DVF
    """

    def __init__(self, db: Session):
        self.db = db
        self.matches_found = 0
        self.false_positives = 0
        self.true_positives = 0

    def normalize_address(self, address: str) -> str:
        """Normalise une adresse pour le matching"""
        if not address:
            return ""

        # Minuscules
        addr = address.lower()

        # Enlever la ponctuation
        addr = re.sub(r'[^\w\s]', ' ', addr)

        # Remplacer les abréviations courantes
        replacements = {
            'rue': 'r',
            'avenue': 'av',
            'boulevard': 'bd',
            'chemin': 'ch',
            'impasse': 'imp',
            'place': 'pl',
            'route': 'rte',
            'allee': 'all',
            'cours': 'crs'
        }

        for old, new in replacements.items():
            addr = addr.replace(old, new)

        # Nettoyer les espaces multiples
        addr = ' '.join(addr.split())

        return addr

    def calculate_address_similarity(self, addr1: str, addr2: str) -> float:
        """
        Calcule un score de similarité entre 2 adresses (0-1)
        Utilise une méthode simple mais efficace
        """
        norm1 = self.normalize_address(addr1)
        norm2 = self.normalize_address(addr2)

        if not norm1 or not norm2:
            return 0.0

        # Exact match
        if norm1 == norm2:
            return 1.0

        # Token matching (mots communs)
        tokens1 = set(norm1.split())
        tokens2 = set(norm2.split())

        if not tokens1 or not tokens2:
            return 0.0

        common = tokens1.intersection(tokens2)
        total = tokens1.union(tokens2)

        # Jaccard similarity
        similarity = len(common) / len(total)

        return similarity

    def reconcile_sales(self, min_similarity: float = 0.7, lookback_months: int = 18) -> Dict:
        """
        Rapproche les transactions DVF récentes avec nos prospects suivis

        Args:
            min_similarity: Score minimum de similarité d'adresse (0-1)
            lookback_months: Période de recherche en arrière (mois)

        Returns:
            Dict avec statistiques du matching
        """
        logger.info("🕵️ Début du rapprochement DVF vs Prospects...")

        # Date limite pour chercher les ventes récentes
        cutoff_date = datetime.now() - timedelta(days=lookback_months * 30)

        # 1. Récupérer les prospects "ouverts" (avec prédiction mais pas encore validés)
        prospects = self.db.query(TransactionDVF).filter(
            and_(
                TransactionDVF.propensity_score >= 40,  # On avait prédit une vente probable
                TransactionDVF.statut_final == None,  # Pas encore validé
                TransactionDVF.derniere_analyse_propension.isnot(None),  # On a fait une prédiction
                TransactionDVF.date_mutation < cutoff_date  # Transaction "ancienne" qu'on suivait
            )
        ).all()

        logger.info(f"📊 {len(prospects)} prospects à vérifier")

        # 2. Récupérer les ventes DVF récentes (potentiellement ces mêmes biens revendus)
        recent_sales = self.db.query(TransactionDVF).filter(
            and_(
                TransactionDVF.date_mutation >= cutoff_date,  # Vente récente
                TransactionDVF.statut_final == None  # Pas encore marquée comme match
            )
        ).all()

        logger.info(f"🔍 {len(recent_sales)} ventes récentes dans DVF")

        matches = []

        # 3. Pour chaque prospect, chercher une revente dans les données récentes
        for prospect in prospects:
            for sale in recent_sales:
                # Filtres rapides d'abord
                if prospect.id == sale.id:  # Même transaction = skip
                    continue

                if prospect.commune != sale.commune:  # Commune différente = skip
                    continue

                # Matching par adresse
                similarity = self.calculate_address_similarity(
                    prospect.adresse or "",
                    sale.adresse or ""
                )

                if similarity >= min_similarity:
                    # BINGO ! C'est probablement une revente du bien qu'on suivait
                    matches.append({
                        'prospect': prospect,
                        'sale': sale,
                        'similarity': similarity
                    })

        logger.info(f"🎯 {len(matches)} correspondances trouvées")

        # 4. Marquer les ventes confirmées
        for match in matches:
            prospect = match['prospect']
            sale = match['sale']

            # Calculer le délai entre notre prédiction et la vente réelle
            delai = None
            if prospect.derniere_analyse_propension and sale.date_mutation:
                delai = (sale.date_mutation - prospect.derniere_analyse_propension.date()).days

            # Calculer la précision de notre prédiction
            precision = None
            if delai is not None:
                # Plus on est proche de notre prédiction de timeframe, meilleur le score
                # timeframe attendu : 6-12 mois = 180-365 jours
                if 180 <= delai <= 365:
                    precision = 1.0  # Parfait !
                elif 90 <= delai < 180:
                    precision = 0.8  # Un peu tôt
                elif 365 < delai <= 545:  # ~18 mois
                    precision = 0.7  # Un peu tard
                else:
                    precision = 0.5  # Assez loin

            logger.info(
                f"✅ Vente confirmée : {prospect.adresse} → {sale.adresse} "
                f"(similarité {match['similarity']:.2f}, délai {delai} jours, précision {precision})"
            )

            # Marquer le prospect original
            prospect.statut_final = 1  # Vendu confirmé
            prospect.source_validation = "DVF_API"
            prospect.date_validation = datetime.now()
            prospect.prix_vente_reel = sale.valeur_fonciere
            prospect.delai_vente_jours = delai
            prospect.precision_prediction = precision

            # Statistiques
            self.matches_found += 1
            if prospect.propensity_score >= 75:
                self.true_positives += 1  # On avait prédit HOT et c'est vendu

        # 5. Marquer les "faux positifs" (prédictions HOT mais pas de vente après 18 mois)
        old_hot_prospects = self.db.query(TransactionDVF).filter(
            and_(
                TransactionDVF.propensity_score >= 75,  # On avait prédit HOT
                TransactionDVF.statut_final == None,  # Pas validé
                TransactionDVF.derniere_analyse_propension < cutoff_date  # Ça fait + de 18 mois
            )
        ).all()

        for prospect in old_hot_prospects:
            # Pas de vente détectée après 18 mois = probablement faux positif
            prospect.statut_final = 0  # Pas vendu
            prospect.source_validation = "DVF_TIMEOUT"
            prospect.date_validation = datetime.now()
            prospect.feedback_agent = "Pas de vente détectée après 18 mois de prédiction HOT"
            self.false_positives += 1

        self.db.commit()

        result = {
            'prospects_verifies': len(prospects),
            'ventes_recentes_dvf': len(recent_sales),
            'matches_trouves': self.matches_found,
            'true_positives': self.true_positives,  # HOT et vendu
            'false_positives': self.false_positives,  # HOT mais pas vendu
            'accuracy': round(self.true_positives / max(self.true_positives + self.false_positives, 1), 3)
        }

        logger.info(
            f"📊 Rapprochement terminé : {self.matches_found} ventes confirmées, "
            f"{self.true_positives} vrais positifs, {self.false_positives} faux positifs "
            f"(accuracy: {result['accuracy']*100:.1f}%)"
        )

        return result

    def get_training_dataset(self, min_samples: int = 100) -> List[TransactionDVF]:
        """
        Récupère les transactions validées pour l'entraînement ML

        Returns:
            Liste des transactions avec statut_final validé (vendu ou pas vendu)
        """
        validated = self.db.query(TransactionDVF).filter(
            and_(
                TransactionDVF.statut_final.isnot(None),  # Statut validé
                TransactionDVF.utilisé_pour_training == False  # Pas encore utilisé
            )
        ).all()

        logger.info(f"📚 {len(validated)} échantillons validés disponibles pour training")

        if len(validated) < min_samples:
            logger.warning(
                f"⚠️ Seulement {len(validated)} échantillons validés. "
                f"Minimum recommandé : {min_samples}"
            )

        return validated


if __name__ == "__main__":
    """Test du matching DVF"""
    from database import SessionLocal

    db = SessionLocal()
    try:
        matcher = DVFMatcher(db)
        result = matcher.reconcile_sales()
        print("\n🎯 Résultats du matching DVF:")
        for key, value in result.items():
            print(f"  {key}: {value}")
    finally:
        db.close()

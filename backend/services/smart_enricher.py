import requests
import re
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from models.dvf import TransactionDVF
import logging
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class SmartEnricher:
    """Scoring probabiliste multi-sources 100% gratuit"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def normalize_address(self, adresse: str) -> str:
        """Normalise une adresse"""
        if not adresse:
            return ""
        addr = adresse.upper()
        addr = re.sub(r'\d+\.0\s+', '', addr)
        addr = re.sub(r'\s+', ' ', addr)
        return addr.strip()
    
    def check_sirene(self, adresse: str, code_postal: str) -> tuple:
        """Vérifie si une entreprise est domiciliée à cette adresse (+50 points)"""
        try:
            query = f"adresseEtablissement:{adresse} AND codePostalEtablissement:{code_postal}"
            response = requests.get(
                "https://api.insee.fr/entreprises/sirene/V3/siret",
                params={'q': query, 'nombre': 1},
                headers={'Accept': 'application/json'},
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('etablissements'):
                    etab = data['etablissements'][0]
                    unite = etab.get('uniteLegale', {})
                    nom = unite.get('denominationUniteLegale')
                    forme = unite.get('categorieJuridiqueUniteLegale')
                    
                    if nom:
                        logger.info(f"✅ SIRENE: {nom} trouvé")
                        return 50, nom, self._determine_type(forme)
        except Exception as e:
            logger.debug(f"SIRENE: {e}")
        
        return 0, None, None
    
    def _determine_type(self, forme_juridique: str):
        """Détermine le type depuis le code INSEE"""
        if not forme_juridique:
            return None
        if forme_juridique == '6540':
            return 'SCI'
        elif forme_juridique in ['5499', '5505']:
            return 'SARL'
        elif forme_juridique in ['5710', '5720']:
            return 'SAS'
        return 'Entreprise'
    
    def check_historique_ventes(self, adresse: str, code_postal: str) -> tuple:
        """Analyse l'historique complet des ventes (+40 points max)"""
        # Récupérer TOUTES les ventes sur cette adresse
        ventes = self.db.query(
            TransactionDVF.date_mutation,
            TransactionDVF.valeur_fonciere,
            TransactionDVF.surface_reelle
        ).filter(
            TransactionDVF.adresse == adresse,
            TransactionDVF.code_postal == code_postal,
            TransactionDVF.date_mutation.isnot(None)
        ).order_by(TransactionDVF.date_mutation).all()
        
        if not ventes or len(ventes) < 2:
            return 0, None, None, False, None
        
        # Construire l'historique JSON
        historique = [
            {
                'date': str(v.date_mutation),
                'prix': float(v.valeur_fonciere) if v.valeur_fonciere else None,
                'surface': float(v.surface_reelle) if v.surface_reelle else None
            }
            for v in ventes
        ]
        
        nb_ventes = len(ventes)
        
        # Calculer la fréquence de vente
        premiere_vente = ventes[0].date_mutation
        derniere_vente = ventes[-1].date_mutation
        duree_totale_mois = (derniere_vente.year - premiere_vente.year) * 12 + (derniere_vente.month - premiere_vente.month)
        
        if duree_totale_mois == 0:
            return 0, None, historique, False, None
        
        frequence_mois = duree_totale_mois / (nb_ventes - 1) if nb_ventes > 1 else None
        
        # Détecter turnover régulier (ventes tous les 12-48 mois)
        turnover_regulier = False
        score = 0
        detail = None
        
        if nb_ventes >= 3 and frequence_mois and 12 <= frequence_mois <= 48:
            turnover_regulier = True
            score = 40
            detail = f"Turnover régulier : {nb_ventes} ventes en {duree_totale_mois//12} ans (tous les {int(frequence_mois)} mois) → INVESTISSEUR ACTIF"
            logger.info(f"🔥 {detail}")
        elif nb_ventes >= 3:
            score = 25
            detail = f"{nb_ventes} ventes sur cette adresse (turnover élevé)"
        elif nb_ventes >= 2:
            score = 15
            detail = f"{nb_ventes} ventes sur cette adresse"
        
        return score, detail, historique, turnover_regulier, int(frequence_mois) if frequence_mois else None
    
    def check_anciennete_optimale(self, transaction: TransactionDVF) -> tuple:
        """Détecte la durée de détention optimale (+30 points max)"""
        if not transaction.duree_detention_estimee:
            return 0, None
        
        duree = transaction.duree_detention_estimee
        
        # Sweet spot : 5-15 ans
        if 5 <= duree <= 10:
            logger.info(f"⏰ Ancienneté optimale: {duree} ans")
            return 30, f"Détention {duree} ans (cycle de vie optimal)"
        elif 10 < duree <= 15:
            return 25, f"Détention {duree} ans (forte plus-value)"
        elif 15 < duree <= 20:
            return 20, f"Détention {duree} ans (succession probable)"
        elif 20 < duree:
            return 15, f"Détention {duree}+ ans (très longue détention)"
        elif 3 <= duree < 5:
            return 10, f"Détention {duree} ans (début motivation)"
        
        return 0, None
    
    def check_address_patterns(self, adresse: str) -> tuple:
        """Détecte les patterns d'adresse professionnelle (+35 points)"""
        if not adresse:
            return 0, None
        
        addr_upper = adresse.upper()
        
        # Patterns TRÈS forts = +35 points
        strong_patterns = {
            'RESIDENCE ': 'Résidence (programme immobilier)',
            'RES ': 'Résidence (programme immobilier)',
            'RESID ': 'Résidence (programme immobilier)',
            'LOT ': 'Lotissement (division parcellaire)',
            'LOTS ': 'Lotissement (division parcellaire)',
            'PROGRAMME ': 'Programme neuf (promoteur)',
            'TOUR ': 'Tour (copropriété)',
            'DOMAINE ': 'Domaine (programme résidentiel)',
            'PARC RESIDENTIEL': 'Parc résidentiel (investisseur)'
        }
        
        for pattern, description in strong_patterns.items():
            if pattern in addr_upper:
                logger.info(f"🏢 Pattern FORT: '{pattern}' dans l'adresse")
                return 35, description
        
        # Patterns moyens = +20 points
        medium_patterns = {
            'ZAC ': 'Zone d\'aménagement concerté',
            'ZONE ': 'Zone aménagée',
            'BAT ': 'Bâtiment (copropriété)',
            'BATIMENT ': 'Bâtiment (copropriété)',
            'IMM ': 'Immeuble collectif',
            'IMMEUBLE ': 'Immeuble collectif',
            'HAMEAU ': 'Hameau (lotissement)',
            'CLOS ': 'Clos résidentiel',
            'ALL ': 'Allée (lotissement)',
            'ALLÉE ': 'Allée (lotissement)'
        }
        
        for pattern, description in medium_patterns.items():
            if pattern in addr_upper:
                logger.info(f"🏢 Pattern moyen: '{pattern}' dans l'adresse")
                return 20, description
        
        # Numéro de lot élevé = +25 points
        lot_match = re.search(r'LOT[:\s]*(\d+)', addr_upper)
        if lot_match:
            lot_num = int(lot_match.group(1))
            if lot_num > 10:
                logger.info(f"🏢 Numéro de lot élevé: {lot_num}")
                return 25, f"Lot n°{lot_num} (programme avec nombreux lots)"
        
        return 0, None
    
    def check_price_standardization(self, transaction: TransactionDVF) -> tuple:
        """Détecte les prix standardisés (signal pro) (+15 points)"""
        if not transaction.valeur_fonciere:
            return 0, None
        
        prix = transaction.valeur_fonciere
        
        # Prix ronds suspects (multiples de 10000)
        if prix % 10000 == 0 and prix > 50000:
            logger.info(f"💰 Prix standardisé: {prix}€")
            return 15, f"Prix rond {int(prix/1000)}k€ (tarif promoteur)"
        
        # Prix/m² très standardisé
        if transaction.surface_reelle and transaction.surface_reelle > 0:
            prix_m2 = prix / transaction.surface_reelle
            if prix_m2 % 100 == 0:
                return 10, f"Prix/m² standardisé {int(prix_m2)}€/m² (grille tarifaire)"
        
        return 0, None
    
    def calculate_professional_score(self, transaction: TransactionDVF) -> dict:
        """Calcule le score professionnel total (0-100)"""
        score = 0
        details = []
        nom = None
        type_proprio = None
        
        adresse_norm = self.normalize_address(transaction.adresse)
        
        # 1. SIRENE (+50)
        sirene_score, sirene_nom, sirene_type = self.check_sirene(
            adresse_norm, 
            transaction.code_postal
        )
        score += sirene_score
        if sirene_score > 0:
            details.append(f"Société domiciliée : {sirene_nom}")
            nom = sirene_nom
            type_proprio = sirene_type
        
        # 2. Historique ventes + Turnover régulier (+40)
        hist_score, hist_detail, historique, turnover_reg, freq = self.check_historique_ventes(
            transaction.adresse,
            transaction.code_postal
        )
        score += hist_score
        if hist_detail:
            details.append(hist_detail)
        
        # 3. Ancienneté optimale (+30)
        anc_score, anc_detail = self.check_anciennete_optimale(transaction)
        score += anc_score
        if anc_detail:
            details.append(anc_detail)
        
        # 4. Patterns adresse (+35)
        addr_score, addr_detail = self.check_address_patterns(transaction.adresse)
        score += addr_score
        if addr_detail:
            details.append(addr_detail)
        
        # 5. Prix standardisé (+15)
        price_score, price_detail = self.check_price_standardization(transaction)
        score += price_score
        if price_detail:
            details.append(price_detail)
        
        # Classification
        if score >= 60:
            classification = "Société probable"
        elif score >= 35:
            classification = "Potentiel professionnel"
        else:
            classification = "Particulier probable"
        
        return {
            'score': min(score, 100),
            'classification': classification,
            'nom': nom,
            'type': type_proprio or classification,
            'details': ' • '.join(details) if details else None,
            'historique_ventes': historique,
            'turnover_regulier': turnover_reg,
            'frequence_vente_mois': freq
        }
    
    def enrich_transactions(self, score_min: int = 0, limit: int = 1000):
        """Enrichit les transactions avec le scoring intelligent"""
        from datetime import datetime
        
        transactions = self.db.query(TransactionDVF).filter(
            TransactionDVF.score >= score_min,
            TransactionDVF.date_enrichissement.is_(None)
        ).order_by(TransactionDVF.score.desc()).limit(limit).all()
        
        enriched = 0
        pro_found = 0
        turnover_found = 0
        
        for trans in transactions:
            result = self.calculate_professional_score(trans)
            
            trans.proprietaire_type = result['type']
            trans.proprietaire_nom = result['nom']
            trans.details_detection = result['details']
            trans.historique_ventes = json.dumps(result['historique_ventes']) if result['historique_ventes'] else None
            trans.turnover_regulier = result['turnover_regulier']
            trans.frequence_vente_mois = result['frequence_vente_mois']
            trans.enrichi_pappers = True
            trans.date_enrichissement = datetime.now()
            
            enriched += 1
            
            if result['turnover_regulier']:
                turnover_found += 1
            
            if result['score'] >= 35:
                pro_found += 1
                
                logger.info(
                    f"Score {result['score']}: {trans.adresse} → "
                    f"{result['classification']} ({result['details']})"
                )
            
            if enriched % 10 == 0:
                self.db.commit()
        
        self.db.commit()
        
        logger.info(f"✅ {enriched} enrichies - {pro_found} pros - {turnover_found} turnover réguliers")
        
        return {
            'enriched': enriched,
            'pro_found': pro_found,
            'turnover_found': turnover_found
        }

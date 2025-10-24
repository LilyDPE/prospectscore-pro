import requests
import time
from sqlalchemy.orm import Session
from models.dvf import TransactionDVF
import logging

logger = logging.getLogger(__name__)

class PappersEnricher:
    BASE_URL = "https://api.pappers.fr/v2/recherche"
    
    def __init__(self, api_key: str, db: Session):
        self.api_key = api_key
        self.db = db
    
    def search_company_at_address(self, adresse: str, code_postal: str, commune: str):
        """Recherche une entreprise à une adresse donnée"""
        try:
            query = f"{adresse}, {code_postal} {commune}"
            response = requests.get(self.BASE_URL, params={
                'api_token': self.api_key,
                'q': query,
                'par_page': 1,
                'precision': 'standard'
            }, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('resultats'):
                    entreprise = data['resultats'][0]
                    return {
                        'nom': entreprise.get('nom_entreprise'),
                        'siren': entreprise.get('siren'),
                        'forme_juridique': entreprise.get('forme_juridique')
                    }
        except Exception as e:
            logger.error(f"Erreur Pappers API: {e}")
        
        return None
    
    def determine_type_proprietaire(self, forme_juridique: str):
        """Détermine le type de propriétaire selon la forme juridique"""
        if not forme_juridique:
            return 'Particulier'
        
        forme = forme_juridique.upper()
        
        if 'SCI' in forme or 'CIVILE IMMOBILIERE' in forme:
            return 'SCI'
        elif 'SARL' in forme:
            return 'SARL'
        elif 'SAS' in forme:
            return 'SAS'
        elif 'SA' in forme and 'SARL' not in forme and 'SAS' not in forme:
            return 'SA'
        else:
            return 'Entreprise'
    
    def enrich_transaction(self, transaction: TransactionDVF):
        """Enrichit une transaction avec les données Pappers"""
        if transaction.enrichi_pappers:
            return False  # Déjà enrichie
        
        company = self.search_company_at_address(
            transaction.adresse,
            transaction.code_postal,
            transaction.commune
        )
        
        if company:
            transaction.proprietaire_nom = company['nom']
            transaction.proprietaire_siren = company['siren']
            transaction.proprietaire_type = self.determine_type_proprietaire(company['forme_juridique'])
        else:
            transaction.proprietaire_type = 'Particulier'
        
        transaction.enrichi_pappers = True
        self.db.commit()
        return True
    
    def enrich_best_prospects(self, score_min: int = 50, limit: int = 100):
        """Enrichit les meilleurs prospects non encore enrichis"""
        transactions = self.db.query(TransactionDVF).filter(
            TransactionDVF.score >= score_min,
            TransactionDVF.enrichi_pappers == False
        ).order_by(TransactionDVF.score.desc()).limit(limit).all()
        
        enriched = 0
        for trans in transactions:
            if self.enrich_transaction(trans):
                enriched += 1
                logger.info(f"Enrichi: {trans.adresse} - {trans.proprietaire_type}")
                time.sleep(1)  # Rate limiting
        
        logger.info(f"✅ {enriched} transactions enrichies avec Pappers")
        return enriched

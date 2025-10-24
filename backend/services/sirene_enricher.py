import requests
import time
from sqlalchemy.orm import Session
from models.dvf import TransactionDVF
import logging
import urllib.parse

logger = logging.getLogger(__name__)

class SireneEnricher:
    BASE_URL = "https://api.insee.fr/entreprises/sirene/V3/siret"
    
    def __init__(self, db: Session):
        self.db = db
    
    def search_company_at_address(self, adresse: str, code_postal: str, commune: str):
        """Recherche une entreprise à une adresse via l'API SIRENE (gratuite)"""
        try:
            adresse_clean = adresse.replace('.0 ', ' ').strip()
            query = f"adresseEtablissement:{adresse_clean} AND codePostalEtablissement:{code_postal}"
            
            params = {
                'q': query,
                'nombre': 1
            }
            
            response = requests.get(
                self.BASE_URL,
                params=params,
                headers={'Accept': 'application/json'},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('etablissements'):
                    etab = data['etablissements'][0]
                    unite = etab.get('uniteLegale', {})
                    
                    return {
                        'nom': unite.get('denominationUniteLegale') or etab.get('denominationUsuelleEtablissement'),
                        'siren': unite.get('siren'),
                        'forme_juridique': unite.get('categorieJuridiqueUniteLegale')
                    }
        except Exception as e:
            logger.error(f"Erreur SIRENE API: {e}")
        
        return None
    
    def determine_type_proprietaire(self, forme_juridique: str):
        """Détermine le type selon le code forme juridique INSEE"""
        if not forme_juridique:
            return 'Particulier'
        
        if forme_juridique == '6540':
            return 'SCI'
        elif forme_juridique in ['5499', '5505']:
            return 'SARL'
        elif forme_juridique in ['5710', '5720']:
            return 'SAS'
        elif forme_juridique in ['5599', '5560']:
            return 'SA'
        elif forme_juridique:
            return 'Entreprise'
        else:
            return 'Particulier'
    
    def enrich_transaction(self, transaction: TransactionDVF):
        """Enrichit une transaction avec SIRENE"""
        if transaction.enrichi_pappers:
            return False
        
        company = self.search_company_at_address(
            transaction.adresse,
            transaction.code_postal,
            transaction.commune
        )
        
        if company:
            transaction.proprietaire_nom = company['nom']
            transaction.proprietaire_siren = company['siren']
            transaction.proprietaire_type = self.determine_type_proprietaire(company['forme_juridique'])
            logger.info(f"✅ {company['nom']} ({transaction.proprietaire_type})")
        else:
            transaction.proprietaire_type = 'Particulier'
        
        transaction.enrichi_pappers = True
        self.db.commit()
        return True
    
    def enrich_best_prospects(self, score_min: int = 50, limit: int = 1000):
        """Enrichit les meilleurs prospects"""
        transactions = self.db.query(TransactionDVF).filter(
            TransactionDVF.score >= score_min,
            TransactionDVF.enrichi_pappers == False
        ).order_by(TransactionDVF.score.desc()).limit(limit).all()
        
        enriched = 0
        sci_found = 0
        entreprises_found = 0
        
        for trans in transactions:
            if self.enrich_transaction(trans):
                enriched += 1
                if trans.proprietaire_type == 'SCI':
                    sci_found += 1
                elif trans.proprietaire_type in ['SARL', 'SAS', 'SA', 'Entreprise']:
                    entreprises_found += 1
                
                if enriched % 10 == 0:
                    logger.info(f"📊 {enriched}/{limit} - SCI: {sci_found}, Entreprises: {entreprises_found}")
                
                time.sleep(0.5)
        
        logger.info(f"✅ {enriched} enrichies - {sci_found} SCI - {entreprises_found} entreprises")
        return {
            'enriched': enriched,
            'sci_found': sci_found,
            'entreprises_found': entreprises_found
        }

import requests
import pandas as pd
from sqlalchemy.orm import Session
from models.dvf import TransactionDVF
import logging
import re
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class BodaccEnricher:
    """Enrichissement via les données BODACC (annonces légales gratuites)"""
    
    def __init__(self, db: Session):
        self.db = db
        self.sci_cache = {}
    
    def download_bodacc_data(self):
        """Télécharge les données BODACC depuis data.gouv.fr"""
        # API BODACC gratuite
        url = "https://www.data.gouv.fr/fr/datasets/r/8b5f2e7c-5e3a-4d2c-9d6c-5f5e5c5c5c5c"
        
        try:
            logger.info("📥 Téléchargement des données BODACC...")
            # On peut aussi utiliser l'API directe du BODACC
            response = requests.get(
                "https://bodacc-datadila.opendatasoft.com/api/records/1.0/search/",
                params={
                    'dataset': 'annonces-commerciales',
                    'rows': 10000,
                    'refine.type': 'Vente'
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('records', [])
        except Exception as e:
            logger.error(f"Erreur téléchargement BODACC: {e}")
        
        return []
    
    def extract_sci_from_bodacc(self, records):
        """Extrait les SCI et leurs adresses depuis les annonces"""
        sci_dict = {}
        
        for record in records:
            fields = record.get('fields', {})
            
            # Récupérer le nom de la société
            nom_societe = fields.get('nom_entreprise') or fields.get('denomination')
            forme_juridique = fields.get('forme_juridique', '')
            
            # Identifier les SCI
            if 'SCI' in forme_juridique or (nom_societe and 'SCI' in nom_societe.upper()):
                adresse = fields.get('adresse')
                code_postal = fields.get('code_postal')
                
                if adresse and code_postal:
                    key = f"{adresse}_{code_postal}".lower()
                    sci_dict[key] = {
                        'nom': nom_societe,
                        'forme': 'SCI',
                        'adresse': adresse,
                        'code_postal': code_postal
                    }
        
        logger.info(f"✅ {len(sci_dict)} SCI trouvées dans le BODACC")
        return sci_dict
    
    def normalize_address(self, adresse: str, code_postal: str) -> str:
        """Normalise une adresse pour le matching"""
        if not adresse:
            return ""
        
        # Nettoyer l'adresse
        addr = adresse.lower()
        addr = re.sub(r'\d+\.0\s+', '', addr)  # Enlever les ".0"
        addr = re.sub(r'\s+', ' ', addr)  # Espaces multiples
        addr = addr.strip()
        
        return f"{addr}_{code_postal}".lower()
    
    def enrich_from_bodacc(self, score_min: int = 50, limit: int = 1000):
        """Enrichit les transactions en croisant avec BODACC"""
        
        # Télécharger et extraire les SCI
        records = self.download_bodacc_data()
        self.sci_cache = self.extract_sci_from_bodacc(records)
        
        if not self.sci_cache:
            logger.warning("⚠️ Aucune donnée BODACC trouvée")
            return {'enriched': 0, 'sci_found': 0}
        
        # Enrichir les transactions
        transactions = self.db.query(TransactionDVF).filter(
            TransactionDVF.score >= score_min,
            TransactionDVF.enrichi_pappers == False
        ).order_by(TransactionDVF.score.desc()).limit(limit).all()
        
        enriched = 0
        sci_found = 0
        
        for trans in transactions:
            key = self.normalize_address(trans.adresse, trans.code_postal)
            
            if key in self.sci_cache:
                sci_info = self.sci_cache[key]
                trans.proprietaire_nom = sci_info['nom']
                trans.proprietaire_type = 'SCI'
                sci_found += 1
                logger.info(f"✅ SCI trouvée: {sci_info['nom']} à {trans.adresse}")
            else:
                trans.proprietaire_type = 'Particulier'
            
            trans.enrichi_pappers = True
            enriched += 1
            
            if enriched % 100 == 0:
                self.db.commit()
        
        self.db.commit()
        logger.info(f"✅ {enriched} enrichies - {sci_found} SCI trouvées")
        
        return {
            'enriched': enriched,
            'sci_found': sci_found,
            'bodacc_records': len(records)
        }

import requests
import time
from sqlalchemy.orm import Session
from models.dvf import TransactionDVF
import logging

logger = logging.getLogger(__name__)

class Geocoder:
    BASE_URL = "https://api-adresse.data.gouv.fr/search/"
    
    def __init__(self, db: Session):
        self.db = db
    
    def geocode_address(self, adresse: str, code_postal: str, commune: str):
        """Géocode une adresse via l'API gouvernementale"""
        try:
            query = f"{adresse}, {code_postal} {commune}"
            response = requests.get(self.BASE_URL, params={
                'q': query,
                'limit': 1
            }, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('features'):
                    coords = data['features'][0]['geometry']['coordinates']
                    return coords[1], coords[0]  # latitude, longitude
        except Exception as e:
            logger.error(f"Erreur géocodage: {e}")
        
        return None, None
    
    def geocode_all_transactions(self, limit: int = 1000):
        """Géocode les transactions sans coordonnées"""
        transactions = self.db.query(TransactionDVF).filter(
            TransactionDVF.latitude.is_(None)
        ).limit(limit).all()
        
        count = 0
        for trans in transactions:
            lat, lon = self.geocode_address(trans.adresse, trans.code_postal, trans.commune)
            
            if lat and lon:
                trans.latitude = lat
                trans.longitude = lon
                count += 1
                
                if count % 50 == 0:
                    self.db.commit()
                    logger.info(f"Géocodé {count} transactions...")
                    time.sleep(1)  # Rate limiting
        
        self.db.commit()
        logger.info(f"✅ Géocodage terminé : {count} transactions")
        return count

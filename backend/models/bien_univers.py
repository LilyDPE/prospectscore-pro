"""
Modèle pour les biens univers avec features ML contextuelles
Table: biens_univers

Features calculées:
- local_turnover_12m: nombre de ventes dans un rayon de 500m sur 12 mois
- sale_density_12m: densité de ventes corrigée (0-0.935)
- zone_type: RURAL_ISOLE / RURAL / PERIURBAIN / URBAIN
- last_price: dernier prix connu
- code_postal: code postal du bien
- type_local: type de bien (Maison, Appartement, etc.)
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.sql import func
from database import Base

class BienUnivers(Base):
    """
    Bien immobilier de l'univers avec features ML pour le scoring de propension
    """
    __tablename__ = "biens_univers"

    # Identifiant unique
    id_bien = Column(Integer, primary_key=True, index=True)

    # Informations de base
    adresse = Column(String, index=True)
    code_postal = Column(String(5), index=True)
    commune = Column(String)
    departement = Column(String(3), index=True)

    # Caractéristiques du bien
    type_local = Column(String, index=True)  # Maison, Appartement, Local, Dépendance
    surface_reelle = Column(Float)
    nombre_pieces = Column(Integer)

    # Géolocalisation
    latitude = Column(Float, index=True)
    longitude = Column(Float, index=True)
    geocode_quality = Column(String)  # housenumber, street, city

    # Dernière transaction connue
    last_price = Column(Float, index=True)
    last_transaction_date = Column(DateTime)

    # ==================== FEATURES ML ====================

    # Zone type (4 catégories)
    zone_type = Column(String(20), index=True)  # RURAL_ISOLE, RURAL, PERIURBAIN, URBAIN

    # Activité du marché local (rayon 500m, 12 mois)
    local_turnover_12m = Column(Integer, default=0, index=True)  # Nombre de ventes
    sale_density_12m = Column(Float, default=0.0, index=True)  # Densité corrigée (0-1)

    # Statistiques du marché local
    avg_local_price = Column(Float)  # Prix moyen dans la zone
    median_local_price = Column(Float)  # Prix médian dans la zone
    local_price_evolution = Column(Float)  # Évolution prix sur 12 mois (%)

    # Attractivité de la zone
    zone_attractivity_score = Column(Float)  # Score d'attractivité 0-100

    # Score de propension à vendre (calculé par le modèle ML)
    propensity_score = Column(Integer, default=0, index=True)
    propensity_category = Column(String(20))  # TRES_FORT, FORT, MOYEN, FAIBLE

    # Métadonnées
    features_calculated = Column(Boolean, default=False, index=True)
    features_calculated_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        """Conversion en dictionnaire pour l'API"""
        return {
            "id_bien": self.id_bien,
            "adresse": self.adresse,
            "code_postal": self.code_postal,
            "commune": self.commune,
            "departement": self.departement,
            "type_local": self.type_local,
            "surface_reelle": self.surface_reelle,
            "nombre_pieces": self.nombre_pieces,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "last_price": self.last_price,
            "last_transaction_date": str(self.last_transaction_date) if self.last_transaction_date else None,
            "features": {
                "zone_type": self.zone_type,
                "local_turnover_12m": self.local_turnover_12m,
                "sale_density_12m": round(self.sale_density_12m, 4) if self.sale_density_12m else 0,
                "avg_local_price": self.avg_local_price,
                "median_local_price": self.median_local_price,
                "local_price_evolution": round(self.local_price_evolution, 2) if self.local_price_evolution else None,
                "zone_attractivity_score": round(self.zone_attractivity_score, 1) if self.zone_attractivity_score else None
            },
            "propensity": {
                "score": self.propensity_score,
                "category": self.propensity_category
            },
            "metadata": {
                "features_calculated": self.features_calculated,
                "features_calculated_at": str(self.features_calculated_at) if self.features_calculated_at else None
            }
        }

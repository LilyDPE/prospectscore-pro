from sqlalchemy import Column, Integer, String, Float, Date, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class DPECollecte(Base):
    __tablename__ = "dpe_collectes"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Identification DPE
    numero_dpe = Column(String, unique=True, index=True)
    
    # Localisation
    adresse = Column(String, index=True)
    code_postal = Column(String, index=True)
    commune = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    
    # Performance énergétique
    classe_dpe = Column(String, index=True)  # A, B, C, D, E, F, G
    consommation_energie = Column(Float)  # kWh/m²/an
    emission_ges = Column(Float)
    
    # Bien
    type_batiment = Column(String)  # Maison, Appartement
    annee_construction = Column(Integer)
    surface_habitable = Column(Float)
    
    # Date DPE
    date_etablissement_dpe = Column(Date)
    date_visite_dpe = Column(Date, nullable=True)
    
    # Statut de prospection (depuis DPE Pro)
    statut = Column(String, default='nouveau')  # nouveau, interesse, visite, brule
    notes = Column(String, nullable=True)
    vu_par = Column(String, nullable=True)  # Liste des agents qui ont vu ce bien
    
    # Méta
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

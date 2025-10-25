from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Boolean, JSON
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.sql import func
from database import Base

class TransactionDVF(Base):
    __tablename__ = "transactions_dvf"
    
    id = Column(Integer, primary_key=True, index=True)
    id_mutation = Column(String, unique=True, index=True)
    date_mutation = Column(Date)
    adresse = Column(String)
    code_postal = Column(String, index=True)
    commune = Column(String, index=True)
    departement = Column(String, index=True)
    type_local = Column(String)
    surface_reelle = Column(Float)
    nombre_pieces = Column(Integer)
    valeur_fonciere = Column(Float)
    classe_dpe = Column(String, nullable=True)
    valeur_dpe = Column(Float, nullable=True)
    duree_detention_estimee = Column(Integer, nullable=True)
    score = Column(Integer, index=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    
    # Colonnes propriétaire / enrichissement Pappers
    proprietaire_type = Column(String, nullable=True)
    proprietaire_nom = Column(String, nullable=True)
    proprietaire_siren = Column(String, nullable=True)
    enrichi_pappers = Column(Boolean, default=False)
    date_enrichissement = Column(DateTime, nullable=True)
    details_detection = Column(String, nullable=True)
    propensity_score = Column(Integer, default=0)
    propensity_raisons = Column(ARRAY(String), nullable=True)
    propensity_timeframe = Column(String, nullable=True)
    contact_priority = Column(String, nullable=True)
    cohorte_vente_active = Column(Boolean, default=False)
    contraintes_convergentes = Column(Integer, default=0)
    pic_marche_local = Column(Boolean, default=False)
    derniere_analyse_propension = Column(DateTime, nullable=True)
    historique_ventes = Column(JSON, nullable=True)
    turnover_regulier = Column(Boolean, default=False)
    frequence_vente_mois = Column(Integer, nullable=True)
    date_enrichissement = Column(DateTime, nullable=True)
    details_detection = Column(String, nullable=True)
    propensity_score = Column(Integer, default=0)
    propensity_raisons = Column(ARRAY(String), nullable=True)
    propensity_timeframe = Column(String, nullable=True)
    contact_priority = Column(String, nullable=True)
    cohorte_vente_active = Column(Boolean, default=False)
    contraintes_convergentes = Column(Integer, default=0)
    pic_marche_local = Column(Boolean, default=False)
    derniere_analyse_propension = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


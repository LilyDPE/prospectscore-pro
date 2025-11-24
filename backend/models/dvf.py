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

    # Colonnes pour auto-apprentissage et validation
    statut_final = Column(Integer, nullable=True)  # 0=Pas vendu, 1=Vendu confirmé, 2=En négociation
    date_validation = Column(DateTime, nullable=True)
    source_validation = Column(String, nullable=True)  # 'DVF_API', 'AGENT_FEEDBACK', 'WEB_SCRAPING'
    prix_vente_reel = Column(Float, nullable=True)  # Prix réel de vente (si différent de valeur_fonciere)
    delai_vente_jours = Column(Integer, nullable=True)  # Jours entre prédiction et vente
    precision_prediction = Column(Float, nullable=True)  # Écart entre propensity_score et résultat réel
    feedback_agent = Column(String, nullable=True)  # Notes de l'agent (raison refus, etc.)
    contacted_at = Column(DateTime, nullable=True)  # Date du premier contact
    utilisé_pour_training = Column(Boolean, default=False)  # Déjà utilisé dans un entraînement
    date_ajout_training = Column(DateTime, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


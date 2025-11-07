"""
Modèle pour la gestion des commerciaux et assignation de prospects
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Table, Float
from sqlalchemy.dialects.postgresql import ARRAY, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

class Commercial(Base):
    """
    Commercial immobilier avec zones géographiques assignées
    """
    __tablename__ = "commerciaux"

    id = Column(Integer, primary_key=True, index=True)

    # Informations personnelles
    nom = Column(String(100), nullable=False)
    prenom = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    telephone = Column(String(20))

    # Authentification (si séparé des users)
    # Sinon on peut lier à la table users
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)

    # Zones géographiques assignées
    codes_postaux_assignes = Column(ARRAY(String), default=[], index=True)
    departements_assignes = Column(ARRAY(String), default=[], index=True)
    communes_assignees = Column(ARRAY(String), default=[])

    # Configuration
    actif = Column(Boolean, default=True, index=True)
    capacite_max_prospects = Column(Integer, default=100)  # Limite de prospects simultanés
    min_propensity_score = Column(Integer, default=60)  # Score minimum pour assignation auto

    # Statistiques
    nombre_prospects_assignes = Column(Integer, default=0)
    nombre_prospects_contactes = Column(Integer, default=0)
    nombre_rdv_obtenus = Column(Integer, default=0)
    nombre_mandats_obtenus = Column(Integer, default=0)

    # Performance
    taux_conversion_contact = Column(Float, default=0.0)  # % prospects contactés
    taux_conversion_rdv = Column(Float, default=0.0)  # % RDV obtenus
    taux_conversion_mandat = Column(Float, default=0.0)  # % Mandats obtenus

    # Dernière activité
    derniere_assignation = Column(DateTime)
    dernier_contact = Column(DateTime)

    # Métadonnées
    notes = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relations
    # prospects = relationship("ProspectAssignment", back_populates="commercial")

    def to_dict(self):
        """Conversion en dictionnaire pour l'API"""
        return {
            "id": self.id,
            "nom": self.nom,
            "prenom": self.prenom,
            "nom_complet": f"{self.prenom} {self.nom}",
            "email": self.email,
            "telephone": self.telephone,
            "actif": self.actif,
            "zones": {
                "codes_postaux": self.codes_postaux_assignes or [],
                "departements": self.departements_assignes or [],
                "communes": self.communes_assignees or []
            },
            "configuration": {
                "capacite_max": self.capacite_max_prospects,
                "min_propensity_score": self.min_propensity_score
            },
            "statistiques": {
                "prospects_assignes": self.nombre_prospects_assignes,
                "prospects_contactes": self.nombre_prospects_contactes,
                "rdv_obtenus": self.nombre_rdv_obtenus,
                "mandats_obtenus": self.nombre_mandats_obtenus
            },
            "performance": {
                "taux_conversion_contact": round(self.taux_conversion_contact, 2),
                "taux_conversion_rdv": round(self.taux_conversion_rdv, 2),
                "taux_conversion_mandat": round(self.taux_conversion_mandat, 2)
            },
            "derniere_activite": {
                "derniere_assignation": str(self.derniere_assignation) if self.derniere_assignation else None,
                "dernier_contact": str(self.dernier_contact) if self.dernier_contact else None
            },
            "notes": self.notes
        }

class ProspectAssignment(Base):
    """
    Assignation d'un prospect à un commercial
    Permet de suivre l'historique et les actions
    """
    __tablename__ = "prospect_assignments"

    id = Column(Integer, primary_key=True, index=True)

    # Références
    commercial_id = Column(Integer, ForeignKey('commerciaux.id'), nullable=False, index=True)
    bien_id = Column(Integer, ForeignKey('biens_univers.id_bien'), nullable=False, index=True)

    # Score au moment de l'assignation
    propensity_score_at_assignment = Column(Integer)
    zone_type = Column(String(20))

    # Statut du prospect
    statut = Column(String(50), default="NOUVEAU", index=True)
    # NOUVEAU, EN_COURS, CONTACTE, RDV_PRIS, INTERESSE, MANDAT_OBTENU, PERDU, ABANDONNE

    priorite = Column(String(20), default="MOYENNE")  # HAUTE, MOYENNE, BASSE

    # Actions commerciales
    date_assignation = Column(DateTime, server_default=func.now())
    date_premier_contact = Column(DateTime)
    date_dernier_contact = Column(DateTime)
    nombre_tentatives_contact = Column(Integer, default=0)

    # Résultats
    date_rdv = Column(DateTime)
    date_mandat = Column(DateTime)
    valeur_mandat = Column(Float)  # Montant estimé du bien

    # Suivi
    notes_commercial = Column(String)
    historique_actions = Column(JSON, default=[])  # Liste des actions effectuées

    # Raison de perte
    raison_perte = Column(String)  # Si statut = PERDU

    # Métadonnées
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relations
    # commercial = relationship("Commercial", back_populates="prospects")
    # bien = relationship("BienUnivers")

    def to_dict(self):
        """Conversion en dictionnaire pour l'API"""
        return {
            "id": self.id,
            "commercial_id": self.commercial_id,
            "bien_id": self.bien_id,
            "propensity_score": self.propensity_score_at_assignment,
            "zone_type": self.zone_type,
            "statut": self.statut,
            "priorite": self.priorite,
            "dates": {
                "assignation": str(self.date_assignation) if self.date_assignation else None,
                "premier_contact": str(self.date_premier_contact) if self.date_premier_contact else None,
                "dernier_contact": str(self.date_dernier_contact) if self.date_dernier_contact else None,
                "rdv": str(self.date_rdv) if self.date_rdv else None,
                "mandat": str(self.date_mandat) if self.date_mandat else None
            },
            "actions": {
                "nombre_tentatives": self.nombre_tentatives_contact,
                "historique": self.historique_actions or []
            },
            "resultat": {
                "valeur_mandat": self.valeur_mandat,
                "raison_perte": self.raison_perte
            },
            "notes": self.notes_commercial
        }

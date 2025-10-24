from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Définir Base ici
Base = declarative_base()

def init_db():
    """Crée toutes les tables"""
    from models.dvf import TransactionDVF
    
    # Créer les tables
    Base.metadata.create_all(bind=engine)
    
    print("✅ Toutes les tables ont été créées")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

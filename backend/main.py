from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from jose import JWTError, jwt
from passlib.context import CryptContext
import os
from dotenv import load_dotenv

load_dotenv()

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL")
JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key-change-this")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24

# FastAPI App
app = FastAPI(
    title="ProspectScore Pro API",
    description="Système de scoring de vendeurs potentiels pour 2A Immobilier",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

# ==================== MODELS ====================

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    full_name = Column(String)
    role = Column(String, default="user")  # admin, user
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Prospect(Base):
    __tablename__ = "prospects"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Informations propriétaire
    owner_name = Column(String, nullable=True)
    owner_email = Column(String, nullable=True)
    owner_phone = Column(String, nullable=True)
    
    # Informations propriété
    address = Column(String, index=True)
    postal_code = Column(String, index=True)
    city = Column(String, index=True)
    property_type = Column(String)  # maison, appartement
    surface = Column(Float)
    rooms = Column(Integer)
    
    # Informations DPE
    dpe_score = Column(String)  # A, B, C, D, E, F, G
    dpe_value = Column(Float)
    ges_score = Column(String)
    energy_cost_min = Column(Float)
    energy_cost_max = Column(Float)
    
    # Scoring
    score = Column(Float, index=True)  # Score final 0-100
    score_details = Column(JSON)  # Détails du calcul
    priority = Column(String, index=True)  # high, medium, low
    
    # Estimation valeur
    estimated_value = Column(Float, nullable=True)
    estimated_work_cost = Column(Float, nullable=True)
    
    # Statut
    status = Column(String, default="new")  # new, contacted, interested, qualified, lost
    notes = Column(Text, nullable=True)
    
    # Métadonnées
    assigned_to = Column(Integer, nullable=True)  # user_id
    source = Column(String)  # dpe_scraping, manual, import
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    contacted_at = Column(DateTime, nullable=True)
    last_interaction = Column(DateTime, nullable=True)

class DPEData(Base):
    """Table pour stocker les données DPE ADEME"""
    __tablename__ = "dpe_ademe"
    
    id = Column(Integer, primary_key=True, index=True)
    numero_dpe = Column(String, unique=True, index=True)
    
    # Adresse
    adresse = Column(String)
    code_postal = Column(String, index=True)
    commune = Column(String, index=True)
    
    # Caractéristiques
    type_batiment = Column(String)
    surface_habitable = Column(Float)
    nb_pieces = Column(Integer)
    annee_construction = Column(Integer)
    
    # Performances énergétiques
    classe_consommation_energie = Column(String, index=True)
    consommation_energie = Column(Float)
    classe_estimation_ges = Column(String)
    estimation_ges = Column(Float)
    
    # Coûts
    cout_total_5_usages_e_finale_min = Column(Float)
    cout_total_5_usages_e_finale_max = Column(Float)
    
    # Métadonnées
    date_etablissement_dpe = Column(DateTime)
    date_reception_dpe = Column(DateTime)
    
    created_at = Column(DateTime, default=datetime.utcnow)

# Create tables
Base.metadata.create_all(bind=engine)

# ==================== SCHEMAS ====================

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class ProspectCreate(BaseModel):
    address: str
    postal_code: str
    city: str
    property_type: str
    surface: float
    rooms: int
    dpe_score: Optional[str] = None
    dpe_value: Optional[float] = None
    owner_name: Optional[str] = None
    owner_email: Optional[str] = None
    owner_phone: Optional[str] = None

class ProspectUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
    owner_name: Optional[str] = None
    owner_email: Optional[str] = None
    owner_phone: Optional[str] = None
    contacted_at: Optional[datetime] = None

class ProspectResponse(BaseModel):
    id: int
    address: str
    postal_code: str
    city: str
    property_type: str
    surface: float
    rooms: int
    dpe_score: Optional[str]
    score: float
    priority: str
    status: str
    estimated_value: Optional[float]
    created_at: datetime
    
    class Config:
        from_attributes = True

# ==================== DEPENDENCIES ====================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        token = credentials.credentials
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return email
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def get_current_user(
    email: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

# ==================== SCORING SYSTEM ====================

def calculate_prospect_score(prospect_data: dict) -> tuple:
    """
    Calcule le score d'un prospect vendeur potentiel (0-100)
    Retourne (score, details, priority)
    """
    score = 0
    details = {}
    
    # 1. Score DPE (35 points max)
    dpe_score = prospect_data.get("dpe_score", "").upper()
    dpe_points = {
        "G": 35, "F": 30, "E": 20, "D": 10, "C": 5, "B": 2, "A": 0
    }
    dpe_contribution = dpe_points.get(dpe_score, 0)
    score += dpe_contribution
    details["dpe"] = {
        "score": dpe_score,
        "points": dpe_contribution,
        "max": 35,
        "reason": f"DPE {dpe_score} = forte probabilité de vente si travaux nécessaires"
    }
    
    # 2. Coût énergétique (25 points max)
    energy_cost_max = prospect_data.get("energy_cost_max", 0)
    if energy_cost_max > 3000:
        energy_contribution = 25
    elif energy_cost_max > 2000:
        energy_contribution = 20
    elif energy_cost_max > 1500:
        energy_contribution = 15
    elif energy_cost_max > 1000:
        energy_contribution = 10
    else:
        energy_contribution = 5
    
    score += energy_contribution
    details["energy_cost"] = {
        "annual_cost": energy_cost_max,
        "points": energy_contribution,
        "max": 25,
        "reason": "Coûts énergétiques élevés = motivation à vendre"
    }
    
    # 3. Type de bien (15 points max)
    property_type = prospect_data.get("property_type", "").lower()
    if property_type == "maison":
        type_contribution = 15
        type_reason = "Maisons = marché plus actif"
    elif property_type == "appartement":
        type_contribution = 10
        type_reason = "Appartements = bon marché"
    else:
        type_contribution = 5
        type_reason = "Type non spécifié"
    
    score += type_contribution
    details["property_type"] = {
        "type": property_type,
        "points": type_contribution,
        "max": 15,
        "reason": type_reason
    }
    
    # 4. Surface (15 points max)
    surface = prospect_data.get("surface", 0)
    if surface >= 100:
        surface_contribution = 15
    elif surface >= 80:
        surface_contribution = 12
    elif surface >= 60:
        surface_contribution = 8
    elif surface >= 40:
        surface_contribution = 5
    else:
        surface_contribution = 2
    
    score += surface_contribution
    details["surface"] = {
        "value": surface,
        "points": surface_contribution,
        "max": 15,
        "reason": "Surface importante = valeur plus élevée"
    }
    
    # 5. Localisation (10 points max) - basique pour l'instant
    postal_code = prospect_data.get("postal_code", "")
    # Zone à améliorer avec données de marché réelles
    if postal_code.startswith("75"):  # Paris
        location_contribution = 10
    elif postal_code.startswith(("92", "93", "94")):  # Proche banlieue
        location_contribution = 8
    else:
        location_contribution = 5
    
    score += location_contribution
    details["location"] = {
        "postal_code": postal_code,
        "points": location_contribution,
        "max": 10,
        "reason": "Localisation impacte l'intérêt de vente"
    }
    
    # Détermination de la priorité
    if score >= 70:
        priority = "high"
    elif score >= 50:
        priority = "medium"
    else:
        priority = "low"
    
    details["total"] = {
        "score": round(score, 1),
        "max": 100,
        "priority": priority
    }
    
    return round(score, 1), details, priority

# ==================== ROUTES ====================

@app.get("/")
def root():
    return {
        "app": "ProspectScore Pro",
        "version": "1.0.0",
        "status": "operational"
    }

# Auth routes
@app.post("/api/auth/register", response_model=Token)
def register(user: UserCreate, db: Session = Depends(get_db)):
    # Vérifier si l'utilisateur existe
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Créer l'utilisateur
    hashed_password = pwd_context.hash(user.password)
    new_user = User(
        email=user.email,
        hashed_password=hashed_password,
        full_name=user.full_name
    )
    db.add(new_user)
    db.commit()
    
    # Créer le token
    access_token = create_access_token({"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/api/auth/login", response_model=Token)
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == credentials.email).first()
    if not user or not pwd_context.verify(credentials.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    access_token = create_access_token({"sub": credentials.email})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/auth/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role
    }

# Prospect routes
@app.post("/api/prospects", response_model=ProspectResponse)
def create_prospect(
    prospect: ProspectCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Calculer le score
    prospect_dict = prospect.dict()
    score, details, priority = calculate_prospect_score(prospect_dict)
    
    # Créer le prospect
    new_prospect = Prospect(
        **prospect_dict,
        score=score,
        score_details=details,
        priority=priority,
        assigned_to=current_user.id,
        source="manual"
    )
    
    db.add(new_prospect)
    db.commit()
    db.refresh(new_prospect)
    
    return new_prospect

@app.get("/api/prospects", response_model=List[ProspectResponse])
def list_prospects(
    skip: int = 0,
    limit: int = 50,
    priority: Optional[str] = None,
    status: Optional[str] = None,
    postal_code: Optional[str] = None,
    min_score: Optional[float] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Prospect)
    
    # Filtres
    if priority:
        query = query.filter(Prospect.priority == priority)
    if status:
        query = query.filter(Prospect.status == status)
    if postal_code:
        query = query.filter(Prospect.postal_code.like(f"{postal_code}%"))
    if min_score:
        query = query.filter(Prospect.score >= min_score)
    
    # Tri par score décroissant
    query = query.order_by(Prospect.score.desc())
    
    prospects = query.offset(skip).limit(limit).all()
    return prospects

@app.get("/api/prospects/{prospect_id}")
def get_prospect(
    prospect_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    prospect = db.query(Prospect).filter(Prospect.id == prospect_id).first()
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")
    return prospect

@app.put("/api/prospects/{prospect_id}")
def update_prospect(
    prospect_id: int,
    update: ProspectUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    prospect = db.query(Prospect).filter(Prospect.id == prospect_id).first()
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")
    
    # Mise à jour
    for key, value in update.dict(exclude_unset=True).items():
        setattr(prospect, key, value)
    
    prospect.updated_at = datetime.utcnow()
    if update.contacted_at:
        prospect.last_interaction = update.contacted_at
    
    db.commit()
    db.refresh(prospect)
    
    return prospect

@app.delete("/api/prospects/{prospect_id}")
def delete_prospect(
    prospect_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    prospect = db.query(Prospect).filter(Prospect.id == prospect_id).first()
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")
    
    db.delete(prospect)
    db.commit()
    
    return {"message": "Prospect deleted"}

# DPE Data routes
@app.get("/api/dpe/search")
def search_dpe(
    postal_code: str = Query(..., min_length=5, max_length=5),
    dpe_min: Optional[str] = Query(None, pattern="^[A-G]$"),
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Recherche dans la base DPE ADEME"""
    query = db.query(DPEData).filter(DPEData.code_postal == postal_code)
    
    if dpe_min:
        # Filtrer par classe DPE minimale (E, F, G)
        dpe_order = {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6, "G": 7}
        min_value = dpe_order.get(dpe_min, 7)
        valid_classes = [k for k, v in dpe_order.items() if v >= min_value]
        query = query.filter(DPEData.classe_consommation_energie.in_(valid_classes))
    
    results = query.limit(limit).all()
    return results

@app.get("/api/stats/dashboard")
def get_dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Statistiques pour le dashboard"""
    total_prospects = db.query(Prospect).count()
    high_priority = db.query(Prospect).filter(Prospect.priority == "high").count()
    new_prospects = db.query(Prospect).filter(Prospect.status == "new").count()
    avg_score = db.query(Prospect).with_entities(
        db.func.avg(Prospect.score)
    ).scalar() or 0
    
    return {
        "total_prospects": total_prospects,
        "high_priority": high_priority,
        "new_prospects": new_prospects,
        "average_score": round(avg_score, 1)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

# ==================== IMPORT DPE ROUTES ====================
from routes.dpe import router as dpe_router
app.include_router(dpe_router)
# app.include_router(collaboration.router)

# ==================== STARTUP EVENT ====================
@app.on_event("startup")
async def startup_event():
    """Initialise la base de données au démarrage"""
    try:
        from database import init_db
        init_db()
        print("🚀 ProspectScore Pro API démarrée")
    except Exception as e:
        print(f"❌ Erreur initialisation DB: {e}")

# ==================== ADMIN ROUTES ====================
from routes.admin import router as admin_router
app.include_router(admin_router)
# app.include_router(collaboration.router)

# ==================== PROSPECTS ROUTES ====================
from routes.prospects import router as prospects_router
app.include_router(prospects_router)
# app.include_router(collaboration.router)

# ==================== PROSPECTS ROUTES ====================
from routes.prospects import router as prospects_router
app.include_router(prospects_router)
# app.include_router(collaboration.router)

# ==================== PUBLIC ROUTES ====================
from routes.public import router as public_router
app.include_router(public_router)
# app.include_router(collaboration.router)

# ==================== PUBLIC ROUTES ====================
from routes.public import router as public_router
app.include_router(public_router)
# app.include_router(collaboration.router)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.dvf import TransactionDVF
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def calculate_score(t):
    score = 0
    if t.date_mutation:
        years = (datetime.now().date() - t.date_mutation).days / 365.25
        t.duree_detention_estimee = int(years)
        # TOUS les biens ont un score selon leur ancienneté
        if years >= 15: score += 50
        elif years >= 10: score += 45
        elif years >= 7: score += 35
        elif years >= 5: score += 25
        elif years >= 3: score += 15
        else: score += 5
    if t.type_local == "Maison": score += 25
    elif t.type_local == "Appartement": score += 15
    if t.surface_reelle and 70 <= t.surface_reelle <= 200: score += 15
    if t.classe_dpe in ['F', 'G']: score += 10
    return score

def update():
    db = SessionLocal()
    try:
        total = db.query(TransactionDVF).count()
        print(f"{total:,} transactions")
        processed = 0
        while processed < total:
            txs = db.query(TransactionDVF).offset(processed).limit(1000).all()
            if not txs: break
            for t in txs:
                t.score = calculate_score(t)
            db.commit()
            processed += len(txs)
            if processed % 50000 == 0:
                print(f"{processed:,}/{total:,}")
        print("OK!")
    finally:
        db.close()

if __name__ == "__main__":
    update()

import requests
import pandas as pd
from datetime import datetime
from sqlalchemy import text
import logging
import gzip
import io

logger = logging.getLogger(__name__)

class DVFImporter:
    BASE_URL = "https://files.data.gouv.fr/geo-dvf/latest/csv"
    
    def __init__(self, db):
        self.db = db
    
    def download_dvf_data(self, departement: str, year: int = 2024):
        url = f"{self.BASE_URL}/{year}/departements/{departement}.csv.gz"
        logger.info(f"Téléchargement: {url}")
        
        response = requests.get(url, timeout=120)
        response.raise_for_status()
        
        with gzip.open(io.BytesIO(response.content), 'rt', encoding='utf-8') as f:
            df = pd.read_csv(f, low_memory=False)
        
        logger.info(f"✅ {len(df)} lignes téléchargées")
        return df
    
    def clean_and_filter_data(self, df: pd.DataFrame):
        initial = len(df)

        # Normaliser les noms de colonnes (anciens fichiers DVF 2014-2019 vs nouveaux 2020+)
        column_mapping = {
            # Anciens noms → nouveaux noms
            'Id mutation': 'id_mutation',
            'Date mutation': 'date_mutation',
            'No voie': 'adresse_numero',
            'Type de voie': 'type_voie',
            'Voie': 'adresse_nom_voie',
            'Code postal': 'code_postal',
            'Commune': 'nom_commune',
            'Code departement': 'code_departement',
            'Type local': 'type_local',
            'Surface reelle bati': 'surface_reelle_bati',
            'Nombre pieces principales': 'nombre_pieces_principales',
            'Valeur fonciere': 'valeur_fonciere',
            # Garde aussi les nouveaux noms (pour compatibilité 2020+)
            'id_mutation': 'id_mutation',
            'date_mutation': 'date_mutation',
            'adresse_numero': 'adresse_numero',
            'adresse_nom_voie': 'adresse_nom_voie',
            'code_postal': 'code_postal',
            'nom_commune': 'nom_commune',
            'code_departement': 'code_departement',
            'type_local': 'type_local',
            'surface_reelle_bati': 'surface_reelle_bati',
            'nombre_pieces_principales': 'nombre_pieces_principales',
            'valeur_fonciere': 'valeur_fonciere'
        }

        # Renommer les colonnes qui existent
        df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns}, inplace=True)

        # Filtrer par type de bien
        if 'type_local' not in df.columns:
            logger.error(f"Colonnes disponibles: {list(df.columns)[:20]}")
            raise ValueError("Colonne 'type_local' introuvable après normalisation")

        df = df[df['type_local'].isin(['Maison', 'Appartement'])].copy()

        # Filtrer par départements cibles (Seine-Maritime, Somme, Eure, Oise, Calvados, Manche, Orne)
        if 'code_departement' in df.columns:
            target_depts = ['76', '80', '27', '60', '14', '50', '61']
            df = df[df['code_departement'].isin(target_depts)].copy()
            logger.info(f"📍 Filtré par départements {target_depts}: {len(df)} transactions")

        # Convertir les colonnes numériques (dans les anciens fichiers, elles peuvent être des strings)
        if 'valeur_fonciere' in df.columns:
            df['valeur_fonciere'] = pd.to_numeric(df['valeur_fonciere'], errors='coerce')
        if 'surface_reelle_bati' in df.columns:
            df['surface_reelle_bati'] = pd.to_numeric(df['surface_reelle_bati'], errors='coerce')
        if 'nombre_pieces_principales' in df.columns:
            df['nombre_pieces_principales'] = pd.to_numeric(df['nombre_pieces_principales'], errors='coerce')

        df = df[df['valeur_fonciere'].notna() & (df['valeur_fonciere'] > 0)]

        cols = ['id_mutation', 'date_mutation', 'adresse_nom_voie', 'adresse_numero',
                'code_postal', 'nom_commune', 'code_departement', 'type_local',
                'surface_reelle_bati', 'nombre_pieces_principales', 'valeur_fonciere']

        df = df[[c for c in cols if c in df.columns]].copy()
        df.rename(columns={
            'adresse_nom_voie': 'adresse', 'nom_commune': 'commune',
            'code_departement': 'departement', 'surface_reelle_bati': 'surface_reelle',
            'nombre_pieces_principales': 'nombre_pieces'
        }, inplace=True)
        
        if 'adresse_numero' in df.columns:
            df['adresse'] = df['adresse_numero'].astype(str).fillna('') + ' ' + df['adresse'].fillna('')
        
        logger.info(f"Nettoyé: {initial} → {len(df)}")
        return df
    
    def calculate_score(self, surface, type_local):
        score = 30
        if surface and surface > 150:
            score += 20
        elif surface and surface > 100:
            score += 15
        elif surface and surface > 80:
            score += 10
        if type_local == 'Maison':
            score += 10
        return min(score, 100)
    
    def import_to_database(self, df: pd.DataFrame):
        imported = 0
        
        for idx, row in df.iterrows():
            try:
                score = self.calculate_score(row.get('surface_reelle'), row.get('type_local'))
                
                # SQL brut avec ON CONFLICT
                sql = text("""
                    INSERT INTO transactions_dvf 
                    (id_mutation, date_mutation, adresse, code_postal, commune, departement, 
                     type_local, surface_reelle, nombre_pieces, valeur_fonciere, score, created_at, updated_at)
                    VALUES 
                    (:id_mutation, :date_mutation, :adresse, :code_postal, :commune, :departement,
                     :type_local, :surface_reelle, :nombre_pieces, :valeur_fonciere, :score, NOW(), NOW())
                    ON CONFLICT (id_mutation) DO NOTHING
                """)
                
                self.db.execute(sql, {
                    'id_mutation': row['id_mutation'],
                    'date_mutation': pd.to_datetime(row['date_mutation']),
                    'adresse': str(row.get('adresse', ''))[:500],
                    'code_postal': str(row.get('code_postal', ''))[:5],
                    'commune': str(row.get('commune', ''))[:200],
                    'departement': str(row.get('departement', ''))[:3],
                    'type_local': str(row.get('type_local', ''))[:50],
                    'surface_reelle': float(row['surface_reelle']) if pd.notna(row.get('surface_reelle')) else None,
                    'nombre_pieces': int(row['nombre_pieces']) if pd.notna(row.get('nombre_pieces')) else None,
                    'valeur_fonciere': float(row['valeur_fonciere']),
                    'score': score
                })
                
                imported += 1
                
                if imported % 1000 == 0:
                    self.db.commit()
                    logger.info(f"💾 {imported} importées...")
                    
            except Exception as e:
                logger.error(f"Erreur ligne {idx}: {e}")
                continue
        
        self.db.commit()
        logger.info(f"✅ Import terminé: {imported}")
        return {"imported": imported, "skipped": 0, "errors": 0}
    
    def run_import(self, departements: list, years: list = [2024]):
        results = {"departements": {}, "global_imported": 0, "global_skipped": 0, "global_errors": 0}
        
        for dep in departements:
            results["departements"][dep] = {}
            for year in years:
                try:
                    df = self.download_dvf_data(dep, year)
                    df = self.clean_and_filter_data(df)
                    result = self.import_to_database(df)
                    results["departements"][dep][year] = result
                    results["global_imported"] += result["imported"]
                except Exception as e:
                    logger.error(f"Erreur {dep}/{year}: {e}")
                    results["departements"][dep][year] = {"error": str(e)}
        
        return results

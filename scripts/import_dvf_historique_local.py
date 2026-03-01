#!/usr/bin/env python3
"""
Import DVF historique depuis fichiers locaux au format texte (séparateur |)
Filtre sur les départements 76, 27, 80, 60, 14, 62
"""

import sys
import csv
from pathlib import Path
from datetime import datetime
import psycopg2
from psycopg2.extras import execute_batch

# Configuration
DEPARTEMENTS_CIBLES = ['76', '27', '80', '60', '14', '62']
# Pour import rapide juste 76 et 80 : DEPARTEMENTS_CIBLES = ['76', '80']

# Connexion à la base (à adapter selon ton environnement)
DB_CONFIG = {
    'host': 'localhost',  # ou IP du serveur prod
    'port': 5433,
    'database': 'prospectscore',
    'user': 'prospectscore',
    'password': '2aimmobilier2025'
}

def parse_dvf_line(row):
    """Parse une ligne du fichier DVF au format texte avec séparateur |"""
    try:
        # Format ancien DVF avec séparateur pipe
        # Les colonnes principales (ordre peut varier selon l'année)
        id_mutation = row.get('Reference document', '').strip()
        date_mutation = row.get('Date mutation', '').strip()
        valeur_fonciere = row.get('Valeur fonciere', '').strip()
        adresse_numero = row.get('No voie', '').strip()
        type_voie = row.get('Type de voie', '').strip()
        voie = row.get('Voie', '').strip()
        code_postal = row.get('Code postal', '').strip()
        commune = row.get('Commune', '').strip()
        code_departement = row.get('Code departement', '').strip()
        type_local = row.get('Type local', '').strip()
        surface_reelle = row.get('Surface reelle bati', '').strip()
        nombre_pieces = row.get('Nombre pieces principales', '').strip()

        # Filtrage de base
        if not id_mutation or not date_mutation or not valeur_fonciere:
            return None

        # Filtre département
        if code_departement not in DEPARTEMENTS_CIBLES:
            return None

        # Filtre type de bien
        if type_local not in ['Maison', 'Appartement']:
            return None

        # Construction adresse
        adresse_parts = [p for p in [adresse_numero, type_voie, voie] if p]
        adresse = ' '.join(adresse_parts)

        # Conversion valeur foncière
        try:
            valeur = float(valeur_fonciere.replace(',', '.'))
            if valeur <= 0:
                return None
        except (ValueError, AttributeError):
            return None

        # Conversion surface
        try:
            surface = float(surface_reelle.replace(',', '.')) if surface_reelle else None
        except (ValueError, AttributeError):
            surface = None

        # Conversion nombre de pièces
        try:
            pieces = int(nombre_pieces) if nombre_pieces else None
        except (ValueError, AttributeError):
            pieces = None

        return {
            'id_mutation': id_mutation[:50],
            'date_mutation': datetime.strptime(date_mutation, '%d/%m/%Y').date() if '/' in date_mutation else None,
            'adresse': adresse[:500],
            'code_postal': code_postal[:5],
            'commune': commune[:200],
            'departement': code_departement[:3],
            'type_local': type_local[:50],
            'surface_reelle': surface,
            'nombre_pieces': pieces,
            'valeur_fonciere': valeur
        }
    except Exception as e:
        return None

def import_file(filepath, conn):
    """Importe un fichier DVF"""
    print(f"\n📂 Traitement: {filepath.name}")

    imported = 0
    skipped = 0
    batch = []
    batch_size = 1000

    try:
        with open(filepath, 'r', encoding='latin-1') as f:
            # Lecture avec séparateur pipe
            reader = csv.DictReader(f, delimiter='|')

            for i, row in enumerate(reader):
                if i % 10000 == 0 and i > 0:
                    print(f"   📊 {i:,} lignes traitées, {imported:,} importées, {skipped:,} ignorées...")

                parsed = parse_dvf_line(row)
                if parsed:
                    batch.append(parsed)
                else:
                    skipped += 1

                # Import par batch
                if len(batch) >= batch_size:
                    imported += insert_batch(batch, conn)
                    batch = []

            # Derniers éléments
            if batch:
                imported += insert_batch(batch, conn)

        print(f"   ✅ {imported:,} transactions importées, {skipped:,} ignorées")
        return imported

    except Exception as e:
        print(f"   ❌ Erreur: {e}")
        return 0

def insert_batch(batch, conn):
    """Insert un batch de transactions en base"""
    if not batch:
        return 0

    cur = conn.cursor()

    sql = """
        INSERT INTO transactions_dvf
        (id_mutation, date_mutation, adresse, code_postal, commune, departement,
         type_local, surface_reelle, nombre_pieces, valeur_fonciere, created_at, updated_at)
        VALUES (%(id_mutation)s, %(date_mutation)s, %(adresse)s, %(code_postal)s,
                %(commune)s, %(departement)s, %(type_local)s, %(surface_reelle)s,
                %(nombre_pieces)s, %(valeur_fonciere)s, NOW(), NOW())
        ON CONFLICT (id_mutation) DO NOTHING
    """

    try:
        execute_batch(cur, sql, batch)
        conn.commit()
        return len(batch)
    except Exception as e:
        print(f"      ⚠️ Erreur batch: {e}")
        conn.rollback()
        return 0
    finally:
        cur.close()

def main():
    if len(sys.argv) < 2:
        print("Usage: python import_dvf_historique_local.py /chemin/vers/dossier/")
        print("Le dossier doit contenir les fichiers valeursfoncières-YYYY.txt")
        sys.exit(1)

    dossier = Path(sys.argv[1])
    if not dossier.exists():
        print(f"❌ Dossier introuvable: {dossier}")
        sys.exit(1)

    # Connexion à la base
    print("🔌 Connexion à PostgreSQL...")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        print("   ✅ Connecté")
    except Exception as e:
        print(f"   ❌ Erreur de connexion: {e}")
        print("\n💡 Si tu importes sur le serveur prod, modifie DB_CONFIG dans le script")
        sys.exit(1)

    # Recherche des fichiers
    fichiers = sorted(dossier.glob("valeursfoncières-*.txt"))
    if not fichiers:
        print(f"❌ Aucun fichier valeursfoncières-*.txt trouvé dans {dossier}")
        sys.exit(1)

    print(f"\n📋 {len(fichiers)} fichiers trouvés:")
    for f in fichiers:
        print(f"   - {f.name} ({f.stat().st_size / 1024 / 1024:.1f} Mo)")

    print(f"\n🎯 Départements filtrés: {', '.join(DEPARTEMENTS_CIBLES)}")
    input("\n⏸️  Appuie sur ENTRÉE pour démarrer l'import...")

    # Import
    total = 0
    start_time = datetime.now()

    for fichier in fichiers:
        imported = import_file(fichier, conn)
        total += imported

    conn.close()

    duration = (datetime.now() - start_time).total_seconds()
    print(f"\n" + "="*60)
    print(f"✅ IMPORT TERMINÉ")
    print(f"   📊 Total importé: {total:,} transactions")
    print(f"   ⏱️  Durée: {duration/60:.1f} minutes")
    print(f"   🚀 Vitesse: {total/duration:.0f} transactions/seconde")
    print("="*60)

    print("\n🎯 Prochaine étape: calcul des scores de propension")
    print("   curl -X POST 'https://score.2a-immobilier.com/api/admin/calculate-scores'")

if __name__ == '__main__':
    main()

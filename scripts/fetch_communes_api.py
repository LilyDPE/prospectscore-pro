#!/usr/bin/env python3
"""
Script pour récupérer les noms de communes depuis l'API geo.api.gouv.fr
et mettre à jour la table ref_communes
ProspectScore Pro
"""

import psycopg2
import requests
import time
from typing import Dict, List

# Configuration
DB_CONFIG = {
    'host': 'localhost',
    'database': 'prospectscore',
    'user': 'prospectscore',
    'password': 'prospectscore'  # Ajuster si nécessaire
}

API_URL = "https://geo.api.gouv.fr/communes"

def get_commune_name(code_insee: str) -> Dict[str, str]:
    """
    Récupère le nom de la commune depuis l'API geo.api.gouv.fr

    Args:
        code_insee: Code INSEE de la commune (5 caractères)

    Returns:
        Dict avec nom, code_postal, departement
    """
    try:
        response = requests.get(f"{API_URL}/{code_insee}", timeout=5)

        if response.status_code == 200:
            data = response.json()

            # L'API retourne un objet
            nom = data.get('nom', '')
            code_postal = data.get('codesPostaux', [''])[0] if data.get('codesPostaux') else ''
            departement = data.get('codeDepartement', '')

            return {
                'nom': nom,
                'code_postal': code_postal,
                'departement': departement
            }
        else:
            print(f"⚠️  Code INSEE {code_insee} non trouvé (HTTP {response.status_code})")
            return None

    except requests.exceptions.RequestException as e:
        print(f"❌ Erreur API pour {code_insee}: {e}")
        return None

def main():
    print("╔════════════════════════════════════════════════╗")
    print("║   Récupération Noms de Communes (API)         ║")
    print("╚════════════════════════════════════════════════╝")
    print()

    # Connexion à la base
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        print("✓ Connexion PostgreSQL établie")
        print()
    except Exception as e:
        print(f"❌ Erreur connexion PostgreSQL: {e}")
        return

    # Récupérer les codes INSEE sans nom
    cur.execute("""
        SELECT code_insee, code_postal, departement
        FROM ref_communes
        WHERE nom_commune IS NULL
        ORDER BY code_insee
    """)

    codes_a_traiter = cur.fetchall()
    total = len(codes_a_traiter)

    print(f"📊 {total} codes INSEE à traduire")
    print()

    if total == 0:
        print("✓ Tous les codes INSEE sont déjà traduits")
        conn.close()
        return

    # Traiter chaque code INSEE
    success = 0
    failed = 0

    for i, (code_insee, code_postal, departement) in enumerate(codes_a_traiter, 1):
        print(f"[{i}/{total}] {code_insee}... ", end='', flush=True)

        result = get_commune_name(code_insee)

        if result and result['nom']:
            # Mettre à jour la base
            cur.execute("""
                UPDATE ref_communes
                SET nom_commune = %s,
                    code_postal = COALESCE(NULLIF(%s, ''), code_postal),
                    departement = COALESCE(NULLIF(%s, ''), departement)
                WHERE code_insee = %s
            """, (result['nom'], result['code_postal'], result['departement'], code_insee))

            print(f"✓ {result['nom']}")
            success += 1
        else:
            print("❌ Non trouvé")
            failed += 1

        # Commit toutes les 50 requêtes
        if i % 50 == 0:
            conn.commit()
            print(f"  → Progression: {success} réussis, {failed} échoués")

        # Pause pour ne pas surcharger l'API
        time.sleep(0.1)

    # Commit final
    conn.commit()

    print()
    print("╔════════════════════════════════════════════════╗")
    print("║          ✅ TRAITEMENT TERMINÉ                 ║")
    print("╚════════════════════════════════════════════════╝")
    print()
    print(f"📊 Résultat:")
    print(f"   - Réussis: {success}")
    print(f"   - Échoués: {failed}")
    print(f"   - Total: {total}")
    print()

    # Statistiques finales
    cur.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE nom_commune IS NOT NULL) as avec_nom,
            COUNT(*) FILTER (WHERE nom_commune IS NULL) as sans_nom
        FROM ref_communes
    """)

    stats = cur.fetchone()
    print(f"📊 Table ref_communes:")
    print(f"   - Total: {stats[0]}")
    print(f"   - Avec nom: {stats[1]}")
    print(f"   - Sans nom: {stats[2]}")
    print()

    conn.close()

if __name__ == "__main__":
    main()

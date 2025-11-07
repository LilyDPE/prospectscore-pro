#!/usr/bin/env python3
"""
Calcul des Propensity Scores avec Pooling Spatial et Shrinkage EB
ProspectScore Pro - Zone Rurale Compatible
"""

import psycopg2
import numpy as np
from typing import Dict, Tuple
import sys

# Configuration
DB_CONFIG = {
    'host': 'localhost',
    'database': 'prospectscore',
    'user': 'prospectscore',
    'password': 'prospectscore'
}

# Hyperparamètres
N_THRESHOLD = 30  # Seuil pour activer pooling
K_SHRINKAGE = 100  # Force du shrinkage (plus grand = plus de shrinkage)
MONTHS_WINDOW = 36  # Fenêtre temporelle pour considérer ventes récentes

def logit(p):
    """Convert probability to logit"""
    p = np.clip(p, 0.001, 0.999)
    return np.log(p / (1 - p))

def expit(x):
    """Convert logit to probability"""
    return 1 / (1 + np.exp(-x))

def calculate_shrinkage_weight(n_local: float, k: float = K_SHRINKAGE) -> float:
    """
    Calcul du poids de shrinkage (Empirical Bayes)
    w = n_local / (n_local + k)
    """
    return n_local / (n_local + k)

def mixed_p0(p_local: float, n_local: float, p_region: float, k: float = K_SHRINKAGE) -> float:
    """
    Mixture entre base rate locale et régionale
    p0 = w * p_local + (1-w) * p_region
    """
    w = calculate_shrinkage_weight(n_local, k)
    return w * p_local + (1 - w) * p_region

def calculate_base_rates(conn) -> Dict[str, Dict]:
    """
    Calcul des base rates (p0) par département et par density_bin
    """
    cur = conn.cursor()

    print("📊 Calcul des base rates régionales...")

    # Base rate par département
    cur.execute("""
        SELECT
            departement,
            COUNT(*) as total_biens,
            COUNT(*) FILTER (
                WHERE last_transaction_date >= CURRENT_DATE - INTERVAL '36 months'
            ) as ventes_recentes,
            COUNT(*) FILTER (
                WHERE last_transaction_date >= CURRENT_DATE - INTERVAL '36 months'
            )::FLOAT / NULLIF(COUNT(*), 0) as p0_dept
        FROM biens_univers
        WHERE departement IS NOT NULL
        GROUP BY departement
        HAVING COUNT(*) >= 10
    """)

    base_rates_dept = {row[0]: {
        'total': row[1],
        'ventes': row[2],
        'p0': row[3] if row[3] else 0.1
    } for row in cur.fetchall()}

    print(f"   ✓ {len(base_rates_dept)} départements")

    # Base rate par density_bin
    cur.execute("""
        SELECT
            density_bin,
            COUNT(*) as total_biens,
            COUNT(*) FILTER (
                WHERE last_transaction_date >= CURRENT_DATE - INTERVAL '36 months'
            ) as ventes_recentes,
            COUNT(*) FILTER (
                WHERE last_transaction_date >= CURRENT_DATE - INTERVAL '36 months'
            )::FLOAT / NULLIF(COUNT(*), 0) as p0_bin
        FROM biens_univers
        WHERE density_bin != 'UNKNOWN'
        GROUP BY density_bin
        HAVING COUNT(*) >= 10
    """)

    base_rates_bin = {row[0]: {
        'total': row[1],
        'ventes': row[2],
        'p0': row[3] if row[3] else 0.1
    } for row in cur.fetchall()}

    print(f"   ✓ {len(base_rates_bin)} density bins")

    # Base rate globale (fallback)
    cur.execute("""
        SELECT
            COUNT(*) FILTER (
                WHERE last_transaction_date >= CURRENT_DATE - INTERVAL '36 months'
            )::FLOAT / NULLIF(COUNT(*), 0) as p0_global
        FROM biens_univers
    """)

    p0_global = cur.fetchone()[0] or 0.1
    print(f"   ✓ Base rate globale: {p0_global:.3f}")

    cur.close()

    return {
        'departement': base_rates_dept,
        'density_bin': base_rates_bin,
        'global': p0_global
    }

def calculate_odds_ratios(conn, base_rates: Dict) -> Dict[str, float]:
    """
    Calcul des Odds Ratios pour les features principales
    """
    cur = conn.cursor()

    print("📊 Calcul des Odds Ratios...")

    odds_ratios = {}

    # OR pour type_local (MAISON vs APPARTEMENT)
    cur.execute("""
        SELECT
            type_local,
            COUNT(*) FILTER (
                WHERE last_transaction_date >= CURRENT_DATE - INTERVAL '36 months'
            )::FLOAT / NULLIF(COUNT(*), 0) as p_type
        FROM biens_univers
        WHERE type_local IN ('MAISON', 'APPARTEMENT')
        GROUP BY type_local
    """)

    type_rates = {row[0]: row[1] for row in cur.fetchall()}
    if 'MAISON' in type_rates and 'APPARTEMENT' in type_rates:
        odds_maison = type_rates['MAISON'] / (1 - type_rates['MAISON'])
        odds_appart = type_rates['APPARTEMENT'] / (1 - type_rates['APPARTEMENT'])
        odds_ratios['type_maison'] = np.log(odds_maison / odds_appart) if odds_appart > 0 else 0
        print(f"   ✓ OR type_maison: {odds_ratios['type_maison']:.3f}")

    # OR pour density_bin
    p0_ref = base_rates['global']
    for bin_name, bin_data in base_rates['density_bin'].items():
        p_bin = bin_data['p0']
        odds_bin = (p_bin / (1 - p_bin)) / (p0_ref / (1 - p0_ref))
        odds_ratios[f'density_{bin_name}'] = np.log(odds_bin) if odds_bin > 0 else 0

    print(f"   ✓ {len(odds_ratios)} Odds Ratios calculés")

    cur.close()

    return odds_ratios

def calculate_propensity_score(
    bien_data: Dict,
    base_rates: Dict,
    odds_ratios: Dict
) -> Tuple[float, float, str]:
    """
    Calcul du propensity_score pour un bien avec pooling spatial

    Returns:
        (p6_absolute, p6_relative, method_used)
    """
    # Récupérer base rates
    p0_dept = base_rates['departement'].get(bien_data['departement'], {}).get('p0', base_rates['global'])
    p0_bin = base_rates['density_bin'].get(bien_data['density_bin'], {}).get('p0', base_rates['global'])
    p0_global = base_rates['global']

    # Déterminer base rate régionale (moyenne dept + bin)
    p0_region = (p0_dept + p0_bin) / 2

    # Effective n local
    n_local = bien_data.get('effective_n_local', 0)

    # Mixture avec pooling si n_local faible
    if n_local < N_THRESHOLD:
        # Pooling actif : emprunter à la région
        p0_base = mixed_p0(p0_region, n_local, p0_global, K_SHRINKAGE)
        method = 'POOLING'
        w = calculate_shrinkage_weight(n_local, K_SHRINKAGE)
    else:
        # Données locales suffisantes
        p0_base = p0_region
        method = 'LOCAL'
        w = 1.0

    # Convertir en logit
    logit_p0 = logit(p0_base)

    # Appliquer lifts (Odds Ratios) avec shrinkage
    logit_score = logit_p0

    # Feature : type_local
    if bien_data['type_local'] == 'MAISON' and 'type_maison' in odds_ratios:
        lift = odds_ratios['type_maison'] * w  # Shrinkage appliqué
        logit_score += lift

    # Feature : density_bin
    density_key = f"density_{bien_data['density_bin']}"
    if density_key in odds_ratios:
        lift = odds_ratios[density_key] * w
        logit_score += lift

    # Feature : surface (log transform)
    if bien_data['surface_reelle'] and bien_data['surface_reelle'] > 0:
        # Lift pour surface (simulé : +0.2 logit si surface > 100m²)
        if bien_data['surface_reelle'] > 100:
            logit_score += 0.2 * w

    # Convertir back to probability
    p6_absolute = expit(logit_score)

    # Score relatif vs region
    p6_relative = p6_absolute / p0_region if p0_region > 0 else 1.0

    # Normaliser sur échelle 0-100
    propensity_score = int(p6_absolute * 100)

    return propensity_score, p6_relative, method

def main():
    print("╔════════════════════════════════════════════════╗")
    print("║   Calcul Propensity Scores (EB Pooling)       ║")
    print("╚════════════════════════════════════════════════╝")
    print()

    # Connexion
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        print("✓ Connexion PostgreSQL établie")
        print()
    except Exception as e:
        print(f"❌ Erreur connexion : {e}")
        sys.exit(1)

    # Calcul des base rates
    base_rates = calculate_base_rates(conn)

    # Calcul des Odds Ratios
    odds_ratios = calculate_odds_ratios(conn, base_rates)

    print()
    print("📊 Calcul des propensity scores...")

    # Récupérer les biens
    cur = conn.cursor()
    cur.execute("""
        SELECT
            id_bien,
            departement,
            density_bin,
            effective_n_local,
            type_local,
            surface_reelle
        FROM biens_univers
        WHERE density_bin != 'UNKNOWN'
        LIMIT 100000  -- Traiter par batch
    """)

    biens = cur.fetchall()
    total = len(biens)
    print(f"   Traitement de {total} biens...")

    # Traiter chaque bien
    updates = []
    for i, (id_bien, dept, density_bin, n_local, type_local, surface) in enumerate(biens):
        bien_data = {
            'departement': dept,
            'density_bin': density_bin,
            'effective_n_local': n_local or 0,
            'type_local': type_local,
            'surface_reelle': surface
        }

        propensity_score, p6_relative, method = calculate_propensity_score(
            bien_data, base_rates, odds_ratios
        )

        updates.append((propensity_score, method, id_bien))

        if (i + 1) % 10000 == 0:
            print(f"   → {i + 1}/{total} traités")

    # Mise à jour en batch
    print()
    print("📊 Mise à jour de la base...")
    cur.executemany("""
        UPDATE biens_univers
        SET propensity_score = %s,
            propensity_category = CASE
                WHEN %s >= 80 THEN 'TRES_FORT'
                WHEN %s >= 70 THEN 'FORT'
                WHEN %s >= 60 THEN 'MOYEN'
                ELSE 'FAIBLE'
            END,
            features_calculated = TRUE,
            features_calculated_at = CURRENT_TIMESTAMP
        WHERE id_bien = %s
    """, [(score, score, score, score, id_bien) for score, method, id_bien in updates])

    conn.commit()

    print(f"   ✓ {len(updates)} biens mis à jour")
    print()

    # Statistiques finales
    print("📊 Statistiques finales:")
    cur.execute("""
        SELECT
            density_bin,
            COUNT(*) as nb_biens,
            ROUND(AVG(propensity_score), 1) as avg_score,
            COUNT(*) FILTER (WHERE propensity_score >= 70) as score_fort
        FROM biens_univers
        WHERE features_calculated = TRUE
        GROUP BY density_bin
        ORDER BY AVG(propensity_score) DESC
    """)

    for row in cur.fetchall():
        print(f"   {row[0]:15} : {row[1]:6} biens, score moy={row[2]:4.1f}, fort={row[3]}")

    print()
    print("╔════════════════════════════════════════════════╗")
    print("║          ✅ CALCUL TERMINÉ                     ║")
    print("╚════════════════════════════════════════════════╝")

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()

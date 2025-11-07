-- ============================================
-- Calcul des Features de Densité (Spatial)
-- ProspectScore Pro - Zone Rurale Compatible
-- ============================================

-- Étape 1 : Ajouter les colonnes de densité si elles n'existent pas
DO $$
BEGIN
    ALTER TABLE biens_univers ADD COLUMN IF NOT EXISTS density_tx_1km FLOAT DEFAULT 0;
    ALTER TABLE biens_univers ADD COLUMN IF NOT EXISTS density_tx_5km FLOAT DEFAULT 0;
    ALTER TABLE biens_univers ADD COLUMN IF NOT EXISTS density_biens_1km FLOAT DEFAULT 0;
    ALTER TABLE biens_univers ADD COLUMN IF NOT EXISTS effective_n_local FLOAT DEFAULT 0;
    ALTER TABLE biens_univers ADD COLUMN IF NOT EXISTS density_bin VARCHAR(20) DEFAULT 'UNKNOWN';

    RAISE NOTICE '✓ Colonnes de densité ajoutées';
END $$;

-- Étape 2 : Calculer density_tx_1km (nombre de ventes / km² dans rayon 1km)
-- Utilise les transactions DVF des 36 derniers mois
RAISE NOTICE '📊 Calcul density_tx_1km...';

UPDATE biens_univers b
SET density_tx_1km = (
    SELECT COUNT(*)::FLOAT / (PI() * POWER(1.0, 2))  -- area = π * r²
    FROM biens_univers x
    WHERE x.last_transaction_date >= CURRENT_DATE - INTERVAL '36 months'
      AND ST_DWithin(b.geom::geography, x.geom::geography, 1000)  -- 1km
      AND x.id_bien != b.id_bien
)
WHERE b.geom IS NOT NULL
  AND b.latitude IS NOT NULL
  AND b.longitude IS NOT NULL;

-- Étape 3 : Calculer density_tx_5km (rayon 5km pour zones rurales)
RAISE NOTICE '📊 Calcul density_tx_5km...';

UPDATE biens_univers b
SET density_tx_5km = (
    SELECT COUNT(*)::FLOAT / (PI() * POWER(5.0, 2))  -- area = π * r²
    FROM biens_univers x
    WHERE x.last_transaction_date >= CURRENT_DATE - INTERVAL '36 months'
      AND ST_DWithin(b.geom::geography, x.geom::geography, 5000)  -- 5km
      AND x.id_bien != b.id_bien
)
WHERE b.geom IS NOT NULL
  AND b.latitude IS NOT NULL
  AND b.longitude IS NOT NULL;

-- Étape 4 : Calculer density_biens_1km (stock de biens / km²)
RAISE NOTICE '📊 Calcul density_biens_1km...';

UPDATE biens_univers b
SET density_biens_1km = (
    SELECT COUNT(*)::FLOAT / (PI() * POWER(1.0, 2))
    FROM biens_univers x
    WHERE ST_DWithin(b.geom::geography, x.geom::geography, 1000)
      AND x.id_bien != b.id_bien
)
WHERE b.geom IS NOT NULL
  AND b.latitude IS NOT NULL
  AND b.longitude IS NOT NULL;

-- Étape 5 : Calculer effective_n_local avec kernel triangulaire (rayon 5km)
RAISE NOTICE '📊 Calcul effective_n_local (kernel weighting)...';

UPDATE biens_univers b
SET effective_n_local = (
    SELECT SUM(GREATEST(0, 1 - dist_m/5000.0))
    FROM (
        SELECT ST_Distance(b.geom::geography, x.geom::geography) AS dist_m
        FROM biens_univers x
        WHERE ST_DWithin(b.geom::geography, x.geom::geography, 5000)
          AND x.id_bien != b.id_bien
          AND x.last_transaction_date >= CURRENT_DATE - INTERVAL '36 months'
        LIMIT 100  -- Limiter pour performance
    ) distances
)
WHERE b.geom IS NOT NULL
  AND b.latitude IS NOT NULL
  AND b.longitude IS NOT NULL;

-- Étape 6 : Classifier en bins de densité (quintiles)
RAISE NOTICE '📊 Classification en bins de densité...';

WITH density_quantiles AS (
    SELECT
        percentile_cont(0.20) WITHIN GROUP (ORDER BY density_tx_5km) AS q20,
        percentile_cont(0.40) WITHIN GROUP (ORDER BY density_tx_5km) AS q40,
        percentile_cont(0.60) WITHIN GROUP (ORDER BY density_tx_5km) AS q60,
        percentile_cont(0.80) WITHIN GROUP (ORDER BY density_tx_5km) AS q80
    FROM biens_univers
    WHERE density_tx_5km > 0
)
UPDATE biens_univers b
SET density_bin = CASE
    WHEN b.density_tx_5km >= (SELECT q80 FROM density_quantiles) THEN 'URBAIN_DENSE'
    WHEN b.density_tx_5km >= (SELECT q60 FROM density_quantiles) THEN 'URBAIN'
    WHEN b.density_tx_5km >= (SELECT q40 FROM density_quantiles) THEN 'PERIURBAIN'
    WHEN b.density_tx_5km >= (SELECT q20 FROM density_quantiles) THEN 'RURAL'
    ELSE 'RURAL_ISOLE'
END
WHERE b.density_tx_5km > 0;

-- Étape 7 : Créer des index pour performance
CREATE INDEX IF NOT EXISTS idx_biens_univers_density_bin ON biens_univers(density_bin);
CREATE INDEX IF NOT EXISTS idx_biens_univers_last_tx_date ON biens_univers(last_transaction_date);

-- Étape 8 : Statistiques de vérification
RAISE NOTICE '📊 Statistiques finales...';

SELECT
    density_bin,
    COUNT(*) as nb_biens,
    ROUND(AVG(density_tx_1km), 2) as avg_density_tx_1km,
    ROUND(AVG(density_tx_5km), 2) as avg_density_tx_5km,
    ROUND(AVG(effective_n_local), 1) as avg_effective_n_local,
    ROUND(COUNT(*)::NUMERIC / SUM(COUNT(*)) OVER() * 100, 1) as pct
FROM biens_univers
WHERE density_bin != 'UNKNOWN'
GROUP BY density_bin
ORDER BY AVG(density_tx_5km) DESC;

-- ============================================
-- FIN DU SCRIPT
-- ============================================

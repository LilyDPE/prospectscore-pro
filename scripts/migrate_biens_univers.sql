-- ============================================
-- Migration: Vue matérialisée → Table biens_univers
-- ProspectScore Pro
-- ============================================

-- Étape 1 : Vérifier et sauvegarder la vue matérialisée existante
DO $$
BEGIN
    -- Si biens_univers existe comme vue matérialisée
    IF EXISTS (
        SELECT 1 FROM pg_matviews WHERE matviewname = 'biens_univers'
    ) THEN
        RAISE NOTICE '📋 Vue matérialisée biens_univers détectée, migration en cours...';

        -- Renommer la vue matérialisée
        ALTER MATERIALIZED VIEW biens_univers RENAME TO biens_univers_old;
        RAISE NOTICE '✓ Vue matérialisée renommée en biens_univers_old';
    ELSE
        RAISE NOTICE '✓ Pas de vue matérialisée à migrer';
    END IF;
END $$;

-- Étape 2 : Créer la vraie table biens_univers
CREATE TABLE IF NOT EXISTS biens_univers (
    -- Identifiant unique
    id_bien SERIAL PRIMARY KEY,

    -- Informations de base
    adresse VARCHAR(500),
    code_postal VARCHAR(5),
    commune VARCHAR(200),
    departement VARCHAR(3),

    -- Caractéristiques du bien
    type_local VARCHAR(50),
    surface_reelle FLOAT,
    nombre_pieces INTEGER,

    -- Géolocalisation
    latitude FLOAT,
    longitude FLOAT,
    geocode_quality VARCHAR(50),
    geom GEOMETRY(POINT, 4326),

    -- Dernière transaction connue
    last_price FLOAT,
    last_transaction_date TIMESTAMP,

    -- ==================== FEATURES ML ====================

    -- Zone type (4 catégories)
    zone_type VARCHAR(20),

    -- Activité du marché local (rayon 500m, 12 mois)
    local_turnover_12m INTEGER DEFAULT 0,
    sale_density_12m FLOAT DEFAULT 0.0,

    -- Statistiques du marché local
    avg_local_price FLOAT,
    median_local_price FLOAT,
    local_price_evolution FLOAT,

    -- Attractivité de la zone
    zone_attractivity_score FLOAT,

    -- Score de propension à vendre (calculé par le modèle ML)
    propensity_score INTEGER DEFAULT 0,
    propensity_category VARCHAR(20),

    -- Métadonnées
    features_calculated BOOLEAN DEFAULT FALSE,
    features_calculated_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Étape 3 : Copier les données depuis l'ancienne vue matérialisée
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_matviews WHERE matviewname = 'biens_univers_old'
    ) THEN
        RAISE NOTICE '📊 Copie des données depuis biens_univers_old...';

        -- Insérer les données existantes
        INSERT INTO biens_univers (
            adresse, code_postal, commune, departement,
            type_local, surface_reelle, nombre_pieces,
            latitude, longitude, geom,
            created_at, updated_at
        )
        SELECT
            adresse, code_postal, commune, departement,
            type_local, surface_reelle, nombre_pieces,
            latitude, longitude, geom,
            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        FROM biens_univers_old
        ON CONFLICT (id_bien) DO NOTHING;

        RAISE NOTICE '✓ Données copiées avec succès';
    ELSE
        RAISE NOTICE '✓ Pas de données à copier';
    END IF;
END $$;

-- Étape 4 : Créer les index
CREATE INDEX IF NOT EXISTS idx_biens_univers_code_postal ON biens_univers(code_postal);
CREATE INDEX IF NOT EXISTS idx_biens_univers_commune ON biens_univers(commune);
CREATE INDEX IF NOT EXISTS idx_biens_univers_departement ON biens_univers(departement);
CREATE INDEX IF NOT EXISTS idx_biens_univers_type_local ON biens_univers(type_local);
CREATE INDEX IF NOT EXISTS idx_biens_univers_lat ON biens_univers(latitude);
CREATE INDEX IF NOT EXISTS idx_biens_univers_lon ON biens_univers(longitude);
CREATE INDEX IF NOT EXISTS idx_biens_univers_geom ON biens_univers USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_biens_univers_zone_type ON biens_univers(zone_type);
CREATE INDEX IF NOT EXISTS idx_biens_univers_local_turnover ON biens_univers(local_turnover_12m);
CREATE INDEX IF NOT EXISTS idx_biens_univers_sale_density ON biens_univers(sale_density_12m);
CREATE INDEX IF NOT EXISTS idx_biens_univers_propensity_score ON biens_univers(propensity_score);
CREATE INDEX IF NOT EXISTS idx_biens_univers_features_calculated ON biens_univers(features_calculated);
CREATE INDEX IF NOT EXISTS idx_biens_univers_last_price ON biens_univers(last_price);

-- Étape 5 : Créer les triggers
CREATE OR REPLACE FUNCTION update_biens_univers_geom()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.latitude IS NOT NULL AND NEW.longitude IS NOT NULL THEN
        NEW.geom = ST_SetSRID(ST_MakePoint(NEW.longitude, NEW.latitude), 4326);
    END IF;
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_biens_univers_geom ON biens_univers;
CREATE TRIGGER trigger_update_biens_univers_geom
    BEFORE INSERT OR UPDATE ON biens_univers
    FOR EACH ROW
    EXECUTE FUNCTION update_biens_univers_geom();

-- Étape 6 : Créer les vues et fonctions helper
CREATE OR REPLACE VIEW v_biens_univers_stats AS
SELECT
    COUNT(*) as total_biens,
    COUNT(*) FILTER (WHERE features_calculated = TRUE) as biens_avec_features,
    COUNT(*) FILTER (WHERE latitude IS NOT NULL AND longitude IS NOT NULL) as biens_geolocalises,
    COUNT(*) FILTER (WHERE zone_type = 'RURAL_ISOLE') as rural_isole,
    COUNT(*) FILTER (WHERE zone_type = 'RURAL') as rural,
    COUNT(*) FILTER (WHERE zone_type = 'PERIURBAIN') as periurbain,
    COUNT(*) FILTER (WHERE zone_type = 'URBAIN') as urbain,
    AVG(local_turnover_12m) as avg_turnover,
    MAX(local_turnover_12m) as max_turnover,
    AVG(sale_density_12m) as avg_density,
    MAX(sale_density_12m) as max_density,
    AVG(propensity_score) as avg_propensity_score,
    MAX(propensity_score) as max_propensity_score
FROM biens_univers;

CREATE OR REPLACE FUNCTION calculate_zone_type(p_local_turnover INTEGER)
RETURNS VARCHAR(20) AS $$
BEGIN
    IF p_local_turnover >= 20 THEN RETURN 'URBAIN';
    ELSIF p_local_turnover >= 10 THEN RETURN 'PERIURBAIN';
    ELSIF p_local_turnover >= 3 THEN RETURN 'RURAL';
    ELSE RETURN 'RURAL_ISOLE';
    END IF;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

CREATE OR REPLACE FUNCTION calculate_sale_density(
    p_local_turnover INTEGER,
    p_radius_km FLOAT DEFAULT 0.5
)
RETURNS FLOAT AS $$
DECLARE
    v_area_km2 FLOAT;
    v_density FLOAT;
BEGIN
    v_area_km2 := PI() * POWER(p_radius_km, 2);
    v_density := p_local_turnover::FLOAT / v_area_km2;
    v_density := LEAST(v_density / 15.0, 1.0);
    RETURN ROUND(v_density::NUMERIC, 4)::FLOAT;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Étape 7 : Permissions
GRANT ALL PRIVILEGES ON biens_univers TO prospectscore;
GRANT USAGE, SELECT ON SEQUENCE biens_univers_id_bien_seq TO prospectscore;
GRANT SELECT ON v_biens_univers_stats TO prospectscore;

-- Étape 8 : Afficher le résultat
SELECT
    'Migration terminée' as status,
    COUNT(*) as total_biens,
    COUNT(*) FILTER (WHERE latitude IS NOT NULL) as geolocalises,
    COUNT(*) FILTER (WHERE features_calculated = TRUE) as avec_features
FROM biens_univers;

-- ============================================
-- FIN DE LA MIGRATION
-- ============================================

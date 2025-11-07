-- ============================================
-- Table biens_univers avec features ML
-- ProspectScore Pro - Criel-sur-Mer
-- ============================================

-- Activer PostGIS si pas déjà fait
CREATE EXTENSION IF NOT EXISTS postgis;

-- Créer la table biens_univers
CREATE TABLE IF NOT EXISTS biens_univers (
    -- Identifiant unique
    id_bien SERIAL PRIMARY KEY,

    -- Informations de base
    adresse VARCHAR(500),
    code_postal VARCHAR(5),
    commune VARCHAR(200),
    departement VARCHAR(3),

    -- Caractéristiques du bien
    type_local VARCHAR(50),  -- Maison, Appartement, Local, Dépendance
    surface_reelle FLOAT,
    nombre_pieces INTEGER,

    -- Géolocalisation
    latitude FLOAT,
    longitude FLOAT,
    geocode_quality VARCHAR(50),  -- housenumber, street, city
    geom GEOMETRY(POINT, 4326),  -- Point géographique PostGIS

    -- Dernière transaction connue
    last_price FLOAT,
    last_transaction_date TIMESTAMP,

    -- ==================== FEATURES ML ====================

    -- Zone type (4 catégories)
    zone_type VARCHAR(20),  -- RURAL_ISOLE, RURAL, PERIURBAIN, URBAIN

    -- Activité du marché local (rayon 500m, 12 mois)
    local_turnover_12m INTEGER DEFAULT 0,  -- Nombre de ventes
    sale_density_12m FLOAT DEFAULT 0.0,    -- Densité corrigée (0-1)

    -- Statistiques du marché local
    avg_local_price FLOAT,           -- Prix moyen dans la zone
    median_local_price FLOAT,        -- Prix médian dans la zone
    local_price_evolution FLOAT,     -- Évolution prix sur 12 mois (%)

    -- Attractivité de la zone
    zone_attractivity_score FLOAT,   -- Score d'attractivité 0-100

    -- Score de propension à vendre (calculé par le modèle ML)
    propensity_score INTEGER DEFAULT 0,
    propensity_category VARCHAR(20), -- TRES_FORT, FORT, MOYEN, FAIBLE

    -- Métadonnées
    features_calculated BOOLEAN DEFAULT FALSE,
    features_calculated_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- INDEX pour performances
-- ============================================

-- Index de base
CREATE INDEX IF NOT EXISTS idx_biens_univers_code_postal ON biens_univers(code_postal);
CREATE INDEX IF NOT EXISTS idx_biens_univers_commune ON biens_univers(commune);
CREATE INDEX IF NOT EXISTS idx_biens_univers_departement ON biens_univers(departement);
CREATE INDEX IF NOT EXISTS idx_biens_univers_type_local ON biens_univers(type_local);

-- Index pour géolocalisation
CREATE INDEX IF NOT EXISTS idx_biens_univers_lat ON biens_univers(latitude);
CREATE INDEX IF NOT EXISTS idx_biens_univers_lon ON biens_univers(longitude);
CREATE INDEX IF NOT EXISTS idx_biens_univers_geom ON biens_univers USING GIST(geom);

-- Index pour features ML
CREATE INDEX IF NOT EXISTS idx_biens_univers_zone_type ON biens_univers(zone_type);
CREATE INDEX IF NOT EXISTS idx_biens_univers_local_turnover ON biens_univers(local_turnover_12m);
CREATE INDEX IF NOT EXISTS idx_biens_univers_sale_density ON biens_univers(sale_density_12m);
CREATE INDEX IF NOT EXISTS idx_biens_univers_propensity_score ON biens_univers(propensity_score);
CREATE INDEX IF NOT EXISTS idx_biens_univers_features_calculated ON biens_univers(features_calculated);

-- Index pour prix
CREATE INDEX IF NOT EXISTS idx_biens_univers_last_price ON biens_univers(last_price);

-- ============================================
-- TRIGGER pour mettre à jour geom automatiquement
-- ============================================

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

-- ============================================
-- Vue pour statistiques rapides
-- ============================================

CREATE OR REPLACE VIEW v_biens_univers_stats AS
SELECT
    COUNT(*) as total_biens,
    COUNT(*) FILTER (WHERE features_calculated = TRUE) as biens_avec_features,
    COUNT(*) FILTER (WHERE latitude IS NOT NULL AND longitude IS NOT NULL) as biens_geolocalises,

    -- Répartition par zone type
    COUNT(*) FILTER (WHERE zone_type = 'RURAL_ISOLE') as rural_isole,
    COUNT(*) FILTER (WHERE zone_type = 'RURAL') as rural,
    COUNT(*) FILTER (WHERE zone_type = 'PERIURBAIN') as periurbain,
    COUNT(*) FILTER (WHERE zone_type = 'URBAIN') as urbain,

    -- Stats turnover
    AVG(local_turnover_12m) as avg_turnover,
    MAX(local_turnover_12m) as max_turnover,

    -- Stats density
    AVG(sale_density_12m) as avg_density,
    MAX(sale_density_12m) as max_density,

    -- Stats propensity
    AVG(propensity_score) as avg_propensity_score,
    MAX(propensity_score) as max_propensity_score
FROM biens_univers;

-- ============================================
-- Fonction helper : Calculer la zone type
-- ============================================

CREATE OR REPLACE FUNCTION calculate_zone_type(
    p_local_turnover INTEGER
)
RETURNS VARCHAR(20) AS $$
BEGIN
    IF p_local_turnover >= 20 THEN
        RETURN 'URBAIN';
    ELSIF p_local_turnover >= 10 THEN
        RETURN 'PERIURBAIN';
    ELSIF p_local_turnover >= 3 THEN
        RETURN 'RURAL';
    ELSE
        RETURN 'RURAL_ISOLE';
    END IF;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- ============================================
-- Fonction helper : Calculer sale_density corrigée
-- ============================================

CREATE OR REPLACE FUNCTION calculate_sale_density(
    p_local_turnover INTEGER,
    p_radius_km FLOAT DEFAULT 0.5
)
RETURNS FLOAT AS $$
DECLARE
    v_area_km2 FLOAT;
    v_density FLOAT;
BEGIN
    -- Calculer l'aire du cercle en km²
    v_area_km2 := PI() * POWER(p_radius_km, 2);

    -- Densité = nombre de ventes / aire
    v_density := p_local_turnover::FLOAT / v_area_km2;

    -- Normalisation sur une échelle 0-1 (max observé = 0.935 selon vos données)
    -- On considère 15 ventes/km² comme le maximum pratique
    v_density := LEAST(v_density / 15.0, 1.0);

    RETURN ROUND(v_density::NUMERIC, 4)::FLOAT;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- ============================================
-- Grant permissions
-- ============================================

GRANT ALL PRIVILEGES ON biens_univers TO prospectscore;
GRANT USAGE, SELECT ON SEQUENCE biens_univers_id_bien_seq TO prospectscore;
GRANT SELECT ON v_biens_univers_stats TO prospectscore;

-- ============================================
-- Informations
-- ============================================

COMMENT ON TABLE biens_univers IS 'Biens immobiliers de l''univers avec features ML pour le scoring de propension';
COMMENT ON COLUMN biens_univers.zone_type IS 'Classification RURAL_ISOLE / RURAL / PERIURBAIN / URBAIN';
COMMENT ON COLUMN biens_univers.local_turnover_12m IS 'Nombre de ventes dans un rayon de 500m sur 12 mois';
COMMENT ON COLUMN biens_univers.sale_density_12m IS 'Densité de ventes corrigée (0-0.935)';
COMMENT ON COLUMN biens_univers.propensity_score IS 'Score de propension à vendre (0-100)';

-- Afficher les stats
SELECT * FROM v_biens_univers_stats;

-- ============================================
-- FIN DU SCRIPT
-- ============================================

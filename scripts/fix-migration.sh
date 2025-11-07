#!/bin/bash
# Script de migration pour convertir biens_univers de vue matérialisée vers table
# ProspectScore Pro

set -e

# Couleurs
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Migration biens_univers → Table            ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════╝${NC}"
echo ""

# Configuration PostgreSQL
DB_CONTAINER="postgres-prospectscore"
DB_NAME="prospectscore"
DB_USER="prospectscore"
PROJECT_DIR="/var/www/prospectscore-pro"

# Vérifier que le conteneur PostgreSQL tourne
if ! docker ps | grep -q $DB_CONTAINER; then
    echo -e "${RED}❌ Le conteneur PostgreSQL n'est pas démarré${NC}"
    echo -e "${YELLOW}   Lancez: docker-compose up -d db${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Conteneur PostgreSQL trouvé${NC}"
echo ""

# Étape 1 : Vérifier le type de biens_univers
echo -e "${CYAN}📊 1. Vérification de l'objet biens_univers existant...${NC}"
TYPE_CHECK=$(docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -t -c "
    SELECT
        CASE
            WHEN EXISTS (SELECT 1 FROM pg_matviews WHERE matviewname = 'biens_univers') THEN 'MATERIALIZED_VIEW'
            WHEN EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'biens_univers') THEN 'TABLE'
            ELSE 'NONE'
        END;
" | tr -d ' ')

if [[ "$TYPE_CHECK" == "MATERIALIZED_VIEW" ]]; then
    echo -e "${YELLOW}   ⚠️  biens_univers est une vue matérialisée${NC}"
    echo -e "${CYAN}   → Migration nécessaire vers une vraie table${NC}"
    NEED_MIGRATION=true
elif [[ "$TYPE_CHECK" == "TABLE" ]]; then
    echo -e "${GREEN}   ✓ biens_univers est déjà une table${NC}"
    NEED_MIGRATION=false
else
    echo -e "${YELLOW}   ⚠️  biens_univers n'existe pas${NC}"
    NEED_MIGRATION=true
fi
echo ""

# Étape 2 : Migration si nécessaire
if [ "$NEED_MIGRATION" = true ]; then
    echo -e "${CYAN}📋 2. Migration de la vue matérialisée vers table...${NC}"
    docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME < "$PROJECT_DIR/scripts/migrate_biens_univers.sql"
    echo ""
else
    echo -e "${CYAN}📋 2. Ajout des colonnes ML si manquantes...${NC}"

    # Ajouter les colonnes manquantes si elles n'existent pas
    docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME << 'EOF'
DO $$
BEGIN
    -- Colonnes ML
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='biens_univers' AND column_name='zone_type') THEN
        ALTER TABLE biens_univers ADD COLUMN zone_type VARCHAR(20);
        RAISE NOTICE '✓ Colonne zone_type ajoutée';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='biens_univers' AND column_name='local_turnover_12m') THEN
        ALTER TABLE biens_univers ADD COLUMN local_turnover_12m INTEGER DEFAULT 0;
        RAISE NOTICE '✓ Colonne local_turnover_12m ajoutée';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='biens_univers' AND column_name='sale_density_12m') THEN
        ALTER TABLE biens_univers ADD COLUMN sale_density_12m FLOAT DEFAULT 0.0;
        RAISE NOTICE '✓ Colonne sale_density_12m ajoutée';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='biens_univers' AND column_name='propensity_score') THEN
        ALTER TABLE biens_univers ADD COLUMN propensity_score INTEGER DEFAULT 0;
        RAISE NOTICE '✓ Colonne propensity_score ajoutée';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='biens_univers' AND column_name='features_calculated') THEN
        ALTER TABLE biens_univers ADD COLUMN features_calculated BOOLEAN DEFAULT FALSE;
        RAISE NOTICE '✓ Colonne features_calculated ajoutée';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='biens_univers' AND column_name='last_price') THEN
        ALTER TABLE biens_univers ADD COLUMN last_price FLOAT;
        RAISE NOTICE '✓ Colonne last_price ajoutée';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='biens_univers' AND column_name='propensity_category') THEN
        ALTER TABLE biens_univers ADD COLUMN propensity_category VARCHAR(20);
        RAISE NOTICE '✓ Colonne propensity_category ajoutée';
    END IF;
END $$;

-- Créer les index
CREATE INDEX IF NOT EXISTS idx_biens_univers_zone_type ON biens_univers(zone_type);
CREATE INDEX IF NOT EXISTS idx_biens_univers_local_turnover ON biens_univers(local_turnover_12m);
CREATE INDEX IF NOT EXISTS idx_biens_univers_sale_density ON biens_univers(sale_density_12m);
CREATE INDEX IF NOT EXISTS idx_biens_univers_propensity_score ON biens_univers(propensity_score);
CREATE INDEX IF NOT EXISTS idx_biens_univers_features_calculated ON biens_univers(features_calculated);
CREATE INDEX IF NOT EXISTS idx_biens_univers_last_price ON biens_univers(last_price);
EOF
    echo ""
fi

# Étape 3 : Créer les tables commerciaux
echo -e "${CYAN}📋 3. Création des tables commerciaux...${NC}"
docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME << 'EOF'
-- Table commerciaux
CREATE TABLE IF NOT EXISTS commerciaux (
    id SERIAL PRIMARY KEY,
    nom VARCHAR(100) NOT NULL,
    prenom VARCHAR(100) NOT NULL,
    email VARCHAR(200) UNIQUE NOT NULL,
    telephone VARCHAR(20),

    codes_postaux_assignes TEXT[] DEFAULT '{}',
    departements_assignes TEXT[] DEFAULT '{}',

    capacite_max_prospects INTEGER DEFAULT 100,
    min_propensity_score INTEGER DEFAULT 60,

    nombre_prospects_assignes INTEGER DEFAULT 0,
    nombre_mandats_obtenus INTEGER DEFAULT 0,
    taux_conversion_mandat FLOAT DEFAULT 0.0,

    actif BOOLEAN DEFAULT TRUE,
    derniere_assignation TIMESTAMP,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table prospect_assignments
CREATE TABLE IF NOT EXISTS prospect_assignments (
    id SERIAL PRIMARY KEY,
    commercial_id INTEGER REFERENCES commerciaux(id) ON DELETE CASCADE,
    bien_id INTEGER REFERENCES biens_univers(id_bien) ON DELETE CASCADE,

    statut VARCHAR(50) DEFAULT 'NOUVEAU',
    priorite VARCHAR(20) DEFAULT 'MOYENNE',
    propensity_score_at_assignment INTEGER,

    date_assignation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    date_premier_contact TIMESTAMP,
    date_rdv TIMESTAMP,
    date_obtention_mandat TIMESTAMP,

    notes TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(commercial_id, bien_id)
);

-- Index
CREATE INDEX IF NOT EXISTS idx_prospect_assignments_commercial ON prospect_assignments(commercial_id);
CREATE INDEX IF NOT EXISTS idx_prospect_assignments_bien ON prospect_assignments(bien_id);
CREATE INDEX IF NOT EXISTS idx_prospect_assignments_statut ON prospect_assignments(statut);
CREATE INDEX IF NOT EXISTS idx_commerciaux_actif ON commerciaux(actif);
CREATE INDEX IF NOT EXISTS idx_commerciaux_codes_postaux ON commerciaux USING GIN(codes_postaux_assignes);
CREATE INDEX IF NOT EXISTS idx_commerciaux_departements ON commerciaux USING GIN(departements_assignes);

-- Trigger
CREATE OR REPLACE FUNCTION update_commerciaux_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_commerciaux_updated_at ON commerciaux;
CREATE TRIGGER trigger_update_commerciaux_updated_at
    BEFORE UPDATE ON commerciaux
    FOR EACH ROW
    EXECUTE FUNCTION update_commerciaux_updated_at();

-- Permissions
GRANT ALL PRIVILEGES ON commerciaux TO prospectscore;
GRANT ALL PRIVILEGES ON prospect_assignments TO prospectscore;
GRANT USAGE, SELECT ON SEQUENCE commerciaux_id_seq TO prospectscore;
GRANT USAGE, SELECT ON SEQUENCE prospect_assignments_id_seq TO prospectscore;
EOF
echo ""

# Étape 4 : Vérifier les résultats
echo -e "${CYAN}📊 4. Vérification des tables créées...${NC}"
docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME << 'EOF'
SELECT
    COUNT(*) as total_biens,
    COUNT(*) FILTER (WHERE latitude IS NOT NULL) as geolocalises,
    COUNT(*) FILTER (WHERE features_calculated = TRUE) as avec_features,
    COUNT(*) FILTER (WHERE propensity_score >= 70) as forte_probabilite
FROM biens_univers;

SELECT COUNT(*) as nb_commerciaux FROM commerciaux;
SELECT COUNT(*) as nb_assignments FROM prospect_assignments;
EOF
echo ""

# Résumé final
echo -e "${GREEN}╔════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║          ✅ MIGRATION TERMINÉE                  ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}🎯 Prochaine étape :${NC}"
echo "   sudo docker-compose restart backend"
echo "   sudo ./scripts/check_probabilites.sh"
echo ""

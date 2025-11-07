#!/bin/bash
# Script complet pour calculer toutes les features ML
# ProspectScore Pro - Zone Rurale Compatible

set -e

# Couleurs
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Calcul Features ML (Spatial + EB Pooling)   ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════╝${NC}"
echo ""

PROJECT_DIR="/var/www/prospectscore-pro"
cd "$PROJECT_DIR"

DB_CONTAINER="postgres-prospectscore"
DB_NAME="prospectscore"
DB_USER="prospectscore"

# Étape 1 : Calculer les features de densité spatiale
echo -e "${CYAN}📊 Étape 1/3 : Calcul features de densité...${NC}"
echo -e "${YELLOW}   ⚠️  Cela peut prendre 10-30 minutes selon la taille${NC}"
echo ""

docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME < scripts/calculate_density_features.sql
echo ""

# Étape 2 : Calculer les propensity scores avec pooling
echo -e "${CYAN}📊 Étape 2/3 : Calcul propensity scores (EB pooling)...${NC}"
echo ""

# Vérifier Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python3 non trouvé${NC}"
    echo -e "${YELLOW}   Installez: sudo apt-get install python3${NC}"
    exit 1
fi

# Installer dépendances si nécessaire
python3 -m pip install psycopg2-binary numpy --quiet 2>/dev/null || true

# Exécuter le calcul
python3 scripts/calculate_propensity_scores.py
echo ""

# Étape 3 : Calculer zone_type final
echo -e "${CYAN}📊 Étape 3/3 : Calcul zone_type et local_turnover...${NC}"
docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME << 'EOF'
-- Mapper density_bin vers zone_type
UPDATE biens_univers
SET zone_type = CASE
    WHEN density_bin = 'URBAIN_DENSE' THEN 'URBAIN'
    WHEN density_bin = 'URBAIN' THEN 'URBAIN'
    WHEN density_bin = 'PERIURBAIN' THEN 'PERIURBAIN'
    WHEN density_bin = 'RURAL' THEN 'RURAL'
    WHEN density_bin = 'RURAL_ISOLE' THEN 'RURAL_ISOLE'
    ELSE NULL
END
WHERE density_bin != 'UNKNOWN';

-- Calculer local_turnover_12m depuis density_tx_1km
UPDATE biens_univers
SET local_turnover_12m = ROUND((density_tx_1km * PI())::NUMERIC, 0)::INTEGER
WHERE density_tx_1km > 0;

-- Calculer sale_density_12m (normalisé 0-1)
UPDATE biens_univers
SET sale_density_12m = LEAST(density_tx_1km / 15.0, 1.0)
WHERE density_tx_1km > 0;

SELECT COUNT(*) as nb_biens_avec_features
FROM biens_univers
WHERE features_calculated = TRUE;
EOF
echo ""

# Résumé final
echo -e "${GREEN}╔════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║          ✅ CALCUL ML TERMINÉ                   ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════╝${NC}"
echo ""

# Statistiques
echo -e "${CYAN}📊 Statistiques finales :${NC}"
docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME << 'EOF'
SELECT
    zone_type,
    COUNT(*) as nb_biens,
    ROUND(AVG(propensity_score), 1) as avg_propensity,
    ROUND(AVG(local_turnover_12m), 0) as avg_turnover,
    COUNT(*) FILTER (WHERE propensity_score >= 70) as nb_forte_proba
FROM biens_univers
WHERE features_calculated = TRUE
GROUP BY zone_type
ORDER BY AVG(propensity_score) DESC;
EOF
echo ""

echo -e "${BLUE}🎯 Prochaine étape :${NC}"
echo "   sudo ./scripts/check_probabilites.sh"
echo ""

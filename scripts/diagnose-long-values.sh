#!/bin/bash
# Script de diagnostic pour identifier les valeurs trop longues
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
echo -e "${BLUE}║   Diagnostic des Valeurs Trop Longues         ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════╝${NC}"
echo ""

DB_CONTAINER="postgres-prospectscore"
DB_NAME="prospectscore"
DB_USER="prospectscore"

echo -e "${CYAN}📊 Recherche des valeurs problématiques...${NC}"
echo ""

# Vérifier la longueur des communes
echo -e "${CYAN}1. Longueur des communes:${NC}"
docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME << 'EOF'
SELECT
    MAX(LENGTH(commune)) as max_length_commune,
    MIN(LENGTH(commune)) as min_length_commune,
    AVG(LENGTH(commune))::INTEGER as avg_length_commune,
    COUNT(*) FILTER (WHERE LENGTH(commune) > 200) as communes_trop_longues
FROM biens_univers_old
WHERE commune IS NOT NULL;
EOF
echo ""

# Afficher les communes trop longues
echo -e "${CYAN}2. Communes avec LENGTH > 200:${NC}"
docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME << 'EOF'
SELECT
    LEFT(commune, 100) as commune_debut,
    LENGTH(commune) as longueur,
    code_postal,
    departement
FROM biens_univers_old
WHERE LENGTH(commune) > 200
LIMIT 10;
EOF
echo ""

# Vérifier les autres colonnes texte
echo -e "${CYAN}3. Longueur des autres colonnes texte:${NC}"
docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME << 'EOF'
SELECT
    'type_local' as colonne,
    MAX(LENGTH(type_local)) as max_length,
    COUNT(*) FILTER (WHERE LENGTH(type_local) > 50) as trop_longues
FROM biens_univers_old
UNION ALL
SELECT
    'code_postal' as colonne,
    MAX(LENGTH(code_postal)) as max_length,
    COUNT(*) FILTER (WHERE LENGTH(code_postal) > 5) as trop_longues
FROM biens_univers_old
UNION ALL
SELECT
    'departement' as colonne,
    MAX(LENGTH(departement)) as max_length,
    COUNT(*) FILTER (WHERE LENGTH(departement) > 3) as trop_longues
FROM biens_univers_old;
EOF
echo ""

# Vérifier la colonne geocode_quality si elle existe
echo -e "${CYAN}4. Colonnes dans biens_univers:${NC}"
docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME << 'EOF'
SELECT
    column_name,
    data_type,
    character_maximum_length
FROM information_schema.columns
WHERE table_name = 'biens_univers'
  AND data_type LIKE '%char%'
ORDER BY character_maximum_length NULLS LAST;
EOF
echo ""

echo -e "${GREEN}╔════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║          ✅ DIAGNOSTIC TERMINÉ                  ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════╝${NC}"
echo ""

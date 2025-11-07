#!/bin/bash
# Script pour inspecter la structure exacte de biens_univers_old
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
echo -e "${BLUE}║   Inspection Structure biens_univers_old      ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════╝${NC}"
echo ""

DB_CONTAINER="postgres-prospectscore"
DB_NAME="prospectscore"
DB_USER="prospectscore"

# Vérifier que le conteneur PostgreSQL tourne
if ! docker ps | grep -q $DB_CONTAINER; then
    echo -e "${RED}❌ Le conteneur PostgreSQL n'est pas démarré${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Conteneur PostgreSQL trouvé${NC}"
echo ""

# 1. Lister toutes les colonnes de biens_univers_old
echo -e "${CYAN}📊 1. Colonnes dans biens_univers_old:${NC}"
docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME << 'EOF'
SELECT
    column_name,
    data_type,
    character_maximum_length
FROM information_schema.columns
WHERE table_name = 'biens_univers_old'
ORDER BY ordinal_position;
EOF
echo ""

# 2. Compter les enregistrements
echo -e "${CYAN}📊 2. Nombre d'enregistrements:${NC}"
docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME << 'EOF'
SELECT COUNT(*) as total FROM biens_univers_old;
EOF
echo ""

# 3. Exemple de données
echo -e "${CYAN}📊 3. Exemple de 2 lignes de données:${NC}"
docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME << 'EOF'
SELECT * FROM biens_univers_old LIMIT 2;
EOF
echo ""

# 4. Colonnes communes entre les deux
echo -e "${CYAN}📊 4. Colonnes communes biens_univers_old ∩ biens_univers:${NC}"
docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME << 'EOF'
SELECT
    o.column_name,
    o.data_type as type_old,
    n.data_type as type_new
FROM information_schema.columns o
INNER JOIN information_schema.columns n
    ON o.column_name = n.column_name
WHERE o.table_name = 'biens_univers_old'
  AND n.table_name = 'biens_univers'
ORDER BY o.ordinal_position;
EOF
echo ""

echo -e "${GREEN}╔════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║          ✅ INSPECTION TERMINÉE                 ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════╝${NC}"
echo ""

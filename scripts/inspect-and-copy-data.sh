#!/bin/bash
# Script pour inspecter biens_univers_old et copier les données correctement
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
echo -e "${BLUE}║   Inspection et Copie des Données             ║${NC}"
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

# Étape 1 : Inspecter la structure de biens_univers_old
echo -e "${CYAN}📊 1. Structure de biens_univers_old...${NC}"
docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME << 'EOF'
\d+ biens_univers_old
EOF
echo ""

# Étape 2 : Compter les enregistrements
echo -e "${CYAN}📊 2. Nombre d'enregistrements dans biens_univers_old...${NC}"
OLD_COUNT=$(docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM biens_univers_old;" | tr -d ' ')
echo -e "${GREEN}   $OLD_COUNT biens dans biens_univers_old${NC}"
echo ""

# Étape 3 : Obtenir la liste des colonnes communes
echo -e "${CYAN}📊 3. Colonnes communes entre les deux tables...${NC}"
docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME << 'EOF'
SELECT column_name
FROM information_schema.columns
WHERE table_name = 'biens_univers_old'
  AND column_name IN (
    SELECT column_name
    FROM information_schema.columns
    WHERE table_name = 'biens_univers'
  )
ORDER BY column_name;
EOF
echo ""

# Étape 4 : Copier les données avec les colonnes qui existent réellement
echo -e "${CYAN}📊 4. Copie des données...${NC}"
docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME << 'EOF'
-- D'abord vider biens_univers si des données existent
TRUNCATE TABLE biens_univers RESTART IDENTITY CASCADE;

-- Copier les données en utilisant uniquement les colonnes qui existent dans les deux
INSERT INTO biens_univers (
    code_postal,
    commune,
    departement,
    type_local,
    surface_reelle,
    nombre_pieces,
    latitude,
    longitude,
    geom,
    created_at,
    updated_at
)
SELECT
    code_postal,
    commune,
    departement,
    type_local,
    surface_reelle,
    nombre_pieces,
    latitude,
    longitude,
    geom,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
FROM biens_univers_old;

-- Afficher le résultat
SELECT
    COUNT(*) as total_copie,
    COUNT(*) FILTER (WHERE latitude IS NOT NULL) as avec_geoloc,
    COUNT(*) FILTER (WHERE code_postal IS NOT NULL) as avec_code_postal
FROM biens_univers;
EOF
echo ""

# Étape 5 : Vérifier le résultat
echo -e "${CYAN}📊 5. Vérification finale...${NC}"
NEW_COUNT=$(docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM biens_univers;" | tr -d ' ')
echo -e "${GREEN}   $NEW_COUNT biens copiés dans biens_univers${NC}"
echo ""

if [ "$OLD_COUNT" = "$NEW_COUNT" ]; then
    echo -e "${GREEN}✅ Copie réussie : $NEW_COUNT / $OLD_COUNT biens${NC}"
else
    echo -e "${YELLOW}⚠️  Différence : $NEW_COUNT copiés sur $OLD_COUNT disponibles${NC}"
fi
echo ""

# Résumé final
echo -e "${GREEN}╔════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║          ✅ INSPECTION TERMINÉE                 ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}🎯 Prochaine étape :${NC}"
echo "   Les données sont maintenant copiées dans biens_univers"
echo "   Mais les colonnes ML (zone_type, propensity_score, etc.) sont vides"
echo ""
echo -e "${YELLOW}💡 Vous devez maintenant :${NC}"
echo "   1. Importer vos features ML calculées"
echo "   2. Ou lancer le calcul des features ML"
echo ""

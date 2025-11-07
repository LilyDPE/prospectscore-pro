#!/bin/bash
# Script pour copier automatiquement les données en détectant les colonnes
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
echo -e "${BLUE}║   Copie Automatique des Données               ║${NC}"
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

# Étape 1 : Détecter les colonnes communes
echo -e "${CYAN}📊 1. Détection des colonnes communes...${NC}"
COMMON_COLUMNS=$(docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -t -A -c "
SELECT string_agg(column_name, ', ')
FROM (
    SELECT o.column_name
    FROM information_schema.columns o
    INNER JOIN information_schema.columns n
        ON o.column_name = n.column_name
    WHERE o.table_name = 'biens_univers_old'
      AND n.table_name = 'biens_univers'
    ORDER BY o.ordinal_position
) t;
")

if [ -z "$COMMON_COLUMNS" ]; then
    echo -e "${RED}❌ Aucune colonne commune trouvée${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Colonnes communes détectées:${NC}"
echo "   $COMMON_COLUMNS"
echo ""

# Étape 2 : Compter les enregistrements source
OLD_COUNT=$(docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM biens_univers_old;" | tr -d ' ')
echo -e "${CYAN}📊 2. Source: $OLD_COUNT biens dans biens_univers_old${NC}"
echo ""

# Étape 3 : Copier les données
echo -e "${CYAN}📊 3. Copie des données...${NC}"
docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME << EOF
-- Vider la table destination
TRUNCATE TABLE biens_univers RESTART IDENTITY CASCADE;

-- Copier avec les colonnes communes
INSERT INTO biens_univers ($COMMON_COLUMNS)
SELECT $COMMON_COLUMNS
FROM biens_univers_old;

-- Afficher le résultat
SELECT COUNT(*) as total_copie FROM biens_univers;
EOF
echo ""

# Étape 4 : Vérifier le résultat
NEW_COUNT=$(docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM biens_univers;" | tr -d ' ')
echo -e "${CYAN}📊 4. Résultat: $NEW_COUNT biens copiés${NC}"
echo ""

if [ "$OLD_COUNT" = "$NEW_COUNT" ]; then
    echo -e "${GREEN}✅ Copie réussie: $NEW_COUNT / $OLD_COUNT biens${NC}"
else
    echo -e "${YELLOW}⚠️  Différence: $NEW_COUNT copiés sur $OLD_COUNT disponibles${NC}"
fi
echo ""

# Étape 5 : Statistiques détaillées
echo -e "${CYAN}📊 5. Statistiques détaillées:${NC}"
docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME << 'EOF'
SELECT
    COUNT(*) as total_biens,
    COUNT(*) FILTER (WHERE latitude IS NOT NULL) as geolocalises,
    COUNT(*) FILTER (WHERE code_postal IS NOT NULL) as avec_code_postal,
    COUNT(*) FILTER (WHERE commune IS NOT NULL) as avec_commune,
    COUNT(*) FILTER (WHERE departement IS NOT NULL) as avec_departement,
    COUNT(*) FILTER (WHERE type_local IS NOT NULL) as avec_type_local
FROM biens_univers;
EOF
echo ""

# Résumé final
echo -e "${GREEN}╔════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║          ✅ COPIE TERMINÉE                      ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════╝${NC}"
echo ""

if [ "$NEW_COUNT" -gt 0 ]; then
    echo -e "${GREEN}🎉 $NEW_COUNT biens ont été copiés avec succès !${NC}"
    echo ""
    echo -e "${BLUE}🎯 Structure actuelle :${NC}"
    echo "   - Table biens_univers créée avec colonnes ML"
    echo "   - Données de base copiées depuis biens_univers_old"
    echo "   - Colonnes ML (zone_type, propensity_score) vides"
    echo ""
    echo -e "${YELLOW}💡 Prochaines étapes :${NC}"
    echo "   1. Importer vos features ML calculées"
    echo "   2. Ou calculer les features ML avec votre pipeline"
    echo "   3. Puis tester: sudo ./scripts/check_probabilites.sh"
else
    echo -e "${RED}❌ Aucune donnée copiée${NC}"
    echo ""
    echo -e "${YELLOW}💡 Vérification nécessaire :${NC}"
    echo "   sudo ./scripts/inspect-structure.sh"
fi
echo ""

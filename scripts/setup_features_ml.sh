#!/bin/bash
# Script de setup de la table biens_univers et features ML
# ProspectScore Pro - Criel-sur-Mer

set -e

# Couleurs
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   ProspectScore Pro - Setup Features ML       ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════╝${NC}"
echo ""

# Configuration PostgreSQL
DB_CONTAINER="postgres-prospectscore"
DB_NAME="prospectscore"
DB_USER="prospectscore"

# Vérifier que le conteneur PostgreSQL tourne
if ! docker ps | grep -q $DB_CONTAINER; then
    echo -e "${RED}❌ Le conteneur PostgreSQL n'est pas démarré${NC}"
    echo -e "${YELLOW}   Lancez: docker-compose up -d db${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Conteneur PostgreSQL trouvé${NC}"
echo ""

# Exécuter le script SQL de création
echo -e "${BLUE}📋 Création de la table biens_univers...${NC}"

docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME < "$(dirname "$0")/create_biens_univers.sql"

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ Table biens_univers créée avec succès !${NC}"
    echo ""
else
    echo -e "${RED}❌ Erreur lors de la création de la table${NC}"
    exit 1
fi

# Afficher les statistiques
echo -e "${BLUE}📊 Statistiques actuelles:${NC}"
docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -c "SELECT * FROM v_biens_univers_stats;"

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║            ✅ SETUP TERMINÉ                     ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}🎯 Prochaines étapes:${NC}"
echo ""
echo -e "${YELLOW}1. Importer les données biens_univers existantes${NC}"
echo "   (si vous avez déjà calculé les features)"
echo ""
echo -e "${YELLOW}2. Ou calculer les features ML pour vos biens${NC}"
echo "   (script de calcul à venir)"
echo ""
echo -e "${YELLOW}3. Tester l'API Features${NC}"
echo "   curl http://localhost:8003/api/features/"
echo "   curl http://localhost:8003/api/features/stats"
echo ""

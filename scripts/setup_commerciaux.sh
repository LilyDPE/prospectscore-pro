#!/bin/bash
# Script de setup du système de gestion des commerciaux
# ProspectScore Pro

set -e

# Couleurs
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   ProspectScore Pro - Setup Commerciaux       ║${NC}"
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
echo -e "${BLUE}📋 Création des tables commerciaux...${NC}"

docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME < "$(dirname "$0")/create_commerciaux.sql"

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ Tables créées avec succès !${NC}"
    echo ""
else
    echo -e "${RED}❌ Erreur lors de la création des tables${NC}"
    exit 1
fi

# Afficher les statistiques
echo -e "${BLUE}📊 Statistiques actuelles:${NC}"
docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -c "SELECT * FROM v_commerciaux_stats;"

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║            ✅ SETUP TERMINÉ                     ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}🎯 Prochaines étapes:${NC}"
echo ""
echo -e "${YELLOW}1. Créer votre premier commercial${NC}"
echo "   curl -X POST http://localhost:8003/api/admin/commerciaux/ \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"nom\": \"Dupont\", \"prenom\": \"Jean\", \"email\": \"jean@2a.com\", \"codes_postaux_assignes\": [\"76260\"]}'"
echo ""
echo -e "${YELLOW}2. Assigner des prospects${NC}"
echo "   curl -X POST http://localhost:8003/api/admin/commerciaux/1/assign-prospects?nombre_prospects=20"
echo ""
echo -e "${YELLOW}3. Consulter le dashboard${NC}"
echo "   curl http://localhost:8003/api/admin/commerciaux/dashboard/stats"
echo ""
echo -e "${BLUE}📚 Documentation complète: COMMERCIAUX.md${NC}"
echo ""

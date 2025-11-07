#!/bin/bash
# Script pour copier intelligemment les données depuis biens_univers_old
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
echo -e "${BLUE}║   Copie Intelligente des Données              ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════╝${NC}"
echo ""

DB_CONTAINER="postgres-prospectscore"
DB_NAME="prospectscore"
DB_USER="prospectscore"
PROJECT_DIR="/var/www/prospectscore-pro"

# Vérifier que le conteneur PostgreSQL tourne
if ! docker ps | grep -q $DB_CONTAINER; then
    echo -e "${RED}❌ Le conteneur PostgreSQL n'est pas démarré${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Conteneur PostgreSQL trouvé${NC}"
echo ""

# Exécuter le script SQL intelligent
echo -e "${CYAN}📊 Analyse et copie des données...${NC}"
docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME < "$PROJECT_DIR/scripts/smart-copy-data.sql"
echo ""

# Résumé final
echo -e "${GREEN}╔════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║          ✅ COPIE TERMINÉE                      ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════╝${NC}"
echo ""

# Afficher les prochaines étapes
FEATURES_COUNT=$(docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM biens_univers WHERE features_calculated = TRUE;" | tr -d ' ')

if [ "$FEATURES_COUNT" -gt 0 ]; then
    echo -e "${GREEN}🎉 Vous avez $FEATURES_COUNT biens avec features ML calculées !${NC}"
    echo ""
    echo -e "${BLUE}🎯 Prochaine étape :${NC}"
    echo "   sudo ./scripts/check_probabilites.sh"
else
    echo -e "${YELLOW}⚠️  Aucun bien avec features ML calculées${NC}"
    echo ""
    echo -e "${BLUE}💡 Options :${NC}"
    echo "   1. Si vos features ML existent ailleurs, importez-les"
    echo "   2. Ou calculez les features ML avec votre pipeline"
    echo ""
    echo -e "${CYAN}Pour tester le système sans features ML :${NC}"
    echo "   Vous pouvez quand même créer des commerciaux et tester l'API"
    echo "   curl https://score.2a-immobilier.com/api/features/stats"
fi
echo ""

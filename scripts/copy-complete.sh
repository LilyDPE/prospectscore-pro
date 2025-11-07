#!/bin/bash
# Script complet pour copier toutes les données avec traduction des codes INSEE
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
echo -e "${BLUE}║   Copie Complète avec Traduction INSEE        ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════╝${NC}"
echo ""

PROJECT_DIR="/var/www/prospectscore-pro"
cd "$PROJECT_DIR"

# Étape 1 : Copie initiale avec traduction INSEE locale
echo -e "${CYAN}📊 Étape 1/3 : Copie avec traduction INSEE locale...${NC}"
./scripts/copy-with-insee.sh
echo ""

# Étape 2 : Récupérer les noms de communes via l'API
echo -e "${CYAN}📊 Étape 2/3 : Récupération des noms depuis l'API...${NC}"

# Vérifier combien de codes INSEE restent à traduire
CODES_RESTANTS=$(docker exec -i postgres-prospectscore psql -U prospectscore -d prospectscore -t -c "SELECT COUNT(*) FROM ref_communes WHERE nom_commune IS NULL;" | tr -d ' ')

if [ "$CODES_RESTANTS" -gt 0 ]; then
    echo -e "${YELLOW}   $CODES_RESTANTS codes INSEE à traduire via l'API${NC}"
    ./scripts/fetch_communes_api.sh
else
    echo -e "${GREEN}   ✓ Tous les codes INSEE sont déjà traduits${NC}"
fi
echo ""

# Étape 3 : Recopier avec les noms de communes complets
echo -e "${CYAN}📊 Étape 3/3 : Copie finale avec tous les noms traduits...${NC}"
./scripts/copy-with-insee.sh
echo ""

# Statistiques finales
echo -e "${GREEN}╔════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║          ✅ COPIE COMPLÈTE TERMINÉE            ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════╝${NC}"
echo ""

TOTAL=$(docker exec -i postgres-prospectscore psql -U prospectscore -d prospectscore -t -c "SELECT COUNT(*) FROM biens_univers;" | tr -d ' ')

echo -e "${GREEN}🎉 $TOTAL biens copiés au total !${NC}"
echo ""

echo -e "${BLUE}🎯 Amélioration :${NC}"
echo "   - Copie initiale (sans INSEE) : 282,758 biens"
echo "   - Copie complète (avec INSEE)  : $TOTAL biens"
echo "   - Biens récupérés : +$((TOTAL - 282758)) biens"
echo ""

echo -e "${YELLOW}💡 Prochaines étapes :${NC}"
echo "   1. Redémarrer le backend : sudo docker-compose restart backend"
echo "   2. Calculer les features ML (zone_type, propensity_score)"
echo "   3. Vérifier : sudo ./scripts/check_probabilites.sh"
echo ""

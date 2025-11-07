#!/bin/bash
# Script pour récupérer les noms de communes depuis l'API geo.api.gouv.fr
# Version bash sans dépendances Python
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
echo -e "${BLUE}║   Récupération Noms de Communes (API)         ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════╝${NC}"
echo ""

DB_CONTAINER="postgres-prospectscore"
DB_NAME="prospectscore"
DB_USER="prospectscore"

# Vérifier que curl est installé
if ! command -v curl &> /dev/null; then
    echo -e "${RED}❌ curl n'est pas installé${NC}"
    exit 1
fi

if ! command -v jq &> /dev/null; then
    echo -e "${YELLOW}⚠️  jq n'est pas installé, installation...${NC}"
    sudo apt-get update -qq
    sudo apt-get install -y jq -qq
fi

echo -e "${GREEN}✓ Outils disponibles${NC}"
echo ""

# Récupérer les codes INSEE sans nom
echo -e "${CYAN}📊 Récupération des codes INSEE à traduire...${NC}"
CODES_A_TRAITER=$(docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -t -A -c "
SELECT code_insee
FROM ref_communes
WHERE nom_commune IS NULL
ORDER BY code_insee
")

if [ -z "$CODES_A_TRAITER" ]; then
    echo -e "${GREEN}✓ Tous les codes INSEE sont déjà traduits${NC}"
    exit 0
fi

TOTAL=$(echo "$CODES_A_TRAITER" | wc -l)
echo -e "${GREEN}✓ $TOTAL codes INSEE à traduire${NC}"
echo ""

# Traiter chaque code INSEE
SUCCESS=0
FAILED=0
COUNTER=0

while IFS= read -r CODE_INSEE; do
    COUNTER=$((COUNTER + 1))
    echo -ne "[${COUNTER}/${TOTAL}] ${CODE_INSEE}... "

    # Appeler l'API
    API_RESPONSE=$(curl -s "https://geo.api.gouv.fr/communes/${CODE_INSEE}" 2>/dev/null)

    if [ $? -eq 0 ] && [ -n "$API_RESPONSE" ]; then
        # Extraire le nom de la commune avec jq
        NOM_COMMUNE=$(echo "$API_RESPONSE" | jq -r '.nom // empty' 2>/dev/null)
        CODE_POSTAL=$(echo "$API_RESPONSE" | jq -r '.codesPostaux[0] // empty' 2>/dev/null)
        DEPARTEMENT=$(echo "$API_RESPONSE" | jq -r '.codeDepartement // empty' 2>/dev/null)

        if [ -n "$NOM_COMMUNE" ]; then
            # Échapper les apostrophes pour SQL
            NOM_COMMUNE_SQL=$(echo "$NOM_COMMUNE" | sed "s/'/''/g")

            # Mettre à jour la base
            docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -c "
                UPDATE ref_communes
                SET nom_commune = '$NOM_COMMUNE_SQL',
                    code_postal = COALESCE(NULLIF('$CODE_POSTAL', ''), code_postal),
                    departement = COALESCE(NULLIF('$DEPARTEMENT', ''), departement)
                WHERE code_insee = '$CODE_INSEE'
            " > /dev/null 2>&1

            echo -e "${GREEN}✓ $NOM_COMMUNE${NC}"
            SUCCESS=$((SUCCESS + 1))
        else
            echo -e "${RED}❌ Non trouvé${NC}"
            FAILED=$((FAILED + 1))
        fi
    else
        echo -e "${RED}❌ Erreur API${NC}"
        FAILED=$((FAILED + 1))
    fi

    # Progression tous les 50
    if [ $((COUNTER % 50)) -eq 0 ]; then
        echo -e "  ${CYAN}→ Progression: ${SUCCESS} réussis, ${FAILED} échoués${NC}"
    fi

    # Pause pour ne pas surcharger l'API
    sleep 0.1

done <<< "$CODES_A_TRAITER"

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║          ✅ TRAITEMENT TERMINÉ                 ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${BLUE}📊 Résultat:${NC}"
echo "   - Réussis: $SUCCESS"
echo "   - Échoués: $FAILED"
echo "   - Total: $TOTAL"
echo ""

# Statistiques finales
echo -e "${CYAN}📊 Table ref_communes:${NC}"
docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME << 'EOF'
SELECT
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE nom_commune IS NOT NULL) as avec_nom,
    COUNT(*) FILTER (WHERE nom_commune IS NULL) as sans_nom
FROM ref_communes;
EOF
echo ""

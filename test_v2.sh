#!/bin/bash
# Script de test rapide PropensityPredictorV2

echo "======================================================================"
echo "🚀 TEST PROPENSITY PREDICTOR V2"
echo "======================================================================"
echo ""

# Couleurs
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Variables
API_URL="http://localhost:8003"
SCORE_MIN=40
LIMIT=100

echo -e "${BLUE}📋 Configuration :${NC}"
echo "  • API URL: $API_URL"
echo "  • Score minimum: $SCORE_MIN"
echo "  • Limite: $LIMIT transactions"
echo ""

# 1. Vérifier que le backend est accessible
echo -e "${BLUE}🔍 1. Vérification du backend...${NC}"
if curl -s "$API_URL/" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Backend accessible${NC}"
else
    echo -e "${RED}❌ Backend non accessible${NC}"
    echo ""
    echo "Démarrez le backend avec :"
    echo "  cd backend && uvicorn main:app --reload --port 8003"
    echo ""
    exit 1
fi
echo ""

# 2. Statistiques DVF actuelles
echo -e "${BLUE}📊 2. Statistiques DVF actuelles...${NC}"
STATS=$(curl -s "$API_URL/api/admin/dvf/stats" | python3 -m json.tool 2>/dev/null)
if [ $? -eq 0 ]; then
    echo "$STATS"
else
    echo -e "${YELLOW}⚠️  Impossible de récupérer les stats${NC}"
fi
echo ""

# 3. Test V1 (pour comparaison)
echo -e "${BLUE}🔄 3. Test VERSION 1 (référence)...${NC}"
echo "POST $API_URL/api/admin/analyze-propensity?score_min=$SCORE_MIN&limit=$LIMIT"
echo ""

V1_RESULT=$(curl -s -X POST "$API_URL/api/admin/analyze-propensity?score_min=$SCORE_MIN&limit=$LIMIT")
V1_ANALYZED=$(echo "$V1_RESULT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('analyzed', 0))" 2>/dev/null)
V1_HOT=$(echo "$V1_RESULT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('hot_prospects', 0))" 2>/dev/null)
V1_URGENT=$(echo "$V1_RESULT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('urgent', 0))" 2>/dev/null)

if [ ! -z "$V1_ANALYZED" ]; then
    echo -e "${GREEN}✅ V1 terminé :${NC}"
    echo "  • Analysés: $V1_ANALYZED"
    echo "  • HOT (≥75): $V1_HOT"
    echo "  • URGENT (≥90): $V1_URGENT"
else
    echo -e "${RED}❌ Erreur V1${NC}"
fi
echo ""

# 4. Test V2 (nouvelle version)
echo -e "${BLUE}🚀 4. Test VERSION 2 (améliorée)...${NC}"
echo "POST $API_URL/api/admin/analyze-propensity-v2?score_min=$SCORE_MIN&limit=$LIMIT"
echo ""

V2_RESULT=$(curl -s -X POST "$API_URL/api/admin/analyze-propensity-v2?score_min=$SCORE_MIN&limit=$LIMIT")
V2_ANALYZED=$(echo "$V2_RESULT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('analyzed', 0))" 2>/dev/null)
V2_HOT=$(echo "$V2_RESULT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('hot_prospects', 0))" 2>/dev/null)
V2_URGENT=$(echo "$V2_RESULT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('urgent', 0))" 2>/dev/null)

if [ ! -z "$V2_ANALYZED" ]; then
    echo -e "${GREEN}✅ V2 terminé :${NC}"
    echo "  • Analysés: $V2_ANALYZED"
    echo "  • HOT (≥75): $V2_HOT"
    echo "  • URGENT (≥90): $V2_URGENT"

    # Améliorations
    echo ""
    echo -e "${BLUE}🔍 Améliorations détectées :${NC}"
    echo "$V2_RESULT" | python3 -c "import sys, json; data=json.load(sys.stdin); print('\n'.join(['  • ' + i for i in data.get('improvements', [])]))" 2>/dev/null
else
    echo -e "${RED}❌ Erreur V2${NC}"
    echo "$V2_RESULT" | python3 -m json.tool 2>/dev/null
fi
echo ""

# 5. Comparaison V1 vs V2
if [ ! -z "$V1_HOT" ] && [ ! -z "$V2_HOT" ]; then
    echo -e "${BLUE}📊 5. Comparaison V1 vs V2${NC}"
    echo "======================================================================"
    printf "%-20s | %-15s | %-15s | %-15s\n" "Métrique" "V1" "V2" "Différence"
    echo "----------------------------------------------------------------------"

    printf "%-20s | %-15s | %-15s | " "HOT (≥75)" "$V1_HOT" "$V2_HOT"
    DIFF_HOT=$((V2_HOT - V1_HOT))
    if [ $DIFF_HOT -gt 0 ]; then
        echo -e "${GREEN}+$DIFF_HOT${NC}"
    elif [ $DIFF_HOT -lt 0 ]; then
        echo -e "${RED}$DIFF_HOT${NC}"
    else
        echo "0"
    fi

    printf "%-20s | %-15s | %-15s | " "URGENT (≥90)" "$V1_URGENT" "$V2_URGENT"
    DIFF_URGENT=$((V2_URGENT - V1_URGENT))
    if [ $DIFF_URGENT -gt 0 ]; then
        echo -e "${GREEN}+$DIFF_URGENT${NC}"
    elif [ $DIFF_URGENT -lt 0 ]; then
        echo -e "${RED}$DIFF_URGENT${NC}"
    else
        echo "0"
    fi

    echo "======================================================================"
    echo ""

    # Calcul du taux d'amélioration
    if [ $V1_HOT -gt 0 ]; then
        IMPROVEMENT=$(python3 -c "print(f'{(($V2_HOT - $V1_HOT) / $V1_HOT * 100):.1f}')" 2>/dev/null)
        if [ ! -z "$IMPROVEMENT" ]; then
            echo -e "${GREEN}🎯 Amélioration HOT : $IMPROVEMENT%${NC}"
        fi
    fi
fi

# 6. Récupérer quelques prospects HOT
echo ""
echo -e "${BLUE}🔥 6. Top 5 Prospects HOT${NC}"
echo "GET $API_URL/api/admin/prospects-hot?limit=5"
echo ""

PROSPECTS=$(curl -s "$API_URL/api/admin/prospects-hot?limit=5")
if echo "$PROSPECTS" | grep -q "success"; then
    echo "$PROSPECTS" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    prospects = data.get('prospects', [])
    for i, p in enumerate(prospects[:5], 1):
        print(f\"{i}. {p.get('adresse', 'N/A')} - {p.get('commune', 'N/A')}\")
        print(f\"   Score: {p.get('propensity_score', 0)}/100 | Priority: {p.get('contact_priority', 'N/A')}\")
        print(f\"   Timeframe: {p.get('propensity_timeframe', 'N/A')}\")
        print()
except:
    print('Aucun prospect HOT trouvé')
" 2>/dev/null
else
    echo -e "${YELLOW}⚠️  Pas de prospects HOT ou erreur${NC}"
fi

# Résumé
echo ""
echo "======================================================================"
echo -e "${GREEN}✅ TEST TERMINÉ${NC}"
echo "======================================================================"
echo ""
echo "📚 Pour plus d'informations :"
echo "  • Documentation: AMELIORATIONS_PREDICTION.md"
echo "  • Guide: GUIDE_MIGRATION_V2.md"
echo "  • Code: backend/services/propensity_predictor_v2.py"
echo ""
echo "🚀 Pour migrer toutes les données :"
echo "  python scripts/migrate_to_v2.py --dry-run"
echo ""

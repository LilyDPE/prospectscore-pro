#!/bin/bash
# Script pour vérifier les probabilités des biens dans la base
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
echo -e "${BLUE}║   Vérification des Probabilités de Vente      ║${NC}"
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

# 1. Vérifier si la table biens_univers existe
echo -e "${CYAN}📊 1. Vérification table biens_univers...${NC}"
TABLE_EXISTS=$(docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -t -c "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'biens_univers');")

if [[ "$TABLE_EXISTS" == *"t"* ]]; then
    echo -e "${GREEN}   ✓ Table biens_univers existe${NC}"
else
    echo -e "${RED}   ❌ Table biens_univers n'existe pas${NC}"
    echo -e "${YELLOW}   Exécutez: ./scripts/setup_features_ml.sh${NC}"
    exit 1
fi
echo ""

# 2. Compter les biens totaux
echo -e "${CYAN}📊 2. Statistiques générales...${NC}"
docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME << 'EOF'
SELECT
    COUNT(*) as total_biens,
    COUNT(*) FILTER (WHERE features_calculated = TRUE) as biens_avec_features,
    COUNT(*) FILTER (WHERE latitude IS NOT NULL AND longitude IS NOT NULL) as biens_geolocalises,
    ROUND(COUNT(*) FILTER (WHERE features_calculated = TRUE)::NUMERIC / NULLIF(COUNT(*), 0) * 100, 2) as pourcentage_features
FROM biens_univers;
EOF
echo ""

# 3. Distribution par propensity_score
echo -e "${CYAN}📊 3. Distribution des scores de propension...${NC}"
docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME << 'EOF'
SELECT
    CASE
        WHEN propensity_score >= 80 THEN '🔥 TRES FORT (≥80)'
        WHEN propensity_score >= 70 THEN '⭐ FORT (70-79)'
        WHEN propensity_score >= 60 THEN '✅ BON (60-69)'
        WHEN propensity_score >= 50 THEN '👍 MOYEN (50-59)'
        WHEN propensity_score >= 40 THEN '📊 FAIBLE (40-49)'
        ELSE '❌ TRES FAIBLE (<40)'
    END as categorie_score,
    COUNT(*) as nombre_biens,
    ROUND(COUNT(*)::NUMERIC / SUM(COUNT(*)) OVER() * 100, 2) as pourcentage
FROM biens_univers
WHERE features_calculated = TRUE
GROUP BY
    CASE
        WHEN propensity_score >= 80 THEN 1
        WHEN propensity_score >= 70 THEN 2
        WHEN propensity_score >= 60 THEN 3
        WHEN propensity_score >= 50 THEN 4
        WHEN propensity_score >= 40 THEN 5
        ELSE 6
    END
ORDER BY 1;
EOF
echo ""

# 4. Top 10 meilleurs prospects
echo -e "${CYAN}📊 4. TOP 10 des meilleurs prospects...${NC}"
docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME << 'EOF'
SELECT
    id_bien,
    LEFT(adresse, 40) as adresse,
    code_postal,
    LEFT(commune, 20) as commune,
    type_local,
    propensity_score as score,
    zone_type
FROM biens_univers
WHERE features_calculated = TRUE
ORDER BY propensity_score DESC
LIMIT 10;
EOF
echo ""

# 5. Distribution par zone_type
echo -e "${CYAN}📊 5. Distribution par zone géographique...${NC}"
docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME << 'EOF'
SELECT
    zone_type,
    COUNT(*) as nombre_biens,
    ROUND(AVG(propensity_score), 1) as score_moyen,
    MAX(propensity_score) as score_max,
    ROUND(COUNT(*)::NUMERIC / SUM(COUNT(*)) OVER() * 100, 2) as pourcentage
FROM biens_univers
WHERE features_calculated = TRUE
GROUP BY zone_type
ORDER BY COUNT(*) DESC;
EOF
echo ""

# 6. Biens par code postal (top 10)
echo -e "${CYAN}📊 6. TOP 10 codes postaux avec le plus de biens à forte probabilité (≥70)...${NC}"
docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME << 'EOF'
SELECT
    code_postal,
    LEFT(commune, 25) as commune,
    COUNT(*) as nb_biens_score_eleve,
    ROUND(AVG(propensity_score), 1) as score_moyen
FROM biens_univers
WHERE features_calculated = TRUE
  AND propensity_score >= 70
GROUP BY code_postal, commune
ORDER BY COUNT(*) DESC
LIMIT 10;
EOF
echo ""

# 7. Opportunités par département
echo -e "${CYAN}📊 7. Opportunités par département (score ≥ 60)...${NC}"
docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME << 'EOF'
SELECT
    departement,
    COUNT(*) as biens_disponibles,
    COUNT(*) FILTER (WHERE propensity_score >= 80) as score_tres_fort,
    COUNT(*) FILTER (WHERE propensity_score >= 70) as score_fort,
    COUNT(*) FILTER (WHERE propensity_score >= 60) as score_bon,
    ROUND(AVG(propensity_score), 1) as score_moyen
FROM biens_univers
WHERE features_calculated = TRUE
  AND propensity_score >= 60
GROUP BY departement
ORDER BY COUNT(*) DESC
LIMIT 10;
EOF
echo ""

# 8. Vérifier si des prospects sont déjà assignés
echo -e "${CYAN}📊 8. Vérification des assignations existantes...${NC}"
ASSIGNMENTS_TABLE=$(docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -t -c "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'prospect_assignments');")

if [[ "$ASSIGNMENTS_TABLE" == *"t"* ]]; then
    docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME << 'EOF'
SELECT
    COUNT(*) as total_assignations,
    COUNT(*) FILTER (WHERE statut = 'NOUVEAU') as nouveaux,
    COUNT(*) FILTER (WHERE statut = 'EN_COURS') as en_cours,
    COUNT(*) FILTER (WHERE statut = 'CONTACTE') as contactes,
    COUNT(*) FILTER (WHERE statut = 'RDV_PRIS') as rdv_pris,
    COUNT(*) FILTER (WHERE statut = 'MANDAT_OBTENU') as mandats
FROM prospect_assignments;
EOF
else
    echo -e "${YELLOW}   Table prospect_assignments n'existe pas encore${NC}"
    echo -e "${YELLOW}   Exécutez: ./scripts/setup_commerciaux.sh${NC}"
fi
echo ""

# Résumé final
echo -e "${GREEN}╔════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║            ✅ VÉRIFICATION TERMINÉE             ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════╝${NC}"
echo ""

# Recommandations
echo -e "${BLUE}💡 RECOMMANDATIONS :${NC}"
echo ""

# Compter les biens avec score ≥ 70
BIENS_FORTE_PROBABILITE=$(docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM biens_univers WHERE features_calculated = TRUE AND propensity_score >= 70;")

if [ "$BIENS_FORTE_PROBABILITE" -gt 0 ]; then
    echo -e "${GREEN}✅ Vous avez $BIENS_FORTE_PROBABILITE biens avec une forte probabilité de vente (score ≥ 70)${NC}"
    echo ""
    echo -e "${YELLOW}📞 Prochaines étapes suggérées :${NC}"
    echo "   1. Créer vos commerciaux avec leurs zones"
    echo "   2. Assigner automatiquement les meilleurs prospects"
    echo "   3. Les commerciaux recevront les adresses par email"
    echo ""
    echo -e "${CYAN}Exemple :${NC}"
    echo "   curl -X POST http://localhost:8003/api/admin/commerciaux/1/assign-prospects?nombre_prospects=20"
else
    echo -e "${RED}⚠️  Aucun bien avec une probabilité élevée trouvé${NC}"
    echo ""
    echo -e "${YELLOW}📝 Actions nécessaires :${NC}"
    echo "   1. Vérifier que les features ML sont calculées"
    echo "   2. Importer vos données avec propensity_score"
    echo "   3. Ou recalculer les scores de propension"
fi
echo ""

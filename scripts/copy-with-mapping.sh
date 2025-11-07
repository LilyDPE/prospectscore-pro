#!/bin/bash
# Script pour copier les données avec mapping de colonnes
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
echo -e "${BLUE}║   Copie avec Mapping des Colonnes             ║${NC}"
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

# Compter les enregistrements source
OLD_COUNT=$(docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM biens_univers_old;" | tr -d ' ')
echo -e "${CYAN}📊 Source: $OLD_COUNT biens dans biens_univers_old${NC}"
echo ""

# Copier les données avec mapping
echo -e "${CYAN}📊 Copie des données avec mapping...${NC}"
docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME << 'EOF'
-- Vider la table destination
TRUNCATE TABLE biens_univers RESTART IDENTITY CASCADE;

-- Copier avec mapping des colonnes
INSERT INTO biens_univers (
    -- id_bien sera auto-généré par SERIAL
    code_postal,
    commune,
    departement,
    type_local,
    surface_reelle,
    nombre_pieces,
    latitude,
    longitude,
    geom,
    last_price,
    last_transaction_date,
    created_at,
    updated_at
)
SELECT
    code_postal,
    commune,
    departement,
    type_local,
    NULLIF(derniere_surface, 0),  -- Convertir 0 en NULL
    NULLIF(dernier_nb_pieces::INTEGER, 0),  -- Convertir en integer et 0 en NULL
    NULLIF(latitude, 0),  -- Convertir 0 en NULL
    NULLIF(longitude, 0),  -- Convertir 0 en NULL
    geom,
    NULLIF(derniere_valeur, 0),  -- Convertir 0 en NULL
    CASE
        WHEN derniere_vente_date::TEXT = '' THEN NULL
        ELSE derniere_vente_date::TIMESTAMP
    END,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
FROM biens_univers_old
WHERE commune IS NOT NULL  -- Filtrer les lignes invalides
  AND code_postal IS NOT NULL;

-- Afficher le résultat
SELECT
    COUNT(*) as total_copie,
    COUNT(*) FILTER (WHERE latitude IS NOT NULL AND latitude != 0) as geolocalises,
    COUNT(*) FILTER (WHERE surface_reelle IS NOT NULL) as avec_surface,
    COUNT(*) FILTER (WHERE last_price IS NOT NULL) as avec_prix
FROM biens_univers;
EOF
echo ""

# Vérifier le résultat
NEW_COUNT=$(docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM biens_univers;" | tr -d ' ')
echo -e "${CYAN}📊 Résultat: $NEW_COUNT biens copiés${NC}"
echo ""

if [ "$NEW_COUNT" -gt 0 ]; then
    echo -e "${GREEN}✅ Copie réussie: $NEW_COUNT biens${NC}"

    # Statistiques détaillées
    echo ""
    echo -e "${CYAN}📊 Statistiques détaillées:${NC}"
    docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME << 'EOF'
SELECT
    COUNT(*) as total_biens,
    COUNT(*) FILTER (WHERE latitude IS NOT NULL AND latitude != 0 AND longitude IS NOT NULL AND longitude != 0) as geolocalises,
    COUNT(*) FILTER (WHERE code_postal IS NOT NULL) as avec_code_postal,
    COUNT(*) FILTER (WHERE commune IS NOT NULL) as avec_commune,
    COUNT(*) FILTER (WHERE type_local IS NOT NULL) as avec_type,
    COUNT(*) FILTER (WHERE surface_reelle IS NOT NULL) as avec_surface,
    COUNT(*) FILTER (WHERE nombre_pieces IS NOT NULL) as avec_pieces,
    COUNT(*) FILTER (WHERE last_price IS NOT NULL) as avec_prix,
    ROUND(AVG(NULLIF(surface_reelle, 0)), 1) as surface_moyenne,
    ROUND(AVG(NULLIF(last_price, 0)), 0) as prix_moyen
FROM biens_univers;
EOF
    echo ""

    # Top 5 communes
    echo -e "${CYAN}📊 Top 5 communes:${NC}"
    docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME << 'EOF'
SELECT
    commune,
    COUNT(*) as nb_biens
FROM biens_univers
WHERE commune IS NOT NULL
GROUP BY commune
ORDER BY COUNT(*) DESC
LIMIT 5;
EOF
    echo ""
else
    echo -e "${RED}❌ Aucune donnée copiée${NC}"
fi

# Résumé final
echo -e "${GREEN}╔════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║          ✅ COPIE TERMINÉE                      ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════╝${NC}"
echo ""

if [ "$NEW_COUNT" -gt 500000 ]; then
    echo -e "${GREEN}🎉 $NEW_COUNT biens copiés avec succès !${NC}"
    echo ""
    echo -e "${BLUE}🎯 Structure actuelle :${NC}"
    echo "   - Données de base : code_postal, commune, latitude, longitude, geom"
    echo "   - Caractéristiques : type_local, surface_reelle, nombre_pieces"
    echo "   - Prix : last_price, last_transaction_date"
    echo "   - Colonnes ML : zone_type, propensity_score (vides pour l'instant)"
    echo ""
    echo -e "${YELLOW}💡 Prochaines étapes :${NC}"
    echo "   1. Calculer les features ML (zone_type, local_turnover, propensity_score)"
    echo "   2. Ou importer les features ML si déjà calculées"
    echo "   3. Puis vérifier: sudo ./scripts/check_probabilites.sh"
    echo ""
    echo -e "${CYAN}Pour tester l'API maintenant :${NC}"
    echo "   curl https://score.2a-immobilier.com/api/features/stats"
else
    echo -e "${YELLOW}⚠️  Seulement $NEW_COUNT biens copiés sur $OLD_COUNT disponibles${NC}"
fi
echo ""

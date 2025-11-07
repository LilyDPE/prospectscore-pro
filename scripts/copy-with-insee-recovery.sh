#!/bin/bash
# Script pour copier TOUS les biens en récupérant les codes postaux depuis ref_communes
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
echo -e "${BLUE}║   Copie Complète avec Récupération INSEE      ║${NC}"
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

# Analyser les données
echo -e "${CYAN}📊 Analyse des données...${NC}"
docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME << 'EOF'
SELECT
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE commune LIKE '[%') as avec_code_insee,
    COUNT(*) FILTER (WHERE code_postal IS NULL OR code_postal = '') as sans_code_postal,
    COUNT(*) FILTER (WHERE commune LIKE '[%' AND (code_postal IS NULL OR code_postal = '')) as insee_et_sans_cp
FROM biens_univers_old;
EOF
echo ""

# Copier TOUS les biens en utilisant ref_communes pour compléter
echo -e "${CYAN}📊 Copie complète avec récupération codes postaux...${NC}"
docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME << 'EOF'
-- Vider la table destination
TRUNCATE TABLE biens_univers RESTART IDENTITY CASCADE;

-- Copier TOUS les biens en utilisant ref_communes
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
    last_price,
    last_transaction_date,
    created_at,
    updated_at
)
SELECT
    -- Code postal : utiliser celui de ref_communes si le bien n'en a pas
    CASE
        WHEN o.code_postal IS NOT NULL AND o.code_postal != '' THEN
            LEFT(o.code_postal, 5)
        WHEN o.commune LIKE '[%' AND r.code_postal IS NOT NULL THEN
            r.code_postal  -- Récupérer depuis ref_communes
        ELSE
            LEFT(COALESCE(o.departement, '00') || '000', 5)  -- Fallback
    END,

    -- Commune : traduire le code INSEE
    CASE
        WHEN o.commune LIKE '[%' THEN
            COALESCE(
                r.nom_commune,  -- Nom trouvé dans ref_communes
                'Commune ' || TRIM(BOTH '[]''' FROM o.commune)  -- Fallback avec code INSEE
            )
        WHEN LENGTH(o.commune) > 200 THEN LEFT(o.commune, 200)
        ELSE o.commune
    END,

    -- Département
    LEFT(COALESCE(o.departement, '00'), 3),

    -- Type local
    CASE
        WHEN o.type_local IN ('MAISON', 'APPARTEMENT', 'DEPENDANCE', 'LOCAL') THEN o.type_local
        ELSE 'AUTRE'
    END,

    -- Surface
    CASE
        WHEN o.derniere_surface > 0 AND o.derniere_surface < 10000 THEN o.derniere_surface
        ELSE NULL
    END,

    -- Nombre de pièces
    CASE
        WHEN o.dernier_nb_pieces::TEXT ~ '^\d+$' THEN NULLIF(o.dernier_nb_pieces::INTEGER, 0)
        ELSE NULL
    END,

    -- Latitude
    CASE
        WHEN o.latitude != 0 AND o.latitude BETWEEN -90 AND 90 THEN o.latitude
        ELSE NULL
    END,

    -- Longitude
    CASE
        WHEN o.longitude != 0 AND o.longitude BETWEEN -180 AND 180 THEN o.longitude
        ELSE NULL
    END,

    -- Geom
    o.geom,

    -- Prix
    CASE
        WHEN o.derniere_valeur > 0 AND o.derniere_valeur < 100000000 THEN o.derniere_valeur
        ELSE NULL
    END,

    -- Date de vente
    CASE
        WHEN o.derniere_vente_date::TEXT != '' AND o.derniere_vente_date::TEXT != '0' THEN
            CASE
                WHEN o.derniere_vente_date::TEXT ~ '^\d{4}-\d{2}-\d{2}' THEN o.derniere_vente_date::TIMESTAMP
                ELSE NULL
            END
        ELSE NULL
    END,

    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
FROM biens_univers_old o
LEFT JOIN ref_communes r ON (
    o.commune LIKE '[%'
    AND TRIM(BOTH '[]''' FROM o.commune) = r.code_insee
)
WHERE o.departement IS NOT NULL;  -- Seule condition : avoir un département

-- Afficher le résultat
SELECT
    COUNT(*) as total_copie,
    COUNT(*) FILTER (WHERE commune LIKE 'Commune %') as codes_insee_non_traduits,
    COUNT(*) FILTER (WHERE commune NOT LIKE 'Commune %') as avec_nom_commune,
    COUNT(*) FILTER (WHERE latitude IS NOT NULL AND latitude != 0) as geolocalises,
    COUNT(*) FILTER (WHERE surface_reelle IS NOT NULL) as avec_surface,
    COUNT(*) FILTER (WHERE last_price IS NOT NULL) as avec_prix
FROM biens_univers;
EOF
echo ""

# Statistiques finales
NEW_COUNT=$(docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM biens_univers;" | tr -d ' ')
echo -e "${CYAN}📊 Résultat: $NEW_COUNT biens copiés${NC}"
echo ""

echo -e "${CYAN}📊 Statistiques détaillées:${NC}"
docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME << 'EOF'
SELECT
    COUNT(*) as total_biens,
    COUNT(*) FILTER (WHERE commune LIKE 'Commune %') as codes_insee_non_traduits,
    ROUND(COUNT(*) FILTER (WHERE commune NOT LIKE 'Commune %')::NUMERIC / COUNT(*) * 100, 1) as pct_noms_valides,
    COUNT(*) FILTER (WHERE latitude IS NOT NULL AND latitude != 0) as geolocalises,
    COUNT(*) FILTER (WHERE surface_reelle IS NOT NULL) as avec_surface,
    COUNT(*) FILTER (WHERE last_price IS NOT NULL) as avec_prix
FROM biens_univers;
EOF
echo ""

# Top 10 communes
echo -e "${CYAN}📊 Top 10 communes:${NC}"
docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME << 'EOF'
SELECT
    commune,
    code_postal,
    COUNT(*) as nb_biens
FROM biens_univers
WHERE commune IS NOT NULL
GROUP BY commune, code_postal
ORDER BY COUNT(*) DESC
LIMIT 10;
EOF
echo ""

# Résumé final
echo -e "${GREEN}╔════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║          ✅ COPIE TERMINÉE                      ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${GREEN}🎉 $NEW_COUNT biens copiés !${NC}"
echo ""

echo -e "${BLUE}🎯 Amélioration :${NC}"
echo "   - Copie précédente (filtre code_postal) : 282,758 biens"
echo "   - Copie nouvelle (récupération INSEE)   : $NEW_COUNT biens"
echo "   - Biens récupérés : +$((NEW_COUNT - 282758)) biens"
echo ""

echo -e "${YELLOW}💡 Prochaines étapes :${NC}"
echo "   1. Redémarrer le backend : sudo docker-compose restart backend"
echo "   2. Calculer les features ML"
echo "   3. Vérifier : sudo ./scripts/check_probabilites.sh"
echo ""

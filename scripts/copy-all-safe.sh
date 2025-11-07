#!/bin/bash
# Script pour copier TOUS les biens avec troncature de sécurité
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
echo -e "${BLUE}║   Copie Sécurisée de Tous les Biens           ║${NC}"
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

# Copier TOUS les biens avec troncature systématique
echo -e "${CYAN}📊 Copie avec troncature de sécurité...${NC}"
docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME << 'EOF'
-- Vider la table destination
TRUNCATE TABLE biens_univers RESTART IDENTITY CASCADE;

-- Copier TOUS les biens avec troncature
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
    -- Code postal : max 5 caractères
    LEFT(COALESCE(
        NULLIF(o.code_postal, ''),
        o.departement || '000'
    ), 5),

    -- Commune : max 200 caractères avec traduction INSEE
    LEFT(
        CASE
            WHEN o.commune LIKE '[%' THEN
                COALESCE(
                    r.nom_commune,
                    'Commune ' || TRIM(BOTH '[]''' FROM o.commune)
                )
            ELSE o.commune
        END,
        200  -- TRONCATURE À 200
    ),

    -- Département : max 3 caractères
    LEFT(COALESCE(o.departement, '00'), 3),

    -- Type local : max 50 caractères
    LEFT(
        CASE
            WHEN o.type_local IN ('MAISON', 'APPARTEMENT', 'DEPENDANCE', 'LOCAL') THEN o.type_local
            ELSE 'AUTRE'
        END,
        50
    ),

    -- Surface : validation
    CASE
        WHEN o.derniere_surface > 0 AND o.derniere_surface < 10000 THEN o.derniere_surface
        ELSE NULL
    END,

    -- Nombre de pièces : validation
    CASE
        WHEN o.dernier_nb_pieces::TEXT ~ '^\d+$' AND o.dernier_nb_pieces::INTEGER BETWEEN 1 AND 50
            THEN o.dernier_nb_pieces::INTEGER
        ELSE NULL
    END,

    -- Latitude : validation
    CASE
        WHEN o.latitude BETWEEN -90 AND 90 AND o.latitude != 0 THEN o.latitude
        ELSE NULL
    END,

    -- Longitude : validation
    CASE
        WHEN o.longitude BETWEEN -180 AND 180 AND o.longitude != 0 THEN o.longitude
        ELSE NULL
    END,

    -- Geom
    o.geom,

    -- Prix : validation
    CASE
        WHEN o.derniere_valeur > 0 AND o.derniere_valeur < 100000000 THEN o.derniere_valeur
        ELSE NULL
    END,

    -- Date de vente : validation
    CASE
        WHEN o.derniere_vente_date::TEXT ~ '^\d{4}-\d{2}-\d{2}' THEN
            o.derniere_vente_date::TIMESTAMP
        ELSE NULL
    END,

    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
FROM biens_univers_old o
LEFT JOIN ref_communes r ON (
    o.commune LIKE '[%'
    AND TRIM(BOTH '[]''' FROM o.commune) = r.code_insee
)
WHERE o.departement IS NOT NULL
  AND LENGTH(o.departement) <= 3;  -- Sécurité supplémentaire

-- Afficher le résultat
SELECT
    COUNT(*) as total_copie,
    COUNT(*) FILTER (WHERE commune LIKE 'Commune %') as codes_insee_non_traduits,
    COUNT(*) FILTER (WHERE commune NOT LIKE 'Commune %') as avec_nom_commune,
    COUNT(*) FILTER (WHERE latitude IS NOT NULL) as geolocalises,
    COUNT(*) FILTER (WHERE surface_reelle IS NOT NULL) as avec_surface,
    COUNT(*) FILTER (WHERE last_price IS NOT NULL) as avec_prix
FROM biens_univers;
EOF
echo ""

# Statistiques finales
NEW_COUNT=$(docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM biens_univers;" | tr -d ' ')
echo -e "${CYAN}📊 Résultat: $NEW_COUNT biens copiés${NC}"
echo ""

if [ "$NEW_COUNT" -gt 0 ]; then
    echo -e "${CYAN}📊 Statistiques détaillées:${NC}"
    docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME << 'EOF'
SELECT
    COUNT(*) as total_biens,
    COUNT(*) FILTER (WHERE commune LIKE 'Commune %') as codes_insee_non_traduits,
    ROUND(COUNT(*) FILTER (WHERE commune NOT LIKE 'Commune %')::NUMERIC / NULLIF(COUNT(*), 0) * 100, 1) as pct_noms_valides,
    COUNT(*) FILTER (WHERE latitude IS NOT NULL) as geolocalises,
    ROUND(COUNT(*) FILTER (WHERE latitude IS NOT NULL)::NUMERIC / NULLIF(COUNT(*), 0) * 100, 1) as pct_geoloc,
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

    # Répartition par type
    echo -e "${CYAN}📊 Répartition par type:${NC}"
    docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME << 'EOF'
SELECT
    type_local,
    COUNT(*) as nb_biens,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) as pourcentage
FROM biens_univers
GROUP BY type_local
ORDER BY COUNT(*) DESC;
EOF
    echo ""
fi

# Résumé final
echo -e "${GREEN}╔════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║          ✅ COPIE TERMINÉE                      ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════╝${NC}"
echo ""

if [ "$NEW_COUNT" -gt 500000 ]; then
    echo -e "${GREEN}🎉 $NEW_COUNT biens copiés avec succès !${NC}"
    echo ""
    echo -e "${BLUE}🎯 Amélioration majeure :${NC}"
    echo "   - Copie précédente : 282,758 biens (47%)"
    echo "   - Copie complète   : $NEW_COUNT biens ($(echo "scale=1; $NEW_COUNT * 100 / $OLD_COUNT" | bc)%)"
    echo "   - Biens récupérés  : +$((NEW_COUNT - 282758)) biens"
else
    echo -e "${YELLOW}⚠️  $NEW_COUNT biens copiés sur $OLD_COUNT disponibles${NC}"
fi
echo ""

echo -e "${YELLOW}💡 Prochaines étapes :${NC}"
echo "   1. Redémarrer le backend : sudo docker-compose restart backend"
echo "   2. Calculer les features ML (zone_type, propensity_score)"
echo "   3. Vérifier : sudo ./scripts/check_probabilites.sh"
echo ""

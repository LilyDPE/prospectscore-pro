#!/bin/bash
# Script pour copier les données avec nettoyage et validation
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
echo -e "${BLUE}║   Copie avec Nettoyage des Données            ║${NC}"
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

# Analyser les données problématiques
echo -e "${CYAN}📊 Analyse des données problématiques...${NC}"
docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME << 'EOF'
-- Compter les communes invalides
SELECT
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE commune LIKE '[%') as communes_invalides,
    COUNT(*) FILTER (WHERE LENGTH(commune) > 200) as communes_trop_longues,
    COUNT(*) FILTER (WHERE code_postal IS NULL OR code_postal = '') as sans_code_postal
FROM biens_univers_old;
EOF
echo ""

# Copier les données avec nettoyage
echo -e "${CYAN}📊 Copie des données avec nettoyage...${NC}"
docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME << 'EOF'
-- Vider la table destination
TRUNCATE TABLE biens_univers RESTART IDENTITY CASCADE;

-- Copier avec mapping et nettoyage
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
    -- Code postal nettoyé (prendre les 5 premiers caractères)
    LEFT(COALESCE(code_postal, departement || '000'), 5),

    -- Commune nettoyée (ignorer les valeurs comme ['76481'])
    CASE
        WHEN commune LIKE '[%' THEN NULL  -- Ignorer les tableaux JSON
        WHEN LENGTH(commune) > 200 THEN LEFT(commune, 200)  -- Tronquer
        ELSE commune
    END,

    -- Département nettoyé
    LEFT(COALESCE(departement, '00'), 3),

    -- Type local nettoyé
    CASE
        WHEN type_local IN ('MAISON', 'APPARTEMENT', 'DEPENDANCE', 'LOCAL') THEN type_local
        ELSE 'AUTRE'
    END,

    -- Surface (convertir 0 en NULL)
    CASE
        WHEN derniere_surface > 0 AND derniere_surface < 10000 THEN derniere_surface
        ELSE NULL
    END,

    -- Nombre de pièces (convertir en integer, 0 en NULL)
    CASE
        WHEN dernier_nb_pieces::TEXT ~ '^\d+$' THEN NULLIF(dernier_nb_pieces::INTEGER, 0)
        ELSE NULL
    END,

    -- Latitude (convertir 0 en NULL, valider plage)
    CASE
        WHEN latitude != 0 AND latitude BETWEEN -90 AND 90 THEN latitude
        ELSE NULL
    END,

    -- Longitude (convertir 0 en NULL, valider plage)
    CASE
        WHEN longitude != 0 AND longitude BETWEEN -180 AND 180 THEN longitude
        ELSE NULL
    END,

    -- Geom
    geom,

    -- Prix (convertir 0 en NULL, valider plage)
    CASE
        WHEN derniere_valeur > 0 AND derniere_valeur < 100000000 THEN derniere_valeur
        ELSE NULL
    END,

    -- Date de vente
    CASE
        WHEN derniere_vente_date::TEXT != '' AND derniere_vente_date::TEXT != '0' THEN
            CASE
                WHEN derniere_vente_date::TEXT ~ '^\d{4}-\d{2}-\d{2}' THEN derniere_vente_date::TIMESTAMP
                ELSE NULL
            END
        ELSE NULL
    END,

    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
FROM biens_univers_old
WHERE code_postal IS NOT NULL
  AND code_postal != ''
  AND departement IS NOT NULL
  AND NOT (commune LIKE '[%');  -- Exclure les communes invalides

-- Afficher le résultat
SELECT
    COUNT(*) as total_copie,
    COUNT(*) FILTER (WHERE latitude IS NOT NULL AND latitude != 0) as geolocalises,
    COUNT(*) FILTER (WHERE surface_reelle IS NOT NULL) as avec_surface,
    COUNT(*) FILTER (WHERE last_price IS NOT NULL) as avec_prix,
    COUNT(*) FILTER (WHERE commune IS NOT NULL) as avec_commune
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
    COUNT(*) FILTER (WHERE latitude IS NOT NULL AND latitude != 0 AND longitude IS NOT NULL AND longitude != 0) as geolocalises_valides,
    ROUND(COUNT(*) FILTER (WHERE latitude IS NOT NULL AND latitude != 0)::NUMERIC / COUNT(*) * 100, 1) as pct_geolocalises,
    COUNT(*) FILTER (WHERE code_postal IS NOT NULL) as avec_code_postal,
    COUNT(*) FILTER (WHERE commune IS NOT NULL) as avec_commune,
    COUNT(*) FILTER (WHERE type_local IS NOT NULL) as avec_type,
    COUNT(*) FILTER (WHERE surface_reelle IS NOT NULL) as avec_surface,
    COUNT(*) FILTER (WHERE nombre_pieces IS NOT NULL) as avec_pieces,
    COUNT(*) FILTER (WHERE last_price IS NOT NULL) as avec_prix
FROM biens_univers;

-- Stats moyennes
SELECT
    ROUND(AVG(NULLIF(surface_reelle, 0)), 1) as surface_moyenne,
    ROUND(AVG(NULLIF(last_price, 0)), 0) as prix_moyen,
    ROUND(AVG(NULLIF(nombre_pieces, 0)), 1) as pieces_moyennes
FROM biens_univers;
EOF
    echo ""

    # Top 5 communes
    echo -e "${CYAN}📊 Top 5 communes:${NC}"
    docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME << 'EOF'
SELECT
    commune,
    code_postal,
    COUNT(*) as nb_biens
FROM biens_univers
WHERE commune IS NOT NULL
GROUP BY commune, code_postal
ORDER BY COUNT(*) DESC
LIMIT 5;
EOF
    echo ""

    # Types de biens
    echo -e "${CYAN}📊 Répartition par type:${NC}"
    docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME << 'EOF'
SELECT
    type_local,
    COUNT(*) as nb_biens,
    ROUND(COUNT(*)::NUMERIC / SUM(COUNT(*)) OVER() * 100, 1) as pourcentage
FROM biens_univers
GROUP BY type_local
ORDER BY COUNT(*) DESC;
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
    echo "   - Données de base : code_postal, commune, departement"
    echo "   - Géolocalisation : latitude, longitude, geom"
    echo "   - Caractéristiques : type_local, surface_reelle, nombre_pieces"
    echo "   - Prix : last_price, last_transaction_date"
    echo "   - Colonnes ML : zone_type, propensity_score (vides)"
    echo ""
    echo -e "${YELLOW}💡 Prochaines étapes :${NC}"
    echo "   1. Calculer les features ML (zone_type, propensity_score, etc.)"
    echo "   2. Puis vérifier: sudo ./scripts/check_probabilites.sh"
    echo ""
    echo -e "${CYAN}Pour tester l'API maintenant :${NC}"
    echo "   curl https://score.2a-immobilier.com/api/features/stats"
elif [ "$NEW_COUNT" -gt 0 ]; then
    echo -e "${YELLOW}⚠️  $NEW_COUNT biens copiés (moins que prévu : $OLD_COUNT)${NC}"
    echo ""
    echo -e "${BLUE}Raisons possibles :${NC}"
    echo "   - Communes invalides filtrées (format ['76481'])"
    echo "   - Codes postaux manquants"
    echo "   - Données invalides exclues"
else
    echo -e "${RED}❌ Aucune donnée copiée${NC}"
fi
echo ""

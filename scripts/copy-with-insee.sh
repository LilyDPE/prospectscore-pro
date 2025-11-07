#!/bin/bash
# Script pour copier les données en traduisant les codes INSEE en noms de communes
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
echo -e "${BLUE}║   Copie avec Traduction Codes INSEE           ║${NC}"
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

# Étape 1 : Créer une table de référence communes
echo -e "${CYAN}📊 1. Création de la table de référence communes...${NC}"
docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME << 'EOF'
-- Table de référence des communes françaises
CREATE TABLE IF NOT EXISTS ref_communes (
    code_insee VARCHAR(5) PRIMARY KEY,
    nom_commune VARCHAR(200),
    code_postal VARCHAR(5),
    departement VARCHAR(3)
);

-- Créer un index
CREATE INDEX IF NOT EXISTS idx_ref_communes_nom ON ref_communes(nom_commune);
EOF
echo ""

# Étape 2 : Vérifier si la table est vide et la peupler depuis les DVF
echo -e "${CYAN}📊 2. Peuplement de la table de référence depuis les données existantes...${NC}"
docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME << 'EOF'
-- Compter les entrées existantes
SELECT COUNT(*) as nb_communes_ref FROM ref_communes;

-- Insérer les communes depuis biens_univers_old (celles qui ont un vrai nom)
INSERT INTO ref_communes (code_insee, nom_commune, code_postal, departement)
SELECT DISTINCT
    -- Extraire le code INSEE des valeurs comme ['76481']
    TRIM(BOTH '[]''' FROM commune) as code_insee,
    NULL as nom_commune,  -- On va le remplir après
    code_postal,
    departement
FROM biens_univers_old
WHERE commune LIKE '[%'  -- Format avec code INSEE
  AND LENGTH(TRIM(BOTH '[]''' FROM commune)) = 5
ON CONFLICT (code_insee) DO NOTHING;

-- Compter les codes INSEE trouvés
SELECT COUNT(*) as codes_insee_detectes FROM ref_communes WHERE nom_commune IS NULL;
EOF
echo ""

# Étape 3 : Essayer de trouver les noms de communes depuis les données existantes
echo -e "${CYAN}📊 3. Recherche des noms de communes depuis les données valides...${NC}"
docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME << 'EOF'
-- Mettre à jour les noms de communes depuis les biens qui ont un vrai nom
UPDATE ref_communes r
SET nom_commune = subq.nom_commune
FROM (
    SELECT DISTINCT
        code_postal,
        departement,
        commune as nom_commune
    FROM biens_univers_old
    WHERE commune NOT LIKE '[%'  -- Vrais noms de communes
      AND commune IS NOT NULL
      AND LENGTH(commune) > 2
) subq
WHERE r.code_postal = subq.code_postal
  AND r.departement = subq.departement
  AND r.nom_commune IS NULL;

-- Afficher le résultat
SELECT
    COUNT(*) as total_codes_insee,
    COUNT(*) FILTER (WHERE nom_commune IS NOT NULL) as avec_nom_trouve,
    COUNT(*) FILTER (WHERE nom_commune IS NULL) as sans_nom
FROM ref_communes;
EOF
echo ""

# Étape 4 : Copier TOUTES les données en utilisant la table de référence
echo -e "${CYAN}📊 4. Copie complète des données avec traduction INSEE...${NC}"
docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME << 'EOF'
-- Vider la table destination
TRUNCATE TABLE biens_univers RESTART IDENTITY CASCADE;

-- Copier TOUTES les données
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
    -- Code postal
    LEFT(COALESCE(o.code_postal, o.departement || '000'), 5),

    -- Commune : traduire le code INSEE si nécessaire
    CASE
        -- Si commune commence par '[', c'est un code INSEE
        WHEN o.commune LIKE '[%' THEN
            COALESCE(
                r.nom_commune,  -- Nom trouvé dans la table de référence
                'Commune ' || TRIM(BOTH '[]''' FROM o.commune)  -- Fallback avec le code INSEE
            )
        -- Si commune est trop longue, tronquer
        WHEN LENGTH(o.commune) > 200 THEN LEFT(o.commune, 200)
        -- Sinon, utiliser le nom tel quel
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
WHERE o.code_postal IS NOT NULL
  AND o.code_postal != ''
  AND o.departement IS NOT NULL;

-- Afficher le résultat
SELECT
    COUNT(*) as total_copie,
    COUNT(*) FILTER (WHERE commune LIKE 'Commune %') as avec_code_insee_non_traduit,
    COUNT(*) FILTER (WHERE commune NOT LIKE 'Commune %' AND commune IS NOT NULL) as avec_nom_commune,
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

if [ "$NEW_COUNT" -gt 500000 ]; then
    echo -e "${GREEN}🎉 $NEW_COUNT biens copiés avec succès !${NC}"
    echo ""
    echo -e "${BLUE}Amélioration par rapport à la copie précédente :${NC}"
    echo "   - Avant : 282,758 biens (321,864 exclus)"
    echo "   - Maintenant : $NEW_COUNT biens"
    echo "   - Récupérés : +$((NEW_COUNT - 282758)) biens"
else
    echo -e "${YELLOW}⚠️  $NEW_COUNT biens copiés${NC}"
fi
echo ""

echo -e "${YELLOW}💡 Prochaines étapes :${NC}"
echo "   1. Améliorer la traduction INSEE en utilisant une API externe"
echo "   2. Calculer les features ML (zone_type, propensity_score)"
echo "   3. Vérifier: sudo ./scripts/check_probabilites.sh"
echo ""

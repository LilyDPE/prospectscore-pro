#!/bin/bash
#
# Import rapide DVF 2014-2018 depuis fichiers locaux
# Utilise PostgreSQL COPY pour performance maximale
#

set -e

# Configuration
DOSSIER_SOURCE="$1"
DEPARTEMENTS="76|27|80|60|14|62"  # Pour juste 76 et 80: "76|80"

# Connexion PostgreSQL (à adapter)
DB_HOST="localhost"
DB_PORT="5433"
DB_NAME="prospectscore"
DB_USER="prospectscore"
export PGPASSWORD="2aimmobilier2025"

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

if [ -z "$DOSSIER_SOURCE" ]; then
    echo -e "${RED}❌ Usage: $0 /chemin/vers/dossier/${NC}"
    echo "   Le dossier doit contenir les fichiers valeursfoncières-*.txt"
    exit 1
fi

if [ ! -d "$DOSSIER_SOURCE" ]; then
    echo -e "${RED}❌ Dossier introuvable: $DOSSIER_SOURCE${NC}"
    exit 1
fi

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}📥 Import DVF Historique 2014-2018${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Test connexion
echo -e "${YELLOW}🔌 Test connexion PostgreSQL...${NC}"
if psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" > /dev/null 2>&1; then
    echo -e "${GREEN}   ✅ Connecté${NC}"
else
    echo -e "${RED}   ❌ Impossible de se connecter à PostgreSQL${NC}"
    echo "   Vérifie DB_HOST, DB_PORT, DB_USER, PGPASSWORD dans le script"
    exit 1
fi

# Création table temporaire si elle n'existe pas
echo -e "${YELLOW}📋 Préparation table temporaire...${NC}"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" << 'EOF'
CREATE TABLE IF NOT EXISTS transactions_dvf_temp_import (
    code_service_ch TEXT,
    reference_document TEXT,
    article_1 TEXT, article_2 TEXT, article_3 TEXT, article_4 TEXT, article_5 TEXT,
    date_mutation TEXT,
    nature_mutation TEXT,
    valeur_fonciere TEXT,
    no_voie TEXT,
    btq TEXT,
    type_voie TEXT,
    code_voie TEXT,
    voie TEXT,
    code_postal TEXT,
    commune TEXT,
    code_departement TEXT,
    code_commune TEXT,
    prefixe_section TEXT,
    section TEXT,
    no_plan TEXT,
    no_volume TEXT,
    lot_1 TEXT, surface_lot_1 TEXT,
    lot_2 TEXT, surface_lot_2 TEXT,
    lot_3 TEXT, surface_lot_3 TEXT,
    lot_4 TEXT, surface_lot_4 TEXT,
    lot_5 TEXT,
    nombre_lots TEXT,
    code_type_local TEXT,
    type_local TEXT,
    identifiant_local TEXT,
    surface_reelle_bati TEXT,
    nombre_pieces_principales TEXT,
    nature_culture TEXT,
    nature_culture_speciale TEXT,
    surface_terrain TEXT
);
EOF
echo -e "${GREEN}   ✅ Table temporaire prête${NC}"
echo ""

# Import des fichiers
TOTAL_IMPORTED=0
START_TIME=$(date +%s)

for FICHIER in "$DOSSIER_SOURCE"/valeursfoncières-*.txt; do
    if [ ! -f "$FICHIER" ]; then
        echo -e "${YELLOW}⚠️  Aucun fichier trouvé${NC}"
        exit 1
    fi

    BASENAME=$(basename "$FICHIER")
    FILESIZE=$(du -h "$FICHIER" | cut -f1)

    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}📂 $BASENAME ($FILESIZE)${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    # 1. Import brut dans la table temporaire
    echo -e "${YELLOW}⏳ Chargement en table temporaire...${NC}"
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
         -c "\COPY transactions_dvf_temp_import FROM '$FICHIER' WITH (FORMAT csv, HEADER true, DELIMITER '|', ENCODING 'LATIN1');"

    # 2. Insertion filtrée dans la table finale
    echo -e "${YELLOW}⏳ Filtrage et insertion en base...${NC}"
    IMPORTED=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "
        WITH inserted AS (
            INSERT INTO transactions_dvf (
                id_mutation, date_mutation, adresse, code_postal, commune, departement,
                type_local, surface_reelle, nombre_pieces, valeur_fonciere,
                created_at, updated_at
            )
            SELECT DISTINCT
                reference_document,
                TO_DATE(date_mutation, 'DD/MM/YYYY'),
                TRIM(COALESCE(no_voie, '') || ' ' || COALESCE(type_voie, '') || ' ' || COALESCE(voie, '')),
                code_postal,
                commune,
                code_departement,
                type_local,
                NULLIF(REPLACE(surface_reelle_bati, ',', '.'), '')::numeric,
                NULLIF(nombre_pieces_principales, '')::integer,
                NULLIF(REPLACE(valeur_fonciere, ',', '.'), '')::numeric,
                NOW(),
                NOW()
            FROM transactions_dvf_temp_import
            WHERE type_local IN ('Maison', 'Appartement')
              AND code_departement ~ '^($DEPARTEMENTS)\$'
              AND valeur_fonciere IS NOT NULL
              AND REPLACE(valeur_fonciere, ',', '.') ~ '^[0-9]+\.?[0-9]*\$'
              AND REPLACE(valeur_fonciere, ',', '.')::numeric > 0
            ON CONFLICT (id_mutation) DO NOTHING
            RETURNING 1
        )
        SELECT COUNT(*) FROM inserted;
    ")

    IMPORTED=$(echo "$IMPORTED" | tr -d ' ')

    # 3. Nettoyage table temporaire
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
         -c "TRUNCATE transactions_dvf_temp_import;" > /dev/null

    echo -e "${GREEN}   ✅ $IMPORTED transactions importées${NC}"
    TOTAL_IMPORTED=$((TOTAL_IMPORTED + IMPORTED))
    echo ""
done

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
MINUTES=$((DURATION / 60))
SECONDS=$((DURATION % 60))

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ IMPORT TERMINÉ${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}📊 Total importé: $(printf "%'d" $TOTAL_IMPORTED) transactions${NC}"
echo -e "${GREEN}⏱️  Durée: ${MINUTES}m ${SECONDS}s${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Statistiques finales
echo -e "${BLUE}📊 Statistiques par année:${NC}"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "
SELECT
    EXTRACT(YEAR FROM date_mutation) as annee,
    COUNT(*) as transactions,
    COUNT(DISTINCT commune) as communes,
    ROUND(AVG(valeur_fonciere)) as prix_moyen
FROM transactions_dvf
GROUP BY annee
ORDER BY annee DESC;
"

echo ""
echo -e "${YELLOW}🎯 Prochaine étape: calcul des scores de propension${NC}"
echo -e "${YELLOW}   python scripts/calculate_propensity_scores.py${NC}"

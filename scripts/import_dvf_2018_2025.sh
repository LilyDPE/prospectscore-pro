#!/bin/bash
# Import DVF 2018-2025 dans valeurs_foncieres
# Complète l'historique avec les 8 années manquantes

set -e  # Exit on error

# Configuration
YEARS=(2018 2019 2020 2021 2022 2023 2024 2025)
DEPTS=(14 27 60 62 76 80)
BASE_URL="https://files.data.gouv.fr/geo-dvf/latest/csv"
TEMP_DIR="/tmp/dvf_import_$(date +%Y%m%d_%H%M%S)"
LOG_FILE="/var/log/prospectscore/dvf_import_2018_2025.log"

# Couleurs pour l'affichage
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Créer les répertoires si nécessaire
mkdir -p $TEMP_DIR
mkdir -p /var/log/prospectscore/

# Fonction de logging
log() {
    echo -e "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a $LOG_FILE
}

# Header
log "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
log "${BLUE}📥 Import DVF 2018-2025${NC}"
log "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
log ""
log "Années à importer : ${YEARS[@]}"
log "Départements cibles : ${DEPTS[@]}"
log "Répertoire temporaire : $TEMP_DIR"
log ""

# Compteurs
TOTAL_DOWNLOADED=0
TOTAL_IMPORTED=0
ERRORS=0

# Boucle sur les années
for YEAR in "${YEARS[@]}"; do
    log "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    log "${YELLOW}📅 Année $YEAR${NC}"
    log "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    for DEPT in "${DEPTS[@]}"; do
        log ""
        log "  ${BLUE}Département $DEPT${NC}..."

        # Construction URL
        URL="$BASE_URL/$YEAR/departements/${DEPT}.csv.gz"
        FILE_GZ="$TEMP_DIR/${YEAR}_${DEPT}.csv.gz"
        FILE_CSV="$TEMP_DIR/${YEAR}_${DEPT}.csv"

        # Téléchargement
        log "    ⏳ Téléchargement depuis data.gouv.fr..."
        if wget -q -O "$FILE_GZ" "$URL" 2>> $LOG_FILE; then
            TOTAL_DOWNLOADED=$((TOTAL_DOWNLOADED + 1))
            FILE_SIZE=$(du -h "$FILE_GZ" | cut -f1)
            log "    ${GREEN}✅ Téléchargé${NC} ($FILE_SIZE)"
        else
            log "    ${RED}❌ Erreur téléchargement${NC} - URL: $URL"
            ERRORS=$((ERRORS + 1))
            continue
        fi

        # Décompression
        log "    📦 Décompression..."
        if gunzip -f "$FILE_GZ" 2>> $LOG_FILE; then
            CSV_SIZE=$(du -h "$FILE_CSV" | cut -f1)
            LINES=$(wc -l < "$FILE_CSV")
            log "    ${GREEN}✅ Décompressé${NC} ($CSV_SIZE, $LINES lignes)"
        else
            log "    ${RED}❌ Erreur décompression${NC}"
            ERRORS=$((ERRORS + 1))
            continue
        fi

        # Import dans PostgreSQL via Docker
        log "    💾 Import dans PostgreSQL..."

        # Note: Le fichier CSV sera copié dans le conteneur Docker
        # car \COPY FROM attend un chemin accessible depuis le conteneur

        # Copier le fichier dans le conteneur
        if sudo docker cp "$FILE_CSV" postgres-prospectscore:/tmp/${YEAR}_${DEPT}.csv 2>> $LOG_FILE; then
            log "    ${GREEN}✅ Fichier copié dans le conteneur${NC}"
        else
            log "    ${RED}❌ Erreur copie dans conteneur${NC}"
            ERRORS=$((ERRORS + 1))
            continue
        fi

        # Import via psql COPY
        # Note: Adaptation nécessaire selon la structure de valeurs_foncieres
        IMPORT_RESULT=$(sudo docker exec -i postgres-prospectscore psql -U prospectscore -d prospectscore 2>&1 << EOF
\COPY valeurs_foncieres(
    code_service_ch, reference_document,
    article_cgi_1, article_cgi_2, article_cgi_3, article_cgi_4, article_cgi_5,
    no_disposition, date_mutation, nature_mutation, valeur_fonciere,
    no_voie, btq, type_de_voie, code_voie, voie,
    code_postal, commune, code_departement, code_commune,
    prefixe_de_section, section, no_plan, no_volume,
    lot_1, surface_carrez_lot_1, lot_2, surface_carrez_lot_2,
    lot_3, surface_carrez_lot_3, lot_4, surface_carrez_lot_4,
    lot_5, surface_carrez_lot_5, nombre_de_lots,
    code_type_local, type_local, identifiant_local,
    surface_reelle_bati, nombre_pieces_principales,
    nature_culture, nature_culture_speciale, surface_terrain
) FROM '/tmp/${YEAR}_${DEPT}.csv'
WITH (FORMAT csv, DELIMITER ',', HEADER true);
EOF
)

        if echo "$IMPORT_RESULT" | grep -q "COPY"; then
            IMPORTED=$(echo "$IMPORT_RESULT" | grep "COPY" | awk '{print $2}')
            TOTAL_IMPORTED=$((TOTAL_IMPORTED + IMPORTED))
            log "    ${GREEN}✅ Importé${NC} ($IMPORTED transactions)"
        else
            log "    ${RED}❌ Erreur import${NC}"
            log "    Détails : $IMPORT_RESULT"
            ERRORS=$((ERRORS + 1))
        fi

        # Nettoyage dans le conteneur
        sudo docker exec postgres-prospectscore rm -f /tmp/${YEAR}_${DEPT}.csv 2>> $LOG_FILE

        # Nettoyage local
        rm -f "$FILE_CSV"

        log "    ${GREEN}✅ Département $DEPT terminé${NC}"
    done
done

# Stats finales
log ""
log "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
log "${BLUE}📊 STATS FINALES${NC}"
log "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
log ""
log "Fichiers téléchargés : $TOTAL_DOWNLOADED"
log "Transactions importées : $TOTAL_IMPORTED"
log "Erreurs rencontrées : $ERRORS"
log ""

# Requête SQL pour stats par année
log "Distribution par année :"
sudo docker exec -i postgres-prospectscore psql -U prospectscore -d prospectscore << 'SQL' | tee -a $LOG_FILE
SELECT
    LEFT(date_mutation, 4) as annee,
    COUNT(*) as nb_transactions,
    COUNT(DISTINCT code_postal) as nb_codes_postaux,
    COUNT(DISTINCT commune) as nb_communes
FROM valeurs_foncieres
WHERE LEFT(date_mutation, 4) >= '2018'
GROUP BY LEFT(date_mutation, 4)
ORDER BY annee;
SQL

log ""
log "Total transactions dans valeurs_foncieres :"
sudo docker exec -i postgres-prospectscore psql -U prospectscore -d prospectscore -c "SELECT COUNT(*) as total_transactions FROM valeurs_foncieres;" | tee -a $LOG_FILE

# Nettoyage final
log ""
log "🧹 Nettoyage du répertoire temporaire..."
rm -rf "$TEMP_DIR"
log "${GREEN}✅ Répertoire temporaire supprimé${NC}"

# Conclusion
log ""
log "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
if [ $ERRORS -eq 0 ]; then
    log "${GREEN}✅ Import terminé avec succès !${NC}"
    log "${GREEN}✅ $TOTAL_IMPORTED transactions importées${NC}"
    exit 0
else
    log "${RED}⚠️  Import terminé avec $ERRORS erreurs${NC}"
    log "${YELLOW}Consultez le log pour plus de détails : $LOG_FILE${NC}"
    exit 1
fi

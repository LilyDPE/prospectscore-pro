#!/bin/bash
# Import DVF Mensuel Automatique
# Met à jour les données DVF avec les dernières publications de data.gouv.fr
# Exécution recommandée : 2ème mercredi du mois à 3h00

set -e  # Exit on error

# Configuration
CURRENT_YEAR=$(date +%Y)
PREVIOUS_YEAR=$((CURRENT_YEAR - 1))
YEARS=($CURRENT_YEAR $PREVIOUS_YEAR)  # Import année en cours + N-1 pour rattrapage
DEPTS=(14 27 60 62 76 80)
BASE_URL="https://files.data.gouv.fr/geo-dvf/latest/csv"
TEMP_DIR="/tmp/dvf_monthly_$(date +%Y%m%d_%H%M%S)"
LOG_FILE="/var/log/prospectscore/dvf_monthly_$(date +%Y%m%d).log"
LOCK_FILE="/tmp/dvf_import_monthly.lock"

# Couleurs
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Fonction de nettoyage (appelée en sortie)
cleanup() {
    rm -f "$LOCK_FILE"
    rm -rf "$TEMP_DIR"
}
trap cleanup EXIT

# Vérifier lock (éviter imports simultanés)
if [ -f "$LOCK_FILE" ]; then
    echo "[ERREUR] Import déjà en cours (lock file existant: $LOCK_FILE)"
    echo "Si aucun import n'est en cours, supprimez : rm $LOCK_FILE"
    exit 1
fi

touch "$LOCK_FILE"

# Créer répertoires
mkdir -p "$TEMP_DIR"
mkdir -p /var/log/prospectscore/

# Fonction de logging
log() {
    echo -e "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Header
log "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
log "${BLUE}📥 Import DVF Mensuel Automatique${NC}"
log "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
log ""
log "Date : $(date +'%Y-%m-%d %H:%M:%S')"
log "Années : ${YEARS[@]}"
log "Départements : ${DEPTS[@]}"
log ""

# Compteurs
TOTAL_DOWNLOADED=0
TOTAL_IMPORTED=0
ERRORS=0

# Boucle années et départements
for YEAR in "${YEARS[@]}"; do
    log "${YELLOW}━━━━ Année $YEAR ━━━━${NC}"

    for DEPT in "${DEPTS[@]}"; do
        log ""
        log "  ${BLUE}Département $DEPT${NC}"

        # URL et fichiers
        URL="$BASE_URL/$YEAR/departements/${DEPT}.csv.gz"
        FILE_GZ="$TEMP_DIR/${YEAR}_${DEPT}.csv.gz"
        FILE_CSV="$TEMP_DIR/${YEAR}_${DEPT}.csv"

        # Téléchargement
        log "    ⏳ Téléchargement..."
        if wget -q -O "$FILE_GZ" "$URL" 2>> "$LOG_FILE"; then
            TOTAL_DOWNLOADED=$((TOTAL_DOWNLOADED + 1))
            FILE_SIZE=$(du -h "$FILE_GZ" | cut -f1)
            log "    ${GREEN}✅ Téléchargé${NC} ($FILE_SIZE)"
        else
            log "    ${YELLOW}⚠️  Pas de données pour $YEAR-$DEPT${NC} (normal si année future)"
            continue
        fi

        # Décompression
        if gunzip -f "$FILE_GZ" 2>> "$LOG_FILE"; then
            LINES=$(wc -l < "$FILE_CSV")
            log "    ${GREEN}✅ Décompressé${NC} ($LINES lignes)"
        else
            log "    ${RED}❌ Erreur décompression${NC}"
            ERRORS=$((ERRORS + 1))
            continue
        fi

        # Copie dans conteneur
        if sudo docker cp "$FILE_CSV" postgres-prospectscore:/tmp/${YEAR}_${DEPT}.csv 2>> "$LOG_FILE"; then
            log "    ✓ Copié dans conteneur"
        else
            log "    ${RED}❌ Erreur copie conteneur${NC}"
            ERRORS=$((ERRORS + 1))
            continue
        fi

        # Import PostgreSQL
        log "    💾 Import en base..."
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
            ERRORS=$((ERRORS + 1))
        fi

        # Nettoyage conteneur
        sudo docker exec postgres-prospectscore rm -f /tmp/${YEAR}_${DEPT}.csv 2>> "$LOG_FILE"
    done
done

# Stats finales
log ""
log "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
log "${BLUE}📊 RÉSUMÉ${NC}"
log "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
log ""
log "Fichiers téléchargés : $TOTAL_DOWNLOADED"
log "Transactions importées : $TOTAL_IMPORTED"
log "Erreurs : $ERRORS"
log ""

# Total en base
TOTAL_DB=$(sudo docker exec -i postgres-prospectscore psql -U prospectscore -d prospectscore -t -c "SELECT COUNT(*) FROM valeurs_foncieres;" | tr -d ' ')
log "Total en base : $TOTAL_DB transactions"

# Stats par année (top 5)
log ""
log "Distribution par année (top 5) :"
sudo docker exec -i postgres-prospectscore psql -U prospectscore -d prospectscore << 'SQL' | tee -a "$LOG_FILE"
SELECT
    LEFT(date_mutation, 4) as annee,
    COUNT(*) as nb_transactions
FROM valeurs_foncieres
GROUP BY LEFT(date_mutation, 4)
ORDER BY annee DESC
LIMIT 5;
SQL

# Conclusion
log ""
log "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
if [ $ERRORS -eq 0 ]; then
    log "${GREEN}✅ Import mensuel terminé avec succès${NC}"
    if [ $TOTAL_IMPORTED -gt 0 ]; then
        log "${GREEN}📈 $TOTAL_IMPORTED nouvelles transactions importées${NC}"
    else
        log "${YELLOW}ℹ️  Aucune nouvelle transaction (normal si déjà à jour)${NC}"
    fi
    exit 0
else
    log "${RED}⚠️  Import terminé avec $ERRORS erreurs${NC}"
    log "${YELLOW}📋 Log complet : $LOG_FILE${NC}"
    exit 1
fi

#!/bin/bash

LOG_FILE="/var/www/prospectscore-pro/import_dvf_monthly.log"
DATE=$(date '+%Y-%m-%d %H:%M:%S')

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | sudo tee -a $LOG_FILE
echo "📥 Import DVF mensuel - $DATE" | sudo tee -a $LOG_FILE
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | sudo tee -a $LOG_FILE

cd /tmp

# Départements à mettre à jour
DEPTS="76 27 80 60 14 62"

# Année en cours et année précédente
CURRENT_YEAR=$(date +%Y)
PREVIOUS_YEAR=$((CURRENT_YEAR - 1))

for YEAR in $PREVIOUS_YEAR $CURRENT_YEAR; do
    echo "📅 Mise à jour année $YEAR" | sudo tee -a $LOG_FILE
    
    for DEPT in $DEPTS; do
        echo "⏳ Département $DEPT..." | sudo tee -a $LOG_FILE
        
        URL="https://files.data.gouv.fr/geo-dvf/latest/csv/${YEAR}/departements/${DEPT}.csv.gz"
        
        wget -q "$URL" -O "${DEPT}_${YEAR}_update.csv.gz" 2>&1 | sudo tee -a $LOG_FILE
        
        if [ -f "${DEPT}_${YEAR}_update.csv.gz" ]; then
            gunzip -f "${DEPT}_${YEAR}_update.csv.gz"
            
            if [ -f "${DEPT}_${YEAR}_update.csv" ]; then
                LINES=$(wc -l < "${DEPT}_${YEAR}_update.csv")
                echo "📊 ${LINES} transactions" | sudo tee -a $LOG_FILE
                
                # Import en base (avec ON CONFLICT DO NOTHING pour éviter les doublons)
                sudo docker exec -i postgres-prospectscore psql -U prospectscore -d prospectscore << PSQL
\copy transactions_dvf_temp FROM '/tmp/${DEPT}_${YEAR}_update.csv' WITH (FORMAT csv, HEADER true, DELIMITER ',');
INSERT INTO transactions_dvf (
    id_mutation, date_mutation, adresse, code_postal, commune, departement,
    type_local, surface_reelle, nombre_pieces, valeur_fonciere
)
SELECT 
    id_mutation, date_mutation::date, adresse, code_postal, commune, 
    code_departement, type_local, surface_reelle_bati::numeric, 
    nombre_pieces_principales::integer, valeur_fonciere::numeric
FROM transactions_dvf_temp
WHERE valeur_fonciere IS NOT NULL AND valeur_fonciere > 0
ON CONFLICT (id_mutation) DO NOTHING;
TRUNCATE transactions_dvf_temp;
PSQL
                
                echo "✅ ${DEPT} importé" | sudo tee -a $LOG_FILE
                rm -f "${DEPT}_${YEAR}_update.csv"
            fi
        else
            echo "⚠️ Fichier non trouvé" | sudo tee -a $LOG_FILE
        fi
    done
done

# Calculer les scores pour les nouvelles transactions
echo "" | sudo tee -a $LOG_FILE
echo "🎯 Calcul des scores pour les nouvelles transactions..." | sudo tee -a $LOG_FILE
curl -s -X POST "http://localhost:8003/api/admin/calculate-scores" | sudo tee -a $LOG_FILE

echo "" | sudo tee -a $LOG_FILE
echo "✅ Import mensuel terminé - $DATE" | sudo tee -a $LOG_FILE

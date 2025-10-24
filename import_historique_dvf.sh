#!/bin/bash

LOG_FILE="/var/www/prospectscore-pro/import_historique.log"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | sudo tee -a $LOG_FILE
echo "📥 Import DVF 2014-2023 - $(date)" | sudo tee -a $LOG_FILE
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | sudo tee -a $LOG_FILE
echo "" | sudo tee -a $LOG_FILE

cd /tmp

# Départements à importer (Seine-Maritime + limitrophes)
DEPTS="76 27 80 60 14 62"

# Import par année de 2014 à 2023
for YEAR in {2014..2023}; do
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | sudo tee -a $LOG_FILE
    echo "📅 Année $YEAR" | sudo tee -a $LOG_FILE
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | sudo tee -a $LOG_FILE
    
    for DEPT in $DEPTS; do
        echo "⏳ Téléchargement département $DEPT - $YEAR..." | sudo tee -a $LOG_FILE
        
        # URL du fichier DVF
        URL="https://files.data.gouv.fr/geo-dvf/latest/csv/${YEAR}/departements/${DEPT}.csv.gz"
        
        # Télécharger
        wget -q "$URL" -O "${DEPT}_${YEAR}.csv.gz" 2>&1 | sudo tee -a $LOG_FILE
        
        if [ -f "${DEPT}_${YEAR}.csv.gz" ]; then
            echo "✅ Téléchargé : ${DEPT}_${YEAR}.csv.gz" | sudo tee -a $LOG_FILE
            
            # Décompresser
            gunzip -f "${DEPT}_${YEAR}.csv.gz"
            
            if [ -f "${DEPT}_${YEAR}.csv" ]; then
                # Compter les lignes
                LINES=$(wc -l < "${DEPT}_${YEAR}.csv")
                echo "📊 ${LINES} transactions" | sudo tee -a $LOG_FILE
                
                # Importer directement en base via psql COPY
                echo "💾 Import en base via COPY..." | sudo tee -a $LOG_FILE
                
                # Utiliser COPY direct (beaucoup plus rapide que l'API)
                sudo docker exec -i postgres-prospectscore psql -U prospectscore -d prospectscore << PSQL
\copy transactions_dvf_temp FROM '/tmp/${DEPT}_${YEAR}.csv' WITH (FORMAT csv, HEADER true, DELIMITER ',');
INSERT INTO transactions_dvf (
    id_mutation, date_mutation, adresse, code_postal, commune, departement,
    type_local, surface_reelle, nombre_pieces, valeur_fonciere
)
SELECT 
    id_mutation, date_mutation::date, adresse, code_postal, commune, 
    code_departement, type_local, surface_reelle_bati::numeric, 
    nombre_pieces_principales::integer, valeur_fonciere::numeric
FROM transactions_dvf_temp
WHERE valeur_fonciere IS NOT NULL 
  AND valeur_fonciere > 0
ON CONFLICT (id_mutation) DO NOTHING;
TRUNCATE transactions_dvf_temp;
PSQL
                
                echo "✅ Importé" | sudo tee -a $LOG_FILE
                
                # Nettoyer
                rm -f "${DEPT}_${YEAR}.csv"
            fi
        else
            echo "⚠️ Fichier non trouvé pour ${DEPT} ${YEAR}" | sudo tee -a $LOG_FILE
        fi
        
        echo "" | sudo tee -a $LOG_FILE
    done
    
    # Stats intermédiaires
    echo "📊 Total en base après $YEAR :" | sudo tee -a $LOG_FILE
    sudo docker exec postgres-prospectscore psql -U prospectscore -d prospectscore -t -c "
    SELECT 
        EXTRACT(YEAR FROM date_mutation) as annee,
        COUNT(*) as nombre
    FROM transactions_dvf 
    GROUP BY annee
    ORDER BY annee DESC;
    " | sudo tee -a $LOG_FILE
    echo "" | sudo tee -a $LOG_FILE
done

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | sudo tee -a $LOG_FILE
echo "✅ Import historique terminé !" | sudo tee -a $LOG_FILE
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | sudo tee -a $LOG_FILE

# Statistiques finales
echo "" | sudo tee -a $LOG_FILE
echo "📊 STATISTIQUES FINALES :" | sudo tee -a $LOG_FILE
sudo docker exec postgres-prospectscore psql -U prospectscore -d prospectscore -c "
SELECT 
    EXTRACT(YEAR FROM date_mutation) as annee,
    COUNT(*) as transactions,
    COUNT(DISTINCT commune) as communes,
    ROUND(AVG(valeur_fonciere)) as prix_moyen
FROM transactions_dvf 
GROUP BY annee
ORDER BY annee DESC;
" | sudo tee -a $LOG_FILE

echo "" | sudo tee -a $LOG_FILE
echo "🎯 Lancement du scoring des nouvelles transactions..." | sudo tee -a $LOG_FILE
curl -s -X POST "http://localhost:8003/api/admin/calculate-scores" | sudo tee -a $LOG_FILE
echo "" | sudo tee -a $LOG_FILE

echo "✅ TOUT EST TERMINÉ !" | sudo tee -a $LOG_FILE

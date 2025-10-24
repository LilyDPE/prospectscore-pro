#!/bin/bash

LOG_FILE="/var/www/prospectscore-pro/enrichment_nightly.log"
DATE=$(date '+%Y-%m-%d %H:%M:%S')

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >> $LOG_FILE
echo "🌙 Enrichissement nocturne - $DATE" >> $LOG_FILE
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >> $LOG_FILE

# Compter ce qu'il y a à faire
NEW_COUNT=$(docker exec postgres-prospectscore psql -U prospectscore -d prospectscore -t -c "
SELECT COUNT(*) FROM transactions_dvf WHERE date_enrichissement IS NULL;
" | xargs)

OLD_COUNT=$(docker exec postgres-prospectscore psql -U prospectscore -d prospectscore -t -c "
SELECT COUNT(*) FROM transactions_dvf 
WHERE date_enrichissement < NOW() - INTERVAL '3 months';
" | xargs)

echo "📊 Nouvelles transactions à enrichir : $NEW_COUNT" >> $LOG_FILE
echo "🔄 Transactions à actualiser (> 3 mois) : $OLD_COUNT" >> $LOG_FILE
echo "" >> $LOG_FILE

# Si rien à faire, sortir
if [ "$NEW_COUNT" -eq 0 ] && [ "$OLD_COUNT" -eq 0 ]; then
    echo "✅ Rien à enrichir cette nuit !" >> $LOG_FILE
    exit 0
fi

# Réinitialiser le flag pour les transactions anciennes
docker exec postgres-prospectscore psql -U prospectscore -d prospectscore -c "
UPDATE transactions_dvf 
SET enrichi_pappers = false, date_enrichissement = NULL
WHERE date_enrichissement < NOW() - INTERVAL '3 months';
" >> $LOG_FILE 2>&1

# Enrichir par lots (max 2000 pour ne pas surcharger)
TOTAL_TO_PROCESS=$((NEW_COUNT + OLD_COUNT))
BATCHES=$(( (TOTAL_TO_PROCESS + 999) / 1000 ))

echo "⏳ Enrichissement de $TOTAL_TO_PROCESS transactions en $BATCHES lots..." >> $LOG_FILE
echo "" >> $LOG_FILE

for i in $(seq 1 $BATCHES); do
    echo "Lot $i/$BATCHES en cours..." >> $LOG_FILE
    
    RESULT=$(curl -s -X POST "http://localhost:8003/api/admin/enrich-smart?score_min=0&limit=1000")
    
    echo "$RESULT" >> $LOG_FILE
    echo "" >> $LOG_FILE
    
    # Pause pour éviter de surcharger
    sleep 2
done

# Statistiques finales
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >> $LOG_FILE
echo "📊 STATISTIQUES FINALES" >> $LOG_FILE
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >> $LOG_FILE

docker exec postgres-prospectscore psql -U prospectscore -d prospectscore -c "
SELECT 
    proprietaire_type,
    COUNT(*) as count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) as percentage
FROM transactions_dvf 
WHERE enrichi_pappers = true
GROUP BY proprietaire_type
ORDER BY count DESC;
" >> $LOG_FILE 2>&1

echo "" >> $LOG_FILE
echo "✅ Enrichissement nocturne terminé - $(date '+%Y-%m-%d %H:%M:%S')" >> $LOG_FILE
echo "" >> $LOG_FILE

#!/bin/bash
set -e

# Configuration
DEPARTMENTS=("76" "80" "27" "60" "14" "50" "61")
YEAR=$(date +%Y)
API_URL="http://localhost:8003/api/admin/import-dvf"
LOG_FILE="/var/log/prospectscore/import-$(date +%Y%m%d).log"

# Créer le dossier de logs
sudo mkdir -p /var/log/prospectscore

# Log début
echo "=== Import DVF démarré le $(date) ===" | tee -a $LOG_FILE

# Construire la liste des départements pour l'API
DEPT_JSON=$(printf '%s\n' "${DEPARTMENTS[@]}" | jq -R . | jq -s -c .)

# Lancer l'import
echo "Import des départements: ${DEPARTMENTS[*]}" | tee -a $LOG_FILE
RESULT=$(curl -s -X POST $API_URL \
  -H 'Content-Type: application/json' \
  -d "{\"departements\": $DEPT_JSON, \"years\": [$YEAR]}")

echo "Résultat: $RESULT" | tee -a $LOG_FILE

# Extraire le nombre total importé (correction du path JSON)
IMPORTED=$(echo $RESULT | jq -r '.results.global_imported // 0')

if [ "$IMPORTED" -gt 0 ]; then
    echo "✅ Import réussi : $IMPORTED transactions" | tee -a $LOG_FILE
else
    echo "⚠️ Aucune nouvelle transaction importée" | tee -a $LOG_FILE
fi

echo "=== Import terminé le $(date) ===" | tee -a $LOG_FILE

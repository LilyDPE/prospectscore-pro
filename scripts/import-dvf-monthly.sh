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

    # Étape 2: Rapprochement DVF (Ground Truth Detection)
    echo "" | tee -a $LOG_FILE
    echo "🕵️ Lancement du rapprochement DVF pour détecter les ventes confirmées..." | tee -a $LOG_FILE
    RECONCILE_RESULT=$(curl -s -X POST http://localhost:8003/api/admin/reconcile-dvf \
      -H 'Content-Type: application/json')

    MATCHES=$(echo $RECONCILE_RESULT | jq -r '.matches_trouves // 0')
    ACCURACY=$(echo $RECONCILE_RESULT | jq -r '.accuracy // 0')

    echo "✅ Rapprochement terminé : $MATCHES ventes confirmées (accuracy: $ACCURACY)" | tee -a $LOG_FILE

    # Étape 3: Vérifier si on a assez de données pour ré-entraîner
    echo "" | tee -a $LOG_FILE
    echo "📊 Vérification des données disponibles pour ré-entraînement..." | tee -a $LOG_FILE
    TRAINING_STATS=$(curl -s http://localhost:8003/api/admin/ml-training-stats)

    NOUVEAU_DISPO=$(echo $TRAINING_STATS | jq -r '.nouveau_disponible // 0')
    PRET_TRAINING=$(echo $TRAINING_STATS | jq -r '.pret_entrainement // false')

    echo "📚 Données validées disponibles : $NOUVEAU_DISPO échantillons" | tee -a $LOG_FILE

    # Étape 4: Ré-entraîner le modèle si assez de données
    if [ "$PRET_TRAINING" = "true" ]; then
        echo "" | tee -a $LOG_FILE
        echo "🧠 Lancement du ré-entraînement du modèle ML..." | tee -a $LOG_FILE

        TRAIN_RESULT=$(curl -s -X POST http://localhost:8003/api/admin/train-ml-model \
          -H 'Content-Type: application/json' \
          -d '{"model_type": "random_forest"}')

        F1_SCORE=$(echo $TRAIN_RESULT | jq -r '.f1_score // 0')
        TRAIN_SAMPLES=$(echo $TRAIN_RESULT | jq -r '.train_samples // 0')

        if [ "$F1_SCORE" != "0" ]; then
            echo "✅ Ré-entraînement réussi : F1-Score=$F1_SCORE ($TRAIN_SAMPLES échantillons)" | tee -a $LOG_FILE
        else
            echo "⚠️ Ré-entraînement échoué ou pas assez de données" | tee -a $LOG_FILE
        fi
    else
        echo "⏳ Pas assez de données validées pour ré-entraîner ($NOUVEAU_DISPO < 50)" | tee -a $LOG_FILE
        echo "   Le modèle sera ré-entraîné automatiquement quand assez de feedbacks seront reçus" | tee -a $LOG_FILE
    fi

else
    echo "⚠️ Aucune nouvelle transaction importée" | tee -a $LOG_FILE
fi

echo "" | tee -a $LOG_FILE
echo "=== Import et Auto-Learning terminés le $(date) ===" | tee -a $LOG_FILE

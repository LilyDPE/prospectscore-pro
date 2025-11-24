#!/bin/bash
# Télécharge et upload DVF 2014-2019 pour les départements 76, 80, 27, 60

set -e

TMPDIR="/tmp/dvf_import"
API_URL="http://localhost:8003/api/admin/import-dvf-file"
DEPTS="76,80,27,60"

mkdir -p "$TMPDIR"
cd "$TMPDIR"

echo "🎯 Import DVF Historique 2014-2019"
echo "📍 Départements: $DEPTS"
echo ""

# Fonction pour télécharger, filtrer et uploader une année
process_year() {
    local YEAR=$1
    local FILE_FULL="dvf_${YEAR}_full.csv.gz"
    local FILE_FILTERED="dvf_${YEAR}_filtered.csv.gz"

    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📅 Année $YEAR"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Étape 1: Téléchargement
    echo "📥 Téléchargement depuis cadastre.data.gouv.fr..."
    if wget -q --show-progress "https://cadastre.data.gouv.fr/data/etalab-dvf/${YEAR}/full.csv.gz" -O "$FILE_FULL"; then
        echo "✅ Téléchargement réussi"
    else
        echo "❌ ERREUR: Téléchargement échoué pour $YEAR"
        echo ""
        echo "⚠️  ACTION MANUELLE REQUISE:"
        echo "1. Allez sur: https://cadastre.data.gouv.fr/data/etalab-dvf/"
        echo "2. Téléchargez: ${YEAR}/full.csv.gz"
        echo "3. Uploadez via: curl -X POST $API_URL -F 'file=@/path/to/full.csv.gz'"
        echo ""
        return 1
    fi

    # Étape 2: Filtrage par département
    echo "🔍 Filtrage départements $DEPTS..."
    gunzip "$FILE_FULL"
    local FILE_CSV="dvf_${YEAR}_full.csv"

    # Extraire l'en-tête
    head -1 "$FILE_CSV" > "dvf_${YEAR}_filtered.csv"

    # Filtrer les lignes (colonne code_departement est généralement en position 2)
    grep -E "^[^,]*,(76|80|27|60)," "$FILE_CSV" >> "dvf_${YEAR}_filtered.csv" || true

    # Compter les lignes
    local NB_LINES=$(wc -l < "dvf_${YEAR}_filtered.csv")
    echo "📊 $NB_LINES transactions après filtrage"

    # Recompresser
    gzip "dvf_${YEAR}_filtered.csv"

    # Nettoyer le fichier non compressé
    rm -f "$FILE_CSV"

    # Étape 3: Upload vers l'API
    echo "📤 Upload vers l'API..."
    RESPONSE=$(curl -s -X POST "$API_URL" -F "file=@$FILE_FILTERED")

    # Vérifier le succès
    if echo "$RESPONSE" | grep -q '"success":true'; then
        IMPORTED=$(echo "$RESPONSE" | grep -o '"imported":[0-9]*' | cut -d':' -f2)
        echo "✅ Upload réussi: $IMPORTED transactions importées"
    else
        echo "❌ ERREUR lors de l'upload:"
        echo "$RESPONSE"
        return 1
    fi

    # Nettoyer
    rm -f "$FILE_FULL" "$FILE_FILTERED"

    echo ""
}

# Traiter chaque année
TOTAL_SUCCESS=0
TOTAL_FAILED=0

for YEAR in {2014..2019}; do
    if process_year "$YEAR"; then
        ((TOTAL_SUCCESS++))
    else
        ((TOTAL_FAILED++))
    fi

    # Pause entre chaque année pour éviter surcharge
    if [ $YEAR -lt 2019 ]; then
        echo "⏸️  Pause 5 secondes..."
        sleep 5
    fi
done

# Résumé
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 RÉSUMÉ"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Années importées avec succès: $TOTAL_SUCCESS/6"
echo "❌ Années échouées: $TOTAL_FAILED/6"
echo ""

if [ $TOTAL_FAILED -eq 0 ]; then
    echo "🎉 Import historique terminé !"
    echo ""
    echo "🚀 PROCHAINES ÉTAPES:"
    echo ""
    echo "1️⃣  Analyser la propension à vendre:"
    echo "   curl -X POST http://localhost:8003/api/admin/analyze-propensity -d '{\"score_min\": 0, \"limit\": 500000}'"
    echo ""
    echo "2️⃣  Détecter les reventes (Ground Truth):"
    echo "   curl -X POST http://localhost:8003/api/admin/reconcile-dvf -d '{\"lookback_months\": 120}'"
    echo ""
    echo "3️⃣  Vérifier les données ML:"
    echo "   curl http://localhost:8003/api/admin/ml-training-stats"
    echo ""
    echo "4️⃣  Entraîner le modèle ML:"
    echo "   curl -X POST http://localhost:8003/api/admin/train-ml-model -d '{\"model_type\": \"random_forest\"}'"
    echo ""
else
    echo "⚠️  Certaines années ont échoué. Téléchargez-les manuellement."
fi

# Nettoyer le dossier temporaire
cd /
rm -rf "$TMPDIR"

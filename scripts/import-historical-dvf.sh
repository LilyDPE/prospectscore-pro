#!/bin/bash
# Script d'aide pour télécharger et importer les DVF historiques (2014-2022)
# L'API data.gouv.fr ne propose que 2023-2025

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOWNLOAD_DIR="$SCRIPT_DIR/../dvf_historique"
API_URL="http://localhost:8003/api/admin/import-dvf-file"

# Créer le dossier de téléchargement
mkdir -p "$DOWNLOAD_DIR"

echo "📦 Import DVF Historique (2014-2022)"
echo "══════════════════════════════════════"
echo ""
echo "⚠️ L'API data.gouv.fr ne propose que 2023-2025"
echo "Pour les années antérieures, téléchargement manuel requis"
echo ""

# Départements à télécharger
DEPARTMENTS=("76" "80" "27" "60" "14" "50" "61")
YEARS=(2014 2015 2016 2017 2018 2019 2020 2021 2022)

# URLs de téléchargement DVF historique
BASE_URL="https://files.data.gouv.fr/geo-dvf/latest/csv"

echo "📍 Option 1 : Téléchargement Automatique (si disponible)"
echo "────────────────────────────────────────────────────────"
echo ""

for YEAR in "${YEARS[@]}"; do
    for DEPT in "${DEPARTMENTS[@]}"; do
        FILE="${YEAR}-${DEPT}.csv.gz"
        URL="${BASE_URL}/${YEAR}/departements/${DEPT}.csv.gz"

        echo "Tentative : $FILE"

        if curl -f -s -I "$URL" > /dev/null 2>&1; then
            echo "  ✅ Disponible : $URL"

            # Télécharger
            curl -s -o "$DOWNLOAD_DIR/$FILE" "$URL"

            # Uploader vers l'API
            echo "  📤 Upload vers API..."
            RESULT=$(curl -s -X POST "$API_URL" \
                -F "file=@$DOWNLOAD_DIR/$FILE" \
                -H "Content-Type: multipart/form-data")

            IMPORTED=$(echo "$RESULT" | jq -r '.imported // 0')
            echo "  ✅ $IMPORTED transactions importées"

            # Nettoyer
            rm "$DOWNLOAD_DIR/$FILE"
        else
            echo "  ❌ Non disponible via API automatique"
        fi
    done
done

echo ""
echo "📍 Option 2 : Téléchargement Manuel (recommandé)"
echo "────────────────────────────────────────────────────────"
echo ""
echo "Si le téléchargement automatique échoue, suivez ces étapes :"
echo ""
echo "1. Téléchargez manuellement depuis :"
echo "   🔗 https://cadastre.data.gouv.fr/data/etalab-dvf/"
echo ""
echo "2. Pour chaque année (2014-2022), téléchargez :"
for DEPT in "${DEPARTMENTS[@]}"; do
    echo "   - Département ${DEPT}: full.csv.gz de l'année concernée"
done
echo ""
echo "3. Uploadez chaque fichier avec curl :"
echo "   curl -X POST http://localhost:8003/api/admin/import-dvf-file \\"
echo "     -F 'file=@/path/to/76.csv.gz'"
echo ""
echo "4. Ou utilisez l'interface web (si disponible) :"
echo "   http://localhost:8003/docs#/admin/import_dvf_from_file_api_admin_import_dvf_file_post"
echo ""

echo "📊 Vérifier l'import actuel :"
echo "────────────────────────────────────────────────────────"
curl -s http://localhost:8003/api/admin/dvf/stats | jq '.'

echo ""
echo "✅ Script terminé !"
echo ""
echo "💡 Conseil : Pour les années 2014-2022, le téléchargement manuel"
echo "depuis cadastre.data.gouv.fr est souvent plus fiable."

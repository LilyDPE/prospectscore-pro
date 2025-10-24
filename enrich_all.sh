#!/bin/bash

echo "🚀 Début de l'enrichissement global"
echo "📊 Estimation : 37 000 transactions = ~5 heures"
echo ""

# Fonction pour enrichir un lot
enrich_batch() {
    local batch=$1
    echo "⏳ Lot $batch/37 en cours..."
    curl -s -X POST "http://localhost:8003/api/admin/enrich-smart?score_min=0&limit=1000" | jq
    echo ""
}

# Boucle d'enrichissement
for i in {1..37}; do
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    enrich_batch $i
    
    # Petit pause pour ne pas surcharger l'API SIRENE
    sleep 2
    
    # Afficher les stats tous les 5 lots
    if [ $((i % 5)) -eq 0 ]; then
        echo ""
        echo "📊 STATISTIQUES INTERMÉDIAIRES :"
        docker exec postgres-prospectscore psql -U prospectscore -d prospectscore -c "
        SELECT 
            proprietaire_type,
            COUNT(*) as count
        FROM transactions_dvf 
        WHERE enrichi_pappers = true
        GROUP BY proprietaire_type
        ORDER BY count DESC;"
        echo ""
    fi
done

echo ""
echo "✅ ENRICHISSEMENT TERMINÉ !"
echo ""
echo "📊 STATISTIQUES FINALES :"
docker exec postgres-prospectscore psql -U prospectscore -d prospectscore -c "
SELECT 
    proprietaire_type,
    COUNT(*) as count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) as percentage
FROM transactions_dvf 
WHERE enrichi_pappers = true
GROUP BY proprietaire_type
ORDER BY count DESC;"

#!/bin/bash
# Script d'installation du système d'auto-apprentissage ML
# ProspectScore Pro - Auto-Learning Setup

set -e  # Exit on error

echo "🚀 Installation du système d'auto-apprentissage ML pour ProspectScore Pro"
echo ""

# Couleurs
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 1. Vérifier que Docker est en cours
echo "🔍 Vérification de Docker..."
if ! docker-compose ps | grep -q "Up"; then
    echo -e "${RED}❌ Docker Compose n'est pas démarré${NC}"
    echo "Lancez d'abord: docker-compose up -d"
    exit 1
fi
echo -e "${GREEN}✅ Docker est en cours d'exécution${NC}"

# 2. Installer les dépendances ML
echo ""
echo "📦 Installation des dépendances ML (scikit-learn, xgboost)..."
docker-compose exec -T backend pip install -r requirements-ml.txt
echo -e "${GREEN}✅ Dépendances ML installées${NC}"

# 3. Créer le dossier models
echo ""
echo "📁 Création du dossier pour les modèles ML..."
docker-compose exec -T backend mkdir -p /app/models
echo -e "${GREEN}✅ Dossier models créé${NC}"

# 4. Migrer la base de données
echo ""
echo "🗄️ Migration de la base de données (ajout colonnes ML)..."
docker-compose exec -T db psql -U prospectscore -d prospectscore < backend/migrations/add_ml_columns.sql
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Migration réussie${NC}"
else
    echo -e "${YELLOW}⚠️ La migration a échoué ou les colonnes existent déjà${NC}"
fi

# 5. Vérifier les stats actuelles
echo ""
echo "📊 Vérification des données actuelles..."
STATS=$(curl -s http://localhost:8003/api/admin/ml-training-stats 2>/dev/null || echo '{}')
TOTAL=$(echo $STATS | jq -r '.total_validé // 0')
NOUVEAU=$(echo $STATS | jq -r '.nouveau_disponible // 0')

echo "  Transactions validées: $TOTAL"
echo "  Nouvelles données disponibles: $NOUVEAU"

if [ "$NOUVEAU" -ge 50 ]; then
    echo -e "${GREEN}  ✅ Assez de données pour entraîner !${NC}"
else
    echo -e "${YELLOW}  ⏳ Besoin de plus de feedbacks (minimum 50)${NC}"
fi

# 6. Tester le matching DVF
echo ""
echo "🕵️ Test du matching DVF..."
docker-compose exec -T backend python services/dvf_matcher.py
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Matching DVF opérationnel${NC}"
else
    echo -e "${YELLOW}⚠️ Erreur lors du test de matching (normal si pas de données)${NC}"
fi

# 7. Configuration du cron (optionnel)
echo ""
echo "⏰ Configuration du cron pour import mensuel automatique..."
CRON_ENTRY="0 3 1 * * $(pwd)/scripts/import-dvf-monthly.sh"

if crontab -l 2>/dev/null | grep -q "import-dvf-monthly.sh"; then
    echo -e "${YELLOW}  ⚠️ Cron déjà configuré${NC}"
else
    echo "  Voulez-vous ajouter le cron automatique ? (y/n)"
    read -r response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        (crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -
        echo -e "${GREEN}  ✅ Cron configuré (1er de chaque mois à 3h)${NC}"
    else
        echo "  Cron non configuré. Pour l'ajouter manuellement:"
        echo "    crontab -e"
        echo "    Puis ajouter: $CRON_ENTRY"
    fi
fi

# 8. Redémarrer le backend pour charger les nouveaux modules
echo ""
echo "🔄 Redémarrage du backend..."
docker-compose restart backend
sleep 3
echo -e "${GREEN}✅ Backend redémarré${NC}"

# 9. Résumé
echo ""
echo "═══════════════════════════════════════════════════════════"
echo -e "${GREEN}🎉 Installation terminée !${NC}"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "📚 Nouveaux endpoints disponibles:"
echo "  POST /api/admin/feedback             - Feedback agents"
echo "  POST /api/admin/reconcile-dvf        - Matching DVF"
echo "  POST /api/admin/train-ml-model       - Entraînement ML"
echo "  GET  /api/admin/ml-training-stats    - Statistiques"
echo ""
echo "📖 Documentation complète: AUTO_LEARNING_GUIDE.md"
echo ""
echo "🔄 Prochaines étapes:"
echo "  1. Les agents donnent leur feedback via POST /api/admin/feedback"
echo "  2. L'import DVF mensuel tourne automatiquement (cron)"
echo "  3. Le système se ré-entraîne dès que >= 50 feedbacks validés"
echo "  4. Les prédictions s'améliorent automatiquement !"
echo ""
echo -e "${YELLOW}⚠️ Important:${NC}"
echo "  - Minimum 50 échantillons validés pour le 1er entraînement"
echo "  - DVF a ~6 mois de délai (normal)"
echo "  - Combiner feedback agents (rapide) + DVF (fiable)"
echo ""

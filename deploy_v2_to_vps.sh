#!/bin/bash
# Script de déploiement automatique de la V2 sur le VPS OVH
# Usage: ./deploy_v2_to_vps.sh

set -e  # Arrêter en cas d'erreur

# Configuration
VPS_IP="146.59.228.175"
VPS_USER="root"  # Changez si nécessaire
PROJECT_PATH="/var/www/prospectscore-pro"  # Ajustez si différent
BRANCH="claude/project-status-review-018mAyUAV7GK76xZ8odepa1v"

# Couleurs
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}======================================================================"
echo "🚀 DÉPLOIEMENT PROPENSITY PREDICTOR V2 SUR VPS OVH"
echo "======================================================================${NC}"
echo ""
echo "VPS : $VPS_IP"
echo "User : $VPS_USER"
echo "Branch : $BRANCH"
echo ""

# Fonction pour exécuter des commandes sur le VPS
ssh_exec() {
    ssh -o StrictHostKeyChecking=no "$VPS_USER@$VPS_IP" "$@"
}

# 1. Test de connexion SSH
echo -e "${BLUE}🔍 1. Test de connexion SSH...${NC}"
if ssh_exec "echo 'SSH OK'" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Connexion SSH réussie${NC}"
else
    echo -e "${RED}❌ Connexion SSH échouée${NC}"
    echo "Assurez-vous que :"
    echo "  - Le mot de passe est correct"
    echo "  - Le port SSH (22) est ouvert"
    echo "  - Votre IP est autorisée dans le pare-feu OVH"
    exit 1
fi
echo ""

# 2. Vérifier si le projet existe
echo -e "${BLUE}📁 2. Vérification du projet sur le VPS...${NC}"
if ssh_exec "test -d $PROJECT_PATH"; then
    echo -e "${GREEN}✅ Projet trouvé : $PROJECT_PATH${NC}"
    PROJECT_EXISTS=true
else
    echo -e "${YELLOW}⚠️  Projet non trouvé${NC}"
    echo "Le projet sera cloné dans : $PROJECT_PATH"
    PROJECT_EXISTS=false
fi
echo ""

# 3. Cloner ou mettre à jour le projet
if [ "$PROJECT_EXISTS" = false ]; then
    echo -e "${BLUE}📥 3. Clonage du projet...${NC}"
    ssh_exec "
        mkdir -p $(dirname $PROJECT_PATH)
        cd $(dirname $PROJECT_PATH)
        git clone https://github.com/LilyDPE/prospectscore-pro.git $(basename $PROJECT_PATH)
        cd $PROJECT_PATH
        git checkout $BRANCH
    "
    echo -e "${GREEN}✅ Projet cloné${NC}"
else
    echo -e "${BLUE}🔄 3. Mise à jour du projet...${NC}"
    ssh_exec "
        cd $PROJECT_PATH
        git fetch origin
        git checkout $BRANCH
        git pull origin $BRANCH
    "
    echo -e "${GREEN}✅ Projet mis à jour${NC}"
fi
echo ""

# 4. Vérifier les nouveaux fichiers V2
echo -e "${BLUE}🔍 4. Vérification des fichiers V2...${NC}"
FILES_OK=true

for file in \
    "backend/services/propensity_predictor_v2.py" \
    "scripts/migrate_to_v2.py" \
    "AMELIORATIONS_PREDICTION.md" \
    "GUIDE_MIGRATION_V2.md" \
    "QUICKSTART_V2.md" \
    "test_v2.sh"
do
    if ssh_exec "test -f $PROJECT_PATH/$file"; then
        echo -e "${GREEN}  ✅ $file${NC}"
    else
        echo -e "${RED}  ❌ $file (manquant)${NC}"
        FILES_OK=false
    fi
done

if [ "$FILES_OK" = false ]; then
    echo ""
    echo -e "${RED}❌ Certains fichiers V2 sont manquants${NC}"
    echo "Assurez-vous que la branche $BRANCH est correcte"
    exit 1
fi
echo ""

# 5. Redémarrer le backend
echo -e "${BLUE}🔄 5. Redémarrage du backend...${NC}"
if ssh_exec "cd $PROJECT_PATH && docker-compose ps backend > /dev/null 2>&1"; then
    echo "Docker Compose détecté, redémarrage du backend..."
    ssh_exec "cd $PROJECT_PATH && docker-compose restart backend"
    echo -e "${GREEN}✅ Backend redémarré${NC}"

    # Attendre que le backend démarre
    echo "Attente du démarrage (10 secondes)..."
    sleep 10
else
    echo -e "${YELLOW}⚠️  Docker Compose non trouvé ou backend non démarré${NC}"
    echo "Vous devrez redémarrer manuellement le backend"
fi
echo ""

# 6. Rendre les scripts exécutables
echo -e "${BLUE}🔧 6. Configuration des scripts...${NC}"
ssh_exec "
    cd $PROJECT_PATH
    chmod +x test_v2.sh
    chmod +x scripts/migrate_to_v2.py
"
echo -e "${GREEN}✅ Scripts configurés${NC}"
echo ""

# 7. Tester l'API
echo -e "${BLUE}🧪 7. Test de l'API backend...${NC}"
API_TEST=$(ssh_exec "curl -s http://localhost:8003/ 2>&1" || echo "FAILED")

if echo "$API_TEST" | grep -q "ProspectScore Pro"; then
    echo -e "${GREEN}✅ API backend accessible${NC}"
    echo "$API_TEST"
else
    echo -e "${YELLOW}⚠️  API backend non accessible${NC}"
    echo "Vérifiez que le backend est démarré avec :"
    echo "  ssh $VPS_USER@$VPS_IP 'cd $PROJECT_PATH && docker-compose ps'"
fi
echo ""

# 8. Afficher les stats DVF
echo -e "${BLUE}📊 8. Statistiques DVF actuelles...${NC}"
STATS=$(ssh_exec "curl -s http://localhost:8003/api/admin/dvf/stats 2>&1" || echo "{}")
echo "$STATS" | python3 -m json.tool 2>/dev/null || echo "$STATS"
echo ""

# 9. Commandes pour tester la V2
echo -e "${BLUE}======================================================================"
echo "✅ DÉPLOIEMENT TERMINÉ"
echo "======================================================================${NC}"
echo ""
echo -e "${GREEN}🎯 Prochaines étapes :${NC}"
echo ""
echo "1️⃣ Se connecter au VPS :"
echo "   ssh $VPS_USER@$VPS_IP"
echo ""
echo "2️⃣ Aller dans le projet :"
echo "   cd $PROJECT_PATH"
echo ""
echo "3️⃣ Tester la V2 (mode dry-run) :"
echo "   python3 scripts/migrate_to_v2.py --dry-run --score-min 40 --batch-size 100"
echo ""
echo "4️⃣ Migrer toutes les données :"
echo "   python3 scripts/migrate_to_v2.py --score-min 0 --batch-size 500"
echo ""
echo "5️⃣ Tester avec le script automatique :"
echo "   ./test_v2.sh"
echo ""
echo "6️⃣ Ou via API directement :"
echo "   curl -X POST \"http://localhost:8003/api/admin/analyze-propensity-v2?score_min=40&limit=100\""
echo ""
echo -e "${BLUE}📚 Documentation :${NC}"
echo "  • AMELIORATIONS_PREDICTION.md : Détails techniques"
echo "  • GUIDE_MIGRATION_V2.md : Guide complet"
echo "  • QUICKSTART_V2.md : Guide rapide"
echo ""
echo -e "${GREEN}🚀 La V2 est prête à être testée !${NC}"
echo ""

#!/bin/bash
# ProspectScore Pro - Préparation du package de déploiement

echo "================================================"
echo "   Préparation du Package de Déploiement"
echo "================================================"
echo ""

# Couleurs
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

PACKAGE_NAME="prospectscore-deploy-$(date +%Y%m%d-%H%M%S).tar.gz"
OUTPUT_DIR="/mnt/user-data/outputs"

echo -e "${BLUE}Création de l'archive...${NC}"

# Créer l'archive
tar -czf $OUTPUT_DIR/$PACKAGE_NAME \
    --exclude='node_modules' \
    --exclude='.git' \
    --exclude='*.pyc' \
    --exclude='__pycache__' \
    --exclude='.DS_Store' \
    -C /home/claude/prospectscore-vps .

echo -e "${GREEN}✓ Archive créée: $PACKAGE_NAME${NC}"
echo ""

# Afficher les instructions
cat << 'EOF'
================================================
   INSTRUCTIONS DE DÉPLOIEMENT
================================================

1. Copier sur votre VPS:
   scp /chemin/vers/prospectscore-deploy.tar.gz root@votre-vps.com:/tmp/

2. Sur le VPS, extraire:
   cd /tmp
   mkdir -p prospectscore-deploy
   tar -xzf prospectscore-deploy.tar.gz -C prospectscore-deploy/
   cd prospectscore-deploy

3. Rendre les scripts exécutables:
   chmod +x audit-vps.sh deploy.sh

4. Auditer le VPS (optionnel):
   sudo ./audit-vps.sh

5. Déployer:
   sudo ./deploy.sh

================================================

L'application sera accessible sur:
http://score.2a-immobilier.fr

Consultez le README.md pour plus de détails.

EOF

echo ""
echo -e "${GREEN}Package prêt dans: $OUTPUT_DIR/${NC}"
echo ""

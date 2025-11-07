#!/bin/bash
# Script de mise à jour de la configuration Nginx pour ProspectScore Pro
# Usage: sudo ./update-nginx.sh

set -e

# Couleurs
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   ProspectScore Pro - Mise à jour Nginx       ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════╝${NC}"
echo ""

# Vérification root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}❌ Ce script doit être exécuté en root (sudo)${NC}"
    exit 1
fi

# Configuration
NGINX_CONF="/etc/nginx/sites-available/prospectscore-pro"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${YELLOW}📁 Répertoire du projet: $PROJECT_DIR${NC}"
echo ""

# 1. Sauvegarde de l'ancienne configuration
if [ -f "$NGINX_CONF" ]; then
    BACKUP_FILE="${NGINX_CONF}.backup.$(date +%Y%m%d-%H%M%S)"
    echo -e "${BLUE}💾 Sauvegarde de la configuration actuelle...${NC}"
    cp "$NGINX_CONF" "$BACKUP_FILE"
    echo -e "${GREEN}   ✓ Sauvegardé dans: $BACKUP_FILE${NC}"
    echo ""
fi

# 2. Copie de la nouvelle configuration
echo -e "${BLUE}📋 Installation de la nouvelle configuration...${NC}"
cp "$PROJECT_DIR/nginx.conf" "$NGINX_CONF"
echo -e "${GREEN}   ✓ Configuration copiée${NC}"
echo ""

# 3. Activation du site (si pas déjà fait)
if [ ! -L "/etc/nginx/sites-enabled/prospectscore-pro" ]; then
    echo -e "${BLUE}🔗 Activation du site...${NC}"
    ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/prospectscore-pro
    echo -e "${GREEN}   ✓ Site activé${NC}"
    echo ""
fi

# 4. Test de la configuration
echo -e "${BLUE}🔍 Test de la configuration Nginx...${NC}"
if nginx -t; then
    echo -e "${GREEN}   ✓ Configuration valide${NC}"
    echo ""
else
    echo -e "${RED}   ❌ Erreur dans la configuration${NC}"
    echo -e "${YELLOW}   ⚠️  Restauration de la sauvegarde...${NC}"
    if [ -f "$BACKUP_FILE" ]; then
        cp "$BACKUP_FILE" "$NGINX_CONF"
        echo -e "${GREEN}   ✓ Configuration restaurée${NC}"
    fi
    exit 1
fi

# 5. Rechargement de Nginx
echo -e "${BLUE}🔄 Rechargement de Nginx...${NC}"
if systemctl reload nginx; then
    echo -e "${GREEN}   ✓ Nginx rechargé avec succès${NC}"
    echo ""
else
    echo -e "${RED}   ❌ Erreur lors du rechargement${NC}"
    exit 1
fi

# 6. Vérification du statut
echo -e "${BLUE}📊 Statut de Nginx:${NC}"
systemctl status nginx --no-pager | head -5
echo ""

# 7. Test de connectivité
echo -e "${BLUE}🧪 Test de connectivité...${NC}"
echo -e "${YELLOW}   Backend (port 8003):${NC}"
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8003/ | grep -q "200"; then
    echo -e "${GREEN}      ✓ Backend accessible${NC}"
else
    echo -e "${RED}      ⚠️  Backend non accessible (vérifier docker-compose)${NC}"
fi

echo -e "${YELLOW}   Frontend (port 3003):${NC}"
if curl -s -o /dev/null -w "%{http_code}" http://localhost:3003/ | grep -q "200"; then
    echo -e "${GREEN}      ✓ Frontend accessible${NC}"
else
    echo -e "${RED}      ⚠️  Frontend non accessible (vérifier docker-compose)${NC}"
fi
echo ""

# 8. Résumé
echo -e "${GREEN}╔════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║            ✅ MISE À JOUR TERMINÉE              ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}📝 Tests à effectuer:${NC}"
echo "   • https://score.2a-immobilier.com/api/"
echo "   • https://score.2a-immobilier.com/api/public/stats"
echo "   • https://score.2a-immobilier.com/docs"
echo "   • https://score.2a-immobilier.com/"
echo ""
echo -e "${YELLOW}💡 Commandes utiles:${NC}"
echo "   • Voir les logs Nginx: tail -f /var/log/nginx/prospectscore_error.log"
echo "   • Recharger Nginx: sudo systemctl reload nginx"
echo "   • Voir le statut: sudo systemctl status nginx"
echo ""

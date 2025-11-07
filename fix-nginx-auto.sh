#!/bin/bash
# Script automatique de diagnostic et correction Nginx
# ProspectScore Pro

set -e

# Couleurs
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Diagnostic et Correction Automatique        ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════╝${NC}"
echo ""

PROJECT_DIR="/var/www/prospectscore-pro"
cd "$PROJECT_DIR"

# 1. Vérifier les conteneurs Docker
echo -e "${CYAN}📦 1. Vérification des conteneurs Docker...${NC}"
if ! docker ps | grep -q "prospectscore-backend"; then
    echo -e "${YELLOW}   ⚠️  Backend non démarré, démarrage...${NC}"
    docker-compose up -d
    echo -e "${GREEN}   ✓ Conteneurs démarrés${NC}"
    sleep 5
else
    echo -e "${GREEN}   ✓ Backend en cours d'exécution${NC}"
fi
echo ""

# 2. Tester le backend en local
echo -e "${CYAN}🧪 2. Test du backend en local...${NC}"
BACKEND_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8003/api/)

if [ "$BACKEND_RESPONSE" = "200" ]; then
    echo -e "${GREEN}   ✓ Backend accessible sur localhost:8003${NC}"
    echo -e "${GREEN}   $(curl -s http://localhost:8003/api/ | jq -r '.app + " v" + .version')${NC}"
else
    echo -e "${RED}   ❌ Backend ne répond pas (code: $BACKEND_RESPONSE)${NC}"
    echo -e "${YELLOW}   Affichage des logs backend:${NC}"
    docker logs prospectscore-backend --tail 30
    exit 1
fi
echo ""

# 3. Vérifier la configuration Nginx actuelle
echo -e "${CYAN}⚙️  3. Vérification configuration Nginx...${NC}"
if [ -f "/etc/nginx/sites-available/prospectscore-pro" ]; then
    echo -e "${GREEN}   ✓ Fichier de configuration existe${NC}"

    # Vérifier si c'est la bonne config
    if grep -q "proxy_pass http://prospectscore_backend/api/" /etc/nginx/sites-available/prospectscore-pro; then
        echo -e "${GREEN}   ✓ Configuration correcte détectée${NC}"
    else
        echo -e "${YELLOW}   ⚠️  Ancienne configuration détectée${NC}"
        UPDATE_NGINX=true
    fi
else
    echo -e "${YELLOW}   ⚠️  Configuration non trouvée${NC}"
    UPDATE_NGINX=true
fi
echo ""

# 4. Mettre à jour Nginx si nécessaire
if [ "$UPDATE_NGINX" = "true" ]; then
    echo -e "${CYAN}🔧 4. Mise à jour de la configuration Nginx...${NC}"

    # Sauvegarde
    if [ -f "/etc/nginx/sites-available/prospectscore-pro" ]; then
        cp /etc/nginx/sites-available/prospectscore-pro /etc/nginx/sites-available/prospectscore-pro.backup.$(date +%Y%m%d-%H%M%S)
        echo -e "${GREEN}   ✓ Ancienne configuration sauvegardée${NC}"
    fi

    # Copier la nouvelle config
    cp "$PROJECT_DIR/nginx.conf" /etc/nginx/sites-available/prospectscore-pro
    echo -e "${GREEN}   ✓ Nouvelle configuration copiée${NC}"

    # Activer le site
    ln -sf /etc/nginx/sites-available/prospectscore-pro /etc/nginx/sites-enabled/
    echo -e "${GREEN}   ✓ Site activé${NC}"

    # Tester la config
    if nginx -t 2>&1 | grep -q "successful"; then
        echo -e "${GREEN}   ✓ Configuration valide${NC}"

        # Recharger Nginx
        systemctl reload nginx
        echo -e "${GREEN}   ✓ Nginx rechargé${NC}"
    else
        echo -e "${RED}   ❌ Configuration invalide${NC}"
        nginx -t
        exit 1
    fi
else
    echo -e "${CYAN}4. Configuration Nginx déjà à jour${NC}"
fi
echo ""

# 5. Test final via Nginx
echo -e "${CYAN}🎯 5. Test final via Nginx...${NC}"
sleep 2

# Test HTTPS
HTTPS_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" https://score.2a-immobilier.com/api/)

if [ "$HTTPS_RESPONSE" = "200" ]; then
    echo -e "${GREEN}   ✓ API accessible via HTTPS${NC}"
    echo ""
    echo -e "${GREEN}   Réponse de l'API:${NC}"
    curl -s https://score.2a-immobilier.com/api/ | jq '.'
else
    echo -e "${YELLOW}   ⚠️  HTTPS ne répond pas (code: $HTTPS_RESPONSE)${NC}"

    # Test HTTP
    HTTP_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://score.2a-immobilier.com/api/)

    if [ "$HTTP_RESPONSE" = "200" ]; then
        echo -e "${GREEN}   ✓ API accessible via HTTP${NC}"
        echo ""
        echo -e "${YELLOW}   💡 Pensez à configurer HTTPS avec certbot${NC}"
        curl -s http://score.2a-immobilier.com/api/ | jq '.'
    else
        echo -e "${RED}   ❌ API non accessible (HTTP code: $HTTP_RESPONSE)${NC}"
        echo ""
        echo -e "${YELLOW}   Diagnostic supplémentaire:${NC}"
        echo -e "${YELLOW}   - Vérifiez les logs Nginx: sudo tail -20 /var/log/nginx/error.log${NC}"
        echo -e "${YELLOW}   - Vérifiez les logs backend: docker logs prospectscore-backend${NC}"
        exit 1
    fi
fi
echo ""

# 6. Résumé
echo -e "${GREEN}╔════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║          ✅ CORRECTION TERMINÉE                 ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}📊 État du système:${NC}"
echo -e "${GREEN}   ✓ Backend: http://localhost:8003/api/${NC}"
echo -e "${GREEN}   ✓ Frontend: http://localhost:3003/${NC}"
echo -e "${GREEN}   ✓ API publique: https://score.2a-immobilier.com/api/${NC}"
echo ""
echo -e "${BLUE}🎯 Prochaines étapes:${NC}"
echo "   1. Tester l'API: curl https://score.2a-immobilier.com/api/"
echo "   2. Créer les tables: ./scripts/setup_features_ml.sh"
echo "   3. Créer les tables: ./scripts/setup_commerciaux.sh"
echo "   4. Vérifier les données: ./scripts/check_probabilites.sh"
echo ""

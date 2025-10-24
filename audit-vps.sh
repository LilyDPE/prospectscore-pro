#!/bin/bash
# ProspectScore Pro - Audit VPS
# Détecte l'infrastructure existante avant déploiement

set -e

echo "================================================"
echo "   ProspectScore Pro - Audit VPS"
echo "================================================"
echo ""

# Couleurs
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Variables
AUDIT_FILE="/tmp/vps-audit-$(date +%Y%m%d-%H%M%S).txt"

echo "Génération du rapport d'audit dans: $AUDIT_FILE"
echo "" | tee $AUDIT_FILE

# Fonction de vérification
check_service() {
    local service=$1
    local command=$2
    
    echo -n "Vérification $service... " | tee -a $AUDIT_FILE
    
    if eval $command &>/dev/null; then
        echo -e "${GREEN}✓ Installé${NC}" | tee -a $AUDIT_FILE
        return 0
    else
        echo -e "${RED}✗ Non installé${NC}" | tee -a $AUDIT_FILE
        return 1
    fi
}

# Informations système
echo "=== SYSTÈME ===" | tee -a $AUDIT_FILE
echo "OS: $(cat /etc/os-release | grep PRETTY_NAME | cut -d'"' -f2)" | tee -a $AUDIT_FILE
echo "RAM: $(free -h | awk '/^Mem:/ {print $2}')" | tee -a $AUDIT_FILE
echo "Disque: $(df -h / | awk 'NR==2 {print $2 " (utilisé: " $3 ")"}')" | tee -a $AUDIT_FILE
echo "" | tee -a $AUDIT_FILE

# Vérification des services
echo "=== SERVICES INSTALLÉS ===" | tee -a $AUDIT_FILE

DOCKER_INSTALLED=false
DOCKER_COMPOSE_INSTALLED=false
NGINX_INSTALLED=false
POSTGRES_INSTALLED=false
POSTGRES_DOCKER=false

if check_service "Docker" "docker --version"; then
    DOCKER_INSTALLED=true
    docker --version | tee -a $AUDIT_FILE
    
    # Vérifier les conteneurs en cours
    echo "  Conteneurs actifs:" | tee -a $AUDIT_FILE
    docker ps --format "    - {{.Names}} ({{.Image}})" | tee -a $AUDIT_FILE
    
    # Vérifier si PostgreSQL tourne dans Docker
    if docker ps | grep -q postgres; then
        POSTGRES_DOCKER=true
        echo "  ${GREEN}PostgreSQL détecté dans Docker${NC}" | tee -a $AUDIT_FILE
    fi
fi

if check_service "Docker Compose" "docker-compose --version"; then
    DOCKER_COMPOSE_INSTALLED=true
    docker-compose --version | tee -a $AUDIT_FILE
fi

if check_service "Nginx" "nginx -v"; then
    NGINX_INSTALLED=true
    nginx -v 2>&1 | tee -a $AUDIT_FILE
    
    # Vérifier les sites actifs
    if [ -d "/etc/nginx/sites-enabled" ]; then
        echo "  Sites actifs:" | tee -a $AUDIT_FILE
        ls /etc/nginx/sites-enabled/ | sed 's/^/    - /' | tee -a $AUDIT_FILE
    fi
fi

if check_service "PostgreSQL" "psql --version"; then
    POSTGRES_INSTALLED=true
    psql --version | tee -a $AUDIT_FILE
fi

if check_service "Git" "git --version"; then
    git --version | tee -a $AUDIT_FILE
fi

if check_service "Node.js" "node --version"; then
    node --version | tee -a $AUDIT_FILE
fi

if check_service "Python" "python3 --version"; then
    python3 --version | tee -a $AUDIT_FILE
fi

echo "" | tee -a $AUDIT_FILE

# Ports utilisés
echo "=== PORTS UTILISÉS ===" | tee -a $AUDIT_FILE
echo "Ports en écoute:" | tee -a $AUDIT_FILE
netstat -tuln | grep LISTEN | awk '{print "  - " $4}' | sort -u | tee -a $AUDIT_FILE
echo "" | tee -a $AUDIT_FILE

# Espace disque
echo "=== ESPACE DISQUE ===" | tee -a $AUDIT_FILE
df -h | grep -E "Filesystem|/$|/mnt|/var" | tee -a $AUDIT_FILE
echo "" | tee -a $AUDIT_FILE

# Recherche de DPE Pro et 2A Social
echo "=== APPLICATIONS DÉTECTÉES ===" | tee -a $AUDIT_FILE

if [ -d "/var/www/dpe-pro" ] || [ -d "/home/*/dpe-pro" ] || docker ps | grep -q dpe; then
    echo -e "${GREEN}✓ DPE Pro détecté${NC}" | tee -a $AUDIT_FILE
fi

if [ -d "/var/www/2a-social" ] || [ -d "/home/*/2a-social" ] || docker ps | grep -q social; then
    echo -e "${GREEN}✓ 2A Social détecté${NC}" | tee -a $AUDIT_FILE
fi

# Recherche de la base DPE ADEME
echo "" | tee -a $AUDIT_FILE
echo "=== BASE DPE ADEME ===" | tee -a $AUDIT_FILE

DPE_DB_FOUND=false

if [ "$POSTGRES_DOCKER" = true ]; then
    # Recherche dans Docker
    DB_CONTAINER=$(docker ps | grep postgres | awk '{print $1}' | head -1)
    if [ ! -z "$DB_CONTAINER" ]; then
        echo "Recherche dans PostgreSQL Docker..." | tee -a $AUDIT_FILE
        DATABASES=$(docker exec $DB_CONTAINER psql -U postgres -lqt 2>/dev/null | cut -d \| -f 1 | grep -v template | grep -v "^ *$" | sed 's/^ *//;s/ *$//')
        
        for db in $DATABASES; do
            TABLES=$(docker exec $DB_CONTAINER psql -U postgres -d $db -c "\dt" 2>/dev/null | grep -i dpe | wc -l)
            if [ $TABLES -gt 0 ]; then
                echo -e "${GREEN}✓ Base DPE trouvée: $db${NC}" | tee -a $AUDIT_FILE
                DPE_DB_FOUND=true
            fi
        done
    fi
elif [ "$POSTGRES_INSTALLED" = true ]; then
    # Recherche en local
    echo "Recherche dans PostgreSQL local..." | tee -a $AUDIT_FILE
    DATABASES=$(sudo -u postgres psql -lqt 2>/dev/null | cut -d \| -f 1 | grep -v template | grep -v "^ *$" | sed 's/^ *//;s/ *$//' || echo "")
    
    for db in $DATABASES; do
        TABLES=$(sudo -u postgres psql -d $db -c "\dt" 2>/dev/null | grep -i dpe | wc -l)
        if [ $TABLES -gt 0 ]; then
            echo -e "${GREEN}✓ Base DPE trouvée: $db${NC}" | tee -a $AUDIT_FILE
            DPE_DB_FOUND=true
        fi
    done
fi

if [ "$DPE_DB_FOUND" = false ]; then
    echo -e "${YELLOW}⚠ Base DPE ADEME non trouvée${NC}" | tee -a $AUDIT_FILE
    echo "  → Sera téléchargée pendant l'installation" | tee -a $AUDIT_FILE
fi

# Recommandations
echo "" | tee -a $AUDIT_FILE
echo "=== RECOMMANDATIONS ===" | tee -a $AUDIT_FILE

if [ "$DOCKER_INSTALLED" = false ]; then
    echo -e "${YELLOW}⚠ Docker non installé - sera installé${NC}" | tee -a $AUDIT_FILE
fi

if [ "$DOCKER_COMPOSE_INSTALLED" = false ]; then
    echo -e "${YELLOW}⚠ Docker Compose non installé - sera installé${NC}" | tee -a $AUDIT_FILE
fi

if [ "$NGINX_INSTALLED" = false ]; then
    echo -e "${YELLOW}⚠ Nginx non installé - sera installé${NC}" | tee -a $AUDIT_FILE
fi

if [ "$POSTGRES_INSTALLED" = false ] && [ "$POSTGRES_DOCKER" = false ]; then
    echo -e "${YELLOW}⚠ PostgreSQL non installé - conteneur Docker sera créé${NC}" | tee -a $AUDIT_FILE
fi

# Port recommendations
if netstat -tuln | grep -q ":3000 "; then
    echo -e "${YELLOW}⚠ Port 3000 déjà utilisé - configuration nécessaire${NC}" | tee -a $AUDIT_FILE
fi

if netstat -tuln | grep -q ":8000 "; then
    echo -e "${YELLOW}⚠ Port 8000 déjà utilisé - configuration nécessaire${NC}" | tee -a $AUDIT_FILE
fi

echo "" | tee -a $AUDIT_FILE
echo "=== RÉSUMÉ ===" | tee -a $AUDIT_FILE
echo "Infrastructure existante détectée:" | tee -a $AUDIT_FILE
echo "  - Docker: $DOCKER_INSTALLED" | tee -a $AUDIT_FILE
echo "  - Docker Compose: $DOCKER_COMPOSE_INSTALLED" | tee -a $AUDIT_FILE
echo "  - Nginx: $NGINX_INSTALLED" | tee -a $AUDIT_FILE
echo "  - PostgreSQL: $POSTGRES_INSTALLED ou Docker=$POSTGRES_DOCKER" | tee -a $AUDIT_FILE
echo "  - Base DPE: $DPE_DB_FOUND" | tee -a $AUDIT_FILE

echo ""
echo "================================================"
echo "Rapport complet sauvegardé: $AUDIT_FILE"
echo "================================================"
echo ""
echo -e "${GREEN}Prêt pour l'installation !${NC}"
echo "Lancer: sudo ./deploy.sh"

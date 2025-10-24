#!/bin/bash
# ProspectScore Pro - Déploiement VPS
# Installation intelligente qui s'adapte à l'infrastructure existante

set -e

echo "================================================"
echo "   ProspectScore Pro - Déploiement VPS"
echo "================================================"
echo ""

# Vérification root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Ce script doit être exécuté en root (sudo)"
    exit 1
fi

# Couleurs
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
APP_NAME="prospectscore-pro"
APP_DIR="/var/www/$APP_NAME"
DOMAIN="score.2a-immobilier.fr"
BACKEND_PORT=8003
FRONTEND_PORT=3003
DB_NAME="prospectscore"
DB_USER="prospectscore"
DB_PASSWORD=$(openssl rand -base64 32)

echo -e "${BLUE}Configuration:${NC}"
echo "  - Application: $APP_NAME"
echo "  - Répertoire: $APP_DIR"
echo "  - Domaine: $DOMAIN"
echo "  - Backend: localhost:$BACKEND_PORT"
echo "  - Frontend: localhost:$FRONTEND_PORT"
echo ""

# Détection de l'infrastructure
echo -e "${YELLOW}=== Détection de l'infrastructure ===${NC}"

DOCKER_INSTALLED=false
NGINX_INSTALLED=false
POSTGRES_DOCKER=false

if command -v docker &> /dev/null; then
    DOCKER_INSTALLED=true
    echo -e "${GREEN}✓ Docker détecté${NC}"
    
    if docker ps | grep -q postgres; then
        POSTGRES_DOCKER=true
        echo -e "${GREEN}✓ PostgreSQL Docker détecté${NC}"
    fi
else
    echo -e "${YELLOW}⚠ Docker non installé - installation...${NC}"
fi

if command -v nginx &> /dev/null; then
    NGINX_INSTALLED=true
    echo -e "${GREEN}✓ Nginx détecté${NC}"
else
    echo -e "${YELLOW}⚠ Nginx non installé - installation...${NC}"
fi

echo ""

# Installation des dépendances manquantes
if [ "$DOCKER_INSTALLED" = false ]; then
    echo -e "${BLUE}Installation de Docker...${NC}"
    apt-get update
    apt-get install -y apt-transport-https ca-certificates curl software-properties-common
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add -
    add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io
    
    # Docker Compose
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    
    echo -e "${GREEN}✓ Docker installé${NC}"
fi

if [ "$NGINX_INSTALLED" = false ]; then
    echo -e "${BLUE}Installation de Nginx...${NC}"
    apt-get update
    apt-get install -y nginx
    systemctl enable nginx
    systemctl start nginx
    echo -e "${GREEN}✓ Nginx installé${NC}"
fi

# Création du répertoire d'application
echo ""
echo -e "${BLUE}=== Configuration de l'application ===${NC}"

if [ -d "$APP_DIR" ]; then
    echo -e "${YELLOW}⚠ Répertoire existant - sauvegarde...${NC}"
    mv $APP_DIR ${APP_DIR}.backup.$(date +%Y%m%d-%H%M%S)
fi

mkdir -p $APP_DIR
cd $APP_DIR

# Copie des fichiers
echo "Copie des fichiers..."
cp -r /tmp/prospectscore-deploy/* $APP_DIR/

# Configuration de la base de données
echo ""
echo -e "${BLUE}=== Configuration PostgreSQL ===${NC}"

if [ "$POSTGRES_DOCKER" = true ]; then
    echo "Utilisation du PostgreSQL Docker existant..."
    DB_CONTAINER=$(docker ps | grep postgres | awk '{print $1}' | head -1)
    
    # Création de la base et de l'utilisateur
    docker exec $DB_CONTAINER psql -U postgres -c "CREATE DATABASE $DB_NAME;" 2>/dev/null || echo "Base déjà existante"
    docker exec $DB_CONTAINER psql -U postgres -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';" 2>/dev/null || echo "Utilisateur déjà existant"
    docker exec $DB_CONTAINER psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"
    
    # Récupération de l'IP du conteneur
    DB_HOST=$(docker inspect $DB_CONTAINER | grep '"IPAddress"' | head -1 | awk -F'"' '{print $4}')
    echo -e "${GREEN}✓ Base de données créée sur PostgreSQL Docker${NC}"
else
    echo "Création d'un conteneur PostgreSQL..."
    docker run -d \
        --name postgres-prospectscore \
        --restart always \
        -e POSTGRES_DB=$DB_NAME \
        -e POSTGRES_USER=$DB_USER \
        -e POSTGRES_PASSWORD=$DB_PASSWORD \
        -v $APP_DIR/data/postgres:/var/lib/postgresql/data \
        -p 5432:5432 \
        postgres:15-alpine
    
    DB_HOST="postgres-prospectscore"
    echo -e "${GREEN}✓ Conteneur PostgreSQL créé${NC}"
fi

# Génération du fichier .env
cat > $APP_DIR/.env <<EOF
# ProspectScore Pro - Configuration
NODE_ENV=production

# Base de données
DATABASE_URL=postgresql://$DB_USER:$DB_PASSWORD@$DB_HOST:5432/$DB_NAME
DB_HOST=$DB_HOST
DB_PORT=5432
DB_NAME=$DB_NAME
DB_USER=$DB_USER
DB_PASSWORD=$DB_PASSWORD

# API
API_URL=https://$DOMAIN/api
API_PORT=$BACKEND_PORT

# Frontend
FRONTEND_URL=https://$DOMAIN
FRONTEND_PORT=$FRONTEND_PORT

# JWT Secret
JWT_SECRET=$(openssl rand -base64 64)

# 2A Immobilier Branding
BRAND_PRIMARY=#04264b
BRAND_SECONDARY=#b4e434
BRAND_TERTIARY=#c7c7c7
EOF

echo -e "${GREEN}✓ Configuration .env créée${NC}"

# Configuration Docker Compose
cat > $APP_DIR/docker-compose.yml <<EOF
version: '3.8'

services:
  backend:
    build: ./backend
    container_name: prospectscore-backend
    restart: always
    ports:
      - "$BACKEND_PORT:8000"
    environment:
      - DATABASE_URL=\${DATABASE_URL}
      - JWT_SECRET=\${JWT_SECRET}
    volumes:
      - ./backend:/app
      - ./data/uploads:/app/uploads
    depends_on:
      - db-setup

  frontend:
    build: ./frontend
    container_name: prospectscore-frontend
    restart: always
    ports:
      - "$FRONTEND_PORT:3000"
    environment:
      - REACT_APP_API_URL=\${API_URL}
      - REACT_APP_BRAND_PRIMARY=\${BRAND_PRIMARY}
      - REACT_APP_BRAND_SECONDARY=\${BRAND_SECONDARY}
    volumes:
      - ./frontend:/app
      - /app/node_modules

  db-setup:
    image: postgres:15-alpine
    container_name: prospectscore-db-setup
    command: >
      sh -c "echo 'Database ready for connection'"
    environment:
      - DATABASE_URL=\${DATABASE_URL}
EOF

echo -e "${GREEN}✓ docker-compose.yml créé${NC}"

# Configuration Nginx
echo ""
echo -e "${BLUE}=== Configuration Nginx ===${NC}"

cat > /etc/nginx/sites-available/$APP_NAME <<EOF
# ProspectScore Pro - Nginx Configuration

upstream prospectscore_backend {
    server localhost:$BACKEND_PORT;
}

upstream prospectscore_frontend {
    server localhost:$FRONTEND_PORT;
}

server {
    listen 80;
    server_name $DOMAIN;

    # Redirection HTTPS (à activer après certbot)
    # return 301 https://\$server_name\$request_uri;

    client_max_body_size 50M;

    # Frontend
    location / {
        proxy_pass http://prospectscore_frontend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_cache_bypass \$http_upgrade;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # Backend API
    location /api {
        proxy_pass http://prospectscore_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_cache_bypass \$http_upgrade;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # Documentation API
    location /docs {
        proxy_pass http://prospectscore_backend/docs;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
    }
}

# Configuration HTTPS (après certbot)
# server {
#     listen 443 ssl http2;
#     server_name $DOMAIN;
#
#     ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
#     ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;
#     ssl_protocols TLSv1.2 TLSv1.3;
#     ssl_ciphers HIGH:!aNULL:!MD5;
#
#     client_max_body_size 50M;
#
#     location / {
#         proxy_pass http://prospectscore_frontend;
#         # ... (même config que HTTP)
#     }
#
#     location /api {
#         proxy_pass http://prospectscore_backend;
#         # ... (même config que HTTP)
#     }
# }
EOF

# Activation du site
ln -sf /etc/nginx/sites-available/$APP_NAME /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

echo -e "${GREEN}✓ Configuration Nginx activée${NC}"

# Construction et démarrage des conteneurs
echo ""
echo -e "${BLUE}=== Démarrage de l'application ===${NC}"

cd $APP_DIR
docker-compose build
docker-compose up -d

echo ""
echo -e "${GREEN}✓ Application démarrée !${NC}"

# Attente du démarrage
echo ""
echo "Attente du démarrage des services..."
sleep 10

# Vérification de l'état
echo ""
echo -e "${BLUE}=== État des services ===${NC}"
docker-compose ps

# Installation de Certbot (optionnel)
echo ""
echo -e "${YELLOW}=== Configuration HTTPS (optionnel) ===${NC}"
echo "Pour activer HTTPS, exécuter:"
echo "  1. apt-get install -y certbot python3-certbot-nginx"
echo "  2. certbot --nginx -d $DOMAIN"
echo "  3. Décommenter la section HTTPS dans /etc/nginx/sites-available/$APP_NAME"
echo "  4. systemctl reload nginx"

# Sauvegarde des credentials
echo ""
echo -e "${BLUE}=== Informations de connexion ===${NC}"
cat > $APP_DIR/CREDENTIALS.txt <<EOF
ProspectScore Pro - Informations de connexion
==============================================

URL: http://$DOMAIN (ou https:// après certbot)
API Docs: http://$DOMAIN/docs

Base de données:
  Host: $DB_HOST
  Port: 5432
  Database: $DB_NAME
  User: $DB_USER
  Password: $DB_PASSWORD

Répertoire: $APP_DIR

Commandes utiles:
  - Logs: cd $APP_DIR && docker-compose logs -f
  - Restart: cd $APP_DIR && docker-compose restart
  - Stop: cd $APP_DIR && docker-compose down
  - Rebuild: cd $APP_DIR && docker-compose up -d --build

Fichier généré le: $(date)
EOF

echo -e "${GREEN}✓ Credentials sauvegardés dans: $APP_DIR/CREDENTIALS.txt${NC}"

echo ""
echo "================================================"
echo -e "${GREEN}   DÉPLOIEMENT TERMINÉ !${NC}"
echo "================================================"
echo ""
echo "Accès:"
echo "  - Frontend: http://$DOMAIN"
echo "  - API: http://$DOMAIN/api"
echo "  - Docs: http://$DOMAIN/docs"
echo ""
echo "Credentials: $APP_DIR/CREDENTIALS.txt"
echo ""
echo -e "${YELLOW}Note: Penser à configurer le DNS pour pointer $DOMAIN vers ce serveur${NC}"

# ProspectScore Pro - Déploiement VPS

Système de scoring de vendeurs potentiels pour 2A Immobilier.

## 📦 Contenu du Package

```
prospectscore-vps/
├── audit-vps.sh              # Script d'audit de l'infrastructure
├── deploy.sh                 # Script de déploiement automatique
├── backend/                  # API FastAPI
│   ├── Dockerfile
│   ├── requirements.txt
│   └── main.py
├── frontend/                 # Interface React
│   ├── Dockerfile
│   ├── package.json
│   ├── public/
│   └── src/
├── docker-compose.yml
└── README.md                 # Ce fichier
```

## 🚀 Installation Rapide (3 étapes)

### 1. Copier le package sur le VPS

```bash
# Sur votre Mac
cd /chemin/vers/prospectscore-vps
tar -czf prospectscore-deploy.tar.gz *

# Copier sur le VPS
scp prospectscore-deploy.tar.gz root@votre-vps.com:/tmp/

# Se connecter au VPS
ssh root@votre-vps.com
```

### 2. Extraire et préparer

```bash
# Sur le VPS
cd /tmp
mkdir -p prospectscore-deploy
tar -xzf prospectscore-deploy.tar.gz -C prospectscore-deploy/
cd prospectscore-deploy

# Rendre les scripts exécutables
chmod +x audit-vps.sh deploy.sh
```

### 3. Lancer le déploiement

```bash
# D'abord, auditer le VPS (optionnel mais recommandé)
sudo ./audit-vps.sh

# Puis déployer
sudo ./deploy.sh
```

**C'est tout !** Le script s'occupe de :
- ✅ Installer Docker et Docker Compose si nécessaire
- ✅ Installer Nginx si nécessaire
- ✅ Créer la base de données PostgreSQL
- ✅ Configurer les conteneurs
- ✅ Configurer Nginx en reverse proxy
- ✅ Démarrer l'application

## 🌐 Configuration DNS

Avant d'accéder à l'application, configurer le DNS :

1. Dans votre interface OVH (ou autre registrar)
2. Ajouter un enregistrement A :
   ```
   Nom : score
   Type : A
   Valeur : IP de votre VPS
   TTL : 3600
   ```

3. Attendre la propagation DNS (5-30 minutes)

## 🔒 Activer HTTPS (Let's Encrypt)

Une fois le DNS configuré :

```bash
# Sur le VPS
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d score.2a-immobilier.fr

# Suivre les instructions interactives
```

Le certificat se renouvellera automatiquement.

## 📊 Accéder à l'Application

Après déploiement :

- **Frontend** : http://score.2a-immobilier.fr (ou https:// après certbot)
- **API** : http://score.2a-immobilier.fr/api
- **Documentation API** : http://score.2a-immobilier.fr/docs

### Premier utilisateur

Créer un compte depuis l'interface de login (onglet "Inscription").

## 🗂️ Base DPE ADEME

### Option 1 : Base existante

Si vous avez déjà la base DPE ADEME sur votre VPS (depuis DPE Pro) :

```bash
# Le script détectera automatiquement la base
# ProspectScore Pro utilisera la même instance PostgreSQL
```

### Option 2 : Importer la base

Si vous n'avez pas encore la base DPE :

```bash
# Télécharger les données ADEME
cd /var/www/prospectscore-pro
wget https://data.ademe.fr/data-fair/api/v1/datasets/dpe-v2-logements-existants/full -O dpe_data.csv

# Importer dans PostgreSQL
docker exec -i prospectscore-backend python3 << 'EOF'
import pandas as pd
from sqlalchemy import create_engine
import os

# Connexion DB
engine = create_engine(os.getenv("DATABASE_URL"))

# Lire et insérer par chunks
chunksize = 10000
for chunk in pd.read_csv('/app/dpe_data.csv', chunksize=chunksize, low_memory=False):
    chunk.to_sql('dpe_ademe', engine, if_exists='append', index=False)
    
print("Import terminé!")
EOF
```

## 🛠️ Commandes Utiles

### Gérer l'application

```bash
cd /var/www/prospectscore-pro

# Voir les logs
docker-compose logs -f

# Redémarrer
docker-compose restart

# Arrêter
docker-compose down

# Reconstruire et redémarrer
docker-compose up -d --build

# Voir l'état des conteneurs
docker-compose ps
```

### Gérer la base de données

```bash
# Se connecter à PostgreSQL
docker exec -it postgres-prospectscore psql -U prospectscore -d prospectscore

# Backup de la base
docker exec postgres-prospectscore pg_dump -U prospectscore prospectscore > backup.sql

# Restaurer une base
docker exec -i postgres-prospectscore psql -U prospectscore prospectscore < backup.sql
```

### Logs Nginx

```bash
# Voir les logs d'accès
sudo tail -f /var/log/nginx/access.log

# Voir les logs d'erreur
sudo tail -f /var/log/nginx/error.log

# Recharger la config Nginx
sudo nginx -t && sudo systemctl reload nginx
```

## 🔧 Configuration Avancée

### Changer le port

Si les ports 8003 ou 3003 sont déjà utilisés :

1. Éditer `/var/www/prospectscore-pro/.env`
2. Changer `BACKEND_PORT` et `FRONTEND_PORT`
3. Éditer `/etc/nginx/sites-available/prospectscore-pro`
4. Adapter les directives `proxy_pass`
5. Redémarrer :
   ```bash
   docker-compose down
   docker-compose up -d
   sudo systemctl reload nginx
   ```

### Variables d'environnement

Fichier `.env` dans `/var/www/prospectscore-pro/` :

```bash
# Base de données
DATABASE_URL=postgresql://...
DB_HOST=...
DB_PORT=5432
DB_NAME=prospectscore
DB_USER=prospectscore
DB_PASSWORD=...

# API
API_URL=https://score.2a-immobilier.fr/api
API_PORT=8003

# Frontend
FRONTEND_URL=https://score.2a-immobilier.fr
FRONTEND_PORT=3003

# Security
JWT_SECRET=...

# Branding 2A Immobilier
BRAND_PRIMARY=#04264b
BRAND_SECONDARY=#b4e434
BRAND_TERTIARY=#c7c7c7
```

## 🔐 Sécurité

### Credentials sauvegardés

Tous les credentials sont dans :
```bash
cat /var/www/prospectscore-pro/CREDENTIALS.txt
```

⚠️ **Garder ce fichier sécurisé !**

### Firewall

```bash
# Autoriser HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 22/tcp  # SSH
sudo ufw enable
```

## 📈 Mise à jour

Pour mettre à jour l'application :

```bash
cd /var/www/prospectscore-pro

# Sauvegarder la config
cp .env .env.backup

# Récupérer les nouvelles sources
git pull  # ou copier les nouveaux fichiers

# Reconstruire et redémarrer
docker-compose down
docker-compose build
docker-compose up -d
```

## 🐛 Dépannage

### L'application ne démarre pas

```bash
# Vérifier les logs
docker-compose logs backend
docker-compose logs frontend

# Vérifier que les ports sont disponibles
netstat -tuln | grep 8003
netstat -tuln | grep 3003
```

### Erreur de connexion à la base de données

```bash
# Vérifier que PostgreSQL fonctionne
docker ps | grep postgres

# Tester la connexion
docker exec postgres-prospectscore psql -U prospectscore -d prospectscore -c "SELECT 1;"
```

### Nginx renvoie 502 Bad Gateway

```bash
# Vérifier que les conteneurs tournent
docker-compose ps

# Vérifier les logs Nginx
sudo tail -f /var/log/nginx/error.log

# Redémarrer tout
docker-compose restart
sudo systemctl reload nginx
```

### DNS ne résout pas

```bash
# Tester la résolution DNS
nslookup score.2a-immobilier.fr
dig score.2a-immobilier.fr

# Attendre la propagation (jusqu'à 24h dans certains cas)
```

## 📞 Support

Problème de déploiement ? Vérifier :

1. Les logs : `docker-compose logs -f`
2. L'audit du VPS : `./audit-vps.sh`
3. La configuration Nginx : `sudo nginx -t`
4. Les ports utilisés : `netstat -tuln`

## 🎯 Fonctionnalités

### Système de Scoring

L'algorithme évalue les prospects sur 100 points :

- **DPE (35 pts)** : Classes F/G = priorité maximale
- **Coûts énergétiques (25 pts)** : Factures élevées = motivation
- **Type de bien (15 pts)** : Maisons favorisées
- **Surface (15 pts)** : Grandes surfaces = valeur
- **Localisation (10 pts)** : Codes postaux prisés

### Recherche DPE ADEME

Intégration directe avec la base nationale :
- Recherche par code postal
- Filtrage par classe énergétique
- Import automatique des prospects
- Calcul instantané du score

## 🔄 Intégration avec l'Écosystème 2A

ProspectScore Pro s'intègre avec :

- **DPE Pro** : Base de données commune
- **2A Social Studio** : Partage de prospects pour campagnes
- **Netty CRM** : Export vers votre CRM (à venir)

---

**Déployé avec ❤️ pour 2A Immobilier**

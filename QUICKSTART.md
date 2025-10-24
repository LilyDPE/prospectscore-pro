# 🚀 DÉMARRAGE RAPIDE - ProspectScore Pro

## Déploiement en 5 minutes

### 1️⃣ Copier sur le VPS

```bash
# Sur Mac
scp prospectscore-deploy.tar.gz root@votre-vps.com:/tmp/

# Se connecter
ssh root@votre-vps.com
```

### 2️⃣ Extraire

```bash
cd /tmp
mkdir prospectscore-deploy && cd prospectscore-deploy
tar -xzf ../prospectscore-deploy.tar.gz
chmod +x *.sh
```

### 3️⃣ Déployer

```bash
sudo ./deploy.sh
```

**Terminé !** 🎉

---

## Accès

- Frontend: http://score.2a-immobilier.fr
- API: http://score.2a-immobilier.fr/api
- Docs: http://score.2a-immobilier.fr/docs

---

## Configuration DNS (OVH)

1. Ajouter enregistrement A:
   - Nom: `score`
   - Type: `A`
   - Valeur: `IP du VPS`

2. Attendre 5-30 min

---

## HTTPS (après DNS)

```bash
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d score.2a-immobilier.fr
```

---

## Commandes Utiles

```bash
cd /var/www/prospectscore-pro

# Logs
docker-compose logs -f

# Restart
docker-compose restart

# Rebuild
docker-compose up -d --build

# Credentials
cat CREDENTIALS.txt
```

---

## 🆘 Problème ?

```bash
# Audit
./audit-vps.sh

# Vérifier conteneurs
docker-compose ps

# Vérifier Nginx
sudo nginx -t
sudo systemctl status nginx

# Logs détaillés
docker-compose logs -f backend
docker-compose logs -f frontend
```

---

## 📱 Premier Compte

1. Ouvrir http://score.2a-immobilier.fr
2. Cliquer "Inscription"
3. Créer votre compte
4. Se connecter

**C'est parti !** 🚀

---

Documentation complète: `README.md`

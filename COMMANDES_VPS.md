# 🚀 Commandes VPS - Déploiement V2

## 📋 Informations VPS

- **IP** : 146.59.228.175
- **OS** : Ubuntu (OVH)
- **User** : root ou ubuntu
- **Projet** : ProspectScore Pro

---

## 🔑 Connexion SSH

### Depuis ton Mac

```bash
# Méthode 1 : Avec user ubuntu
ssh ubuntu@146.59.228.175
# Mot de passe : Teivaki04;

# Méthode 2 : Avec user root (si configuré)
ssh root@146.59.228.175
# Mot de passe : Teivaki04;
```

**Si erreur "Host key verification failed" :**
```bash
ssh-keygen -R 146.59.228.175
ssh ubuntu@146.59.228.175
```

---

## 🚀 Déploiement Automatique (Depuis ton Mac)

### Option A : Script Automatique (Recommandé)

```bash
# 1. Aller dans le projet local (sur ton Mac)
cd ~/chemin/vers/prospectscore-pro

# 2. Lancer le déploiement automatique
./deploy_v2_to_vps.sh

# Le script va :
# ✅ Se connecter au VPS
# ✅ Mettre à jour le projet
# ✅ Vérifier les fichiers V2
# ✅ Redémarrer le backend
# ✅ Tester l'API
```

### Option B : Manuel (Étape par Étape)

**1. Se connecter au VPS**
```bash
ssh ubuntu@146.59.228.175
```

**2. Vérifier si le projet existe**
```bash
# Chercher le projet
ls /var/www/prospectscore-pro
# OU
ls /home/ubuntu/prospectscore-pro
# OU
find / -name "prospectscore-pro" -type d 2>/dev/null
```

**3. Si le projet existe : Mise à jour**
```bash
cd /var/www/prospectscore-pro  # Ou le chemin trouvé

# Mettre à jour
git fetch origin
git checkout claude/project-status-review-018mAyUAV7GK76xZ8odepa1v
git pull origin claude/project-status-review-018mAyUAV7GK76xZ8odepa1v

# Vérifier les nouveaux fichiers
ls -la backend/services/propensity_predictor_v2.py
ls -la scripts/migrate_to_v2.py
ls -la test_v2.sh
```

**4. Si le projet n'existe pas : Clonage**
```bash
cd /var/www  # Ou /home/ubuntu

# Cloner le projet
git clone https://github.com/LilyDPE/prospectscore-pro.git
cd prospectscore-pro
git checkout claude/project-status-review-018mAyUAV7GK76xZ8odepa1v
```

**5. Redémarrer le backend**
```bash
cd /var/www/prospectscore-pro  # Ou le chemin du projet

# Vérifier Docker
docker-compose ps

# Redémarrer le backend
docker-compose restart backend

# Voir les logs
docker-compose logs -f backend
```

**6. Rendre les scripts exécutables**
```bash
chmod +x test_v2.sh
chmod +x scripts/migrate_to_v2.py
```

---

## 🧪 Tester la V2

### Une fois connecté en SSH sur le VPS

**1. Test rapide avec le script**
```bash
cd /var/www/prospectscore-pro  # Ou le chemin du projet
./test_v2.sh
```

**2. Test dry-run (sans modification)**
```bash
python3 scripts/migrate_to_v2.py --dry-run --score-min 40 --batch-size 100
```

**3. Migration complète**
```bash
python3 scripts/migrate_to_v2.py --score-min 0 --batch-size 500
```

**4. Via API (depuis le VPS)**
```bash
# Test V2
curl -X POST "http://localhost:8003/api/admin/analyze-propensity-v2?score_min=40&limit=100" | python3 -m json.tool

# Voir les prospects HOT
curl "http://localhost:8003/api/admin/prospects-hot?limit=10" | python3 -m json.tool

# Stats DVF
curl "http://localhost:8003/api/admin/dvf/stats" | python3 -m json.tool
```

---

## 🔍 Vérifications

### Vérifier que le backend tourne

```bash
# Docker
docker-compose ps

# Devrait afficher :
# backend    Up    0.0.0.0:8003->8000/tcp
# db         Up    0.0.0.0:5433->5432/tcp
```

### Vérifier les logs

```bash
# Logs en temps réel
docker-compose logs -f backend

# Dernières 100 lignes
docker-compose logs backend --tail 100

# Chercher les erreurs
docker-compose logs backend | grep -i error
```

### Tester l'API

```bash
# Backend actif ?
curl http://localhost:8003/

# Stats DVF
curl http://localhost:8003/api/admin/dvf/stats

# Test V2
curl -X POST "http://localhost:8003/api/admin/analyze-propensity-v2?score_min=40&limit=10"
```

---

## 🚨 Dépannage

### Backend ne répond pas

```bash
# Redémarrer tout
docker-compose restart

# Ou redémarrer juste le backend
docker-compose restart backend

# Vérifier les conteneurs
docker-compose ps

# Voir les logs d'erreur
docker-compose logs backend | tail -50
```

### Git erreur "detached HEAD"

```bash
git checkout claude/project-status-review-018mAyUAV7GK76xZ8odepa1v
git pull origin claude/project-status-review-018mAyUAV7GK76xZ8odepa1v
```

### Permission denied

```bash
# Changer les permissions
sudo chmod +x test_v2.sh
sudo chmod +x scripts/migrate_to_v2.py

# Si problème Docker
sudo docker-compose restart backend
```

### Module propensity_predictor_v2 not found

```bash
# Vérifier que le fichier existe
ls -la backend/services/propensity_predictor_v2.py

# Si absent, pull à nouveau
git pull origin claude/project-status-review-018mAyUAV7GK76xZ8odepa1v

# Redémarrer le backend
docker-compose restart backend
```

---

## 📊 Résultats Attendus

Après la migration V2, tu devrais voir :

```bash
✅ MIGRATION TERMINÉE
Total analysé : 5234
HOT (≥75) : 782 (14.9%)  ← +60% vs V1
URGENT (≥90) : 134 (2.6%)  ← +100% vs V1
```

---

## 🎯 Commandes Rapides

```bash
# Connexion SSH
ssh ubuntu@146.59.228.175

# Aller dans le projet
cd /var/www/prospectscore-pro

# Mettre à jour V2
git pull origin claude/project-status-review-018mAyUAV7GK76xZ8odepa1v

# Redémarrer
docker-compose restart backend

# Tester
./test_v2.sh

# Migrer
python3 scripts/migrate_to_v2.py --dry-run
```

---

## 📚 Documentation

Sur le VPS, consulter :

```bash
cd /var/www/prospectscore-pro

# Guide complet
cat GUIDE_MIGRATION_V2.md

# Guide rapide
cat QUICKSTART_V2.md

# Détails techniques
cat AMELIORATIONS_PREDICTION.md
```

---

## 🚀 Let's Go !

```bash
# Depuis ton Mac
ssh ubuntu@146.59.228.175
# Mot de passe : Teivaki04;

# Puis sur le VPS
cd /var/www/prospectscore-pro
git pull origin claude/project-status-review-018mAyUAV7GK76xZ8odepa1v
docker-compose restart backend
./test_v2.sh
```

**C'est parti ! 🎯**

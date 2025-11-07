# 🚀 Guide de Déploiement Complet - ProspectScore Pro

Guide étape par étape pour déployer toutes les fonctionnalités.

---

## ✅ Étape 1 : Récupérer le code sur le VPS

```bash
# Se connecter au VPS
ssh root@votre-vps

# Aller dans le répertoire du projet
cd /var/www/prospectscore-pro

# Récupérer les dernières modifications
git fetch origin
git checkout claude/fix-nginx-api-routing-011CUuF79L1PQr7iT6qe92gN
git pull origin claude/fix-nginx-api-routing-011CUuF79L1PQr7iT6qe92gN
```

---

## ✅ Étape 2 : Déployer Nginx (Fix routing API)

```bash
sudo ./update-nginx.sh
```

**Ce que fait ce script** :
- ✅ Sauvegarde l'ancienne configuration
- ✅ Installe la nouvelle configuration Nginx
- ✅ Teste la validité
- ✅ Recharge Nginx
- ✅ Vérifie la connectivité

**Vérifier que ça marche** :
```bash
curl https://score.2a-immobilier.com/api/
```

Devrait retourner un JSON avec les endpoints.

---

## ✅ Étape 3 : Créer les tables Features ML

```bash
./scripts/setup_features_ml.sh
```

**Ce que fait ce script** :
- ✅ Crée la table `biens_univers`
- ✅ Crée les index spatiaux PostGIS
- ✅ Crée les fonctions helper
- ✅ Crée les vues statistiques

---

## ✅ Étape 4 : Créer les tables Commerciaux

```bash
./scripts/setup_commerciaux.sh
```

**Ce que fait ce script** :
- ✅ Crée la table `commerciaux`
- ✅ Crée la table `prospect_assignments`
- ✅ Crée les index
- ✅ Crée les triggers
- ✅ Crée les vues statistiques

---

## ✅ Étape 5 : Redémarrer le backend

```bash
docker-compose restart backend
```

**Vérifier les logs** :
```bash
docker logs prospectscore-backend --tail 50
```

Vous devriez voir :
```
🚀 ProspectScore Pro API démarrée
```

---

## 🔍 Étape 6 : Vérifier les données de probabilité

```bash
./scripts/check_probabilites.sh
```

**Ce que fait ce script** :
- ✅ Vérifie que la table `biens_univers` existe
- ✅ Compte les biens totaux et avec features
- ✅ Montre la distribution des scores de propension
- ✅ Affiche le TOP 10 des meilleurs prospects
- ✅ Distribution par zone géographique
- ✅ TOP 10 codes postaux avec forte probabilité
- ✅ Opportunités par département
- ✅ Vérification des assignations existantes

**Résultat attendu** :
```
📊 Statistiques générales...
 total_biens | biens_avec_features | biens_geolocalises | pourcentage_features
-------------+---------------------+--------------------+----------------------
      604622 |              302650 |             604622 |                50.04

📊 Distribution des scores de propension...
    categorie_score     | nombre_biens | pourcentage
------------------------+--------------+-------------
 🔥 TRES FORT (≥80)     |        12560 |        4.15
 ⭐ FORT (70-79)        |        25230 |        8.34
 ✅ BON (60-69)         |        48470 |       16.02
 ...
```

---

## 📧 Configuration de l'envoi d'emails (Optionnel)

Pour que les commerciaux reçoivent les prospects par email, configurez SMTP :

### **Option 1 : Gmail**

```bash
# Éditer docker-compose.yml ou créer un .env
nano docker-compose.yml
```

Ajouter dans la section `backend` → `environment` :
```yaml
- SMTP_HOST=smtp.gmail.com
- SMTP_PORT=587
- SMTP_USER=votre-email@gmail.com
- SMTP_PASSWORD=votre-mot-de-passe-application
- FROM_EMAIL=noreply@2a-immobilier.com
- FROM_NAME=ProspectScore Pro
```

**⚠️ Important Gmail** : Utilisez un "mot de passe d'application" :
1. Aller sur https://myaccount.google.com/security
2. Activer la validation en 2 étapes
3. Créer un mot de passe d'application

### **Option 2 : SMTP personnalisé**

```yaml
- SMTP_HOST=mail.votre-domaine.com
- SMTP_PORT=587
- SMTP_USER=noreply@2a-immobilier.com
- SMTP_PASSWORD=votre-mot-de-passe
- FROM_EMAIL=noreply@2a-immobilier.com
```

### **Option 3 : Service externe (SendGrid, Mailgun, etc.)**

Modifier `backend/services/email_service.py` pour utiliser leur API.

**Après configuration** :
```bash
docker-compose restart backend
```

---

## 👥 Utilisation du système

### 1. Créer un commercial

```bash
curl -X POST https://score.2a-immobilier.com/api/admin/commerciaux/ \
  -H "Content-Type: application/json" \
  -d '{
    "nom": "Dupont",
    "prenom": "Jean",
    "email": "jean.dupont@2a-immobilier.com",
    "telephone": "0601020304",
    "codes_postaux_assignes": ["76260", "76370", "76550"],
    "departements_assignes": ["76"],
    "capacite_max_prospects": 100,
    "min_propensity_score": 60
  }'
```

### 2. Assigner des prospects (avec email automatique)

```bash
curl -X POST "https://score.2a-immobilier.com/api/admin/commerciaux/1/assign-prospects?nombre_prospects=20&envoyer_email=true"
```

**Le commercial recevra un email** avec :
- ✅ Liste des 20 meilleurs prospects
- ✅ Adresse complète
- ✅ Score de propension
- ✅ Détails du bien (surface, pièces, prix, etc.)
- ✅ Priorité (HAUTE, MOYENNE, BASSE)
- ✅ Lien vers l'interface

### 3. Consulter le dashboard admin

```bash
curl https://score.2a-immobilier.com/api/admin/commerciaux/dashboard/stats
```

---

## 🧪 Tests de vérification

### Test 1 : API Nginx

```bash
curl https://score.2a-immobilier.com/api/
```

✅ **Attendu** : JSON avec version 2.0.0 et sections "commerciaux_admin"

### Test 2 : Features ML

```bash
curl https://score.2a-immobilier.com/api/features/stats
```

✅ **Attendu** : Statistiques sur les biens avec features

### Test 3 : Backend opérationnel

```bash
docker ps
```

✅ **Attendu** : Voir `prospectscore-backend`, `prospectscore-frontend`, `postgres-prospectscore`

### Test 4 : PostgreSQL

```bash
docker exec -i postgres-prospectscore psql -U prospectscore -d prospectscore -c "SELECT COUNT(*) FROM biens_univers;"
```

✅ **Attendu** : Un nombre > 0

---

## 🐛 Dépannage

### Problème : API retourne 404

**Solution** :
```bash
# Vérifier Nginx
sudo nginx -t
sudo systemctl status nginx

# Vérifier backend
docker logs prospectscore-backend --tail 50
```

### Problème : Pas de biens avec features

**Vérifier** :
```bash
./scripts/check_probabilites.sh
```

Si `biens_avec_features = 0` :
```sql
-- Importer vos données avec features
-- Ou recalculer les features ML
```

### Problème : Emails non envoyés

**Vérifier la configuration SMTP** :
```bash
docker exec prospectscore-backend env | grep SMTP
```

Si vide, ajouter dans `docker-compose.yml` et redémarrer.

### Problème : Commercial ne reçoit pas d'email

**Vérifier** :
1. Email du commercial est correct
2. Configuration SMTP est bonne
3. Logs backend : `docker logs prospectscore-backend --tail 100`

---

## 📊 Monitoring

### Vérifier l'état global

```bash
# Script de vérification complet
./scripts/check_probabilites.sh
```

### Vérifier les logs en temps réel

```bash
# Backend
docker logs -f prospectscore-backend

# Nginx
sudo tail -f /var/log/nginx/prospectscore_error.log

# PostgreSQL
docker logs -f postgres-prospectscore
```

---

## 🎯 Résumé des commandes essentielles

```bash
# Déploiement initial
git pull origin claude/fix-nginx-api-routing-011CUuF79L1PQr7iT6qe92gN
sudo ./update-nginx.sh
./scripts/setup_features_ml.sh
./scripts/setup_commerciaux.sh
docker-compose restart backend

# Vérification
./scripts/check_probabilites.sh

# Utilisation
curl -X POST .../api/admin/commerciaux/ -d '{...}'
curl -X POST .../api/admin/commerciaux/1/assign-prospects?nombre_prospects=20
```

---

## 📚 Documentation complète

- **NGINX-FIX.md** : Correction routing Nginx
- **FEATURES-ML.md** : API Features ML
- **COMMERCIAUX.md** : Système de gestion commerciaux
- **Ce fichier** : Guide de déploiement

---

**Version** : 2.0.0
**Date** : 2025-11-07
**Auteur** : Claude

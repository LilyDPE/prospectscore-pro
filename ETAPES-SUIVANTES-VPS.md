# 🚀 Étapes Suivantes sur le VPS

## ✅ Étape Actuelle

Vous avez déjà complété avec succès :
- ✅ Fix Nginx routing → API accessible sur https://score.2a-immobilier.com/api/
- ✅ Backend v2.0.0 déployé avec tous les nouveaux endpoints
- ✅ Conteneurs Docker opérationnels

---

## 📋 Étapes à Exécuter sur le VPS

Connectez-vous à votre VPS et exécutez ces commandes dans l'ordre :

### Étape 2 : Créer les tables Features ML

```bash
cd /var/www/prospectscore-pro
sudo ./scripts/setup_features_ml.sh
```

**Ce script va :**
- ✅ Créer/vérifier la table `biens_univers` avec les colonnes ML
- ✅ Ajouter les colonnes : `zone_type`, `local_turnover_12m`, `sale_density_12m`, `propensity_score`
- ✅ Créer les index spatiaux PostGIS
- ✅ Créer les fonctions helper PostgreSQL
- ✅ Créer les vues statistiques

---

### Étape 3 : Créer les tables Commerciaux

```bash
sudo ./scripts/setup_commerciaux.sh
```

**Ce script va :**
- ✅ Créer la table `commerciaux` (gestion équipe commerciale)
- ✅ Créer la table `prospect_assignments` (assignations prospects → commerciaux)
- ✅ Créer les index de performance
- ✅ Créer les triggers automatiques
- ✅ Créer les vues dashboard

---

### Étape 4 : Redémarrer le backend

```bash
cd /var/www/prospectscore-pro
docker-compose restart backend
```

**Vérifier les logs :**
```bash
docker logs prospectscore-backend --tail 50
```

Vous devriez voir : `🚀 ProspectScore Pro API démarrée`

---

### Étape 5 : Vérifier les Données (IMPORTANT)

```bash
sudo ./scripts/check_probabilites.sh
```

**Ce script va répondre à votre question :**
> "Est-ce qu'on a des biens avec des probabilismes intéressantes ?"

Il va afficher :
- 📊 Nombre total de biens avec features calculées
- 🔥 Distribution des scores de propension (TRES FORT ≥80, FORT 70-79, etc.)
- 🎯 TOP 10 des meilleurs prospects
- 📍 TOP 10 codes postaux avec forte probabilité
- 🗺️ Opportunités par département

**Résultat attendu :**
Si vous avez des biens avec `propensity_score ≥ 70`, vous êtes prêt à créer des commerciaux et assigner des prospects !

---

## 🎯 Après la Vérification

### Si vous avez des biens avec scores élevés :

**1. Créer votre premier commercial :**
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

**2. Assigner automatiquement les 20 meilleurs prospects (avec email) :**
```bash
curl -X POST "https://score.2a-immobilier.com/api/admin/commerciaux/1/assign-prospects?nombre_prospects=20&envoyer_email=true"
```

Le commercial recevra un email avec :
- ✅ Adresses complètes des 20 meilleurs prospects de sa zone
- ✅ Score de propension de chaque bien
- ✅ Détails : surface, pièces, prix, type de bien
- ✅ Priorité (HAUTE, MOYENNE, BASSE)

---

## ⚙️ Configuration SMTP (Optionnel mais recommandé)

Pour que les emails fonctionnent, configurez SMTP dans `docker-compose.yml` :

```yaml
services:
  backend:
    environment:
      # ... autres variables ...
      - SMTP_HOST=smtp.gmail.com
      - SMTP_PORT=587
      - SMTP_USER=votre-email@gmail.com
      - SMTP_PASSWORD=votre-mot-de-passe-application
      - FROM_EMAIL=noreply@2a-immobilier.com
      - FROM_NAME=ProspectScore Pro
```

Puis redémarrer :
```bash
docker-compose restart backend
```

---

## 🐛 Dépannage

### Si pas de biens avec features :
- Vérifier que vos données ont les colonnes ML : `propensity_score`, `zone_type`, etc.
- Importer vos données enrichies si nécessaire

### Si les scripts échouent :
```bash
# Vérifier PostgreSQL
docker ps | grep postgres

# Vérifier les logs
docker logs postgres-prospectscore --tail 50
```

---

**Prochaine commande à exécuter :**
```bash
ssh root@votre-vps
cd /var/www/prospectscore-pro
sudo ./scripts/setup_features_ml.sh
```

🎯 **Objectif** : Vérifier que vous avez des biens avec des probabilités intéressantes pour commencer à prospecter !

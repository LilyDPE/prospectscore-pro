# 🔧 Fix Migration : biens_univers

## 📊 Problème Détecté

Lors de l'exécution des scripts de setup, nous avons détecté que **`biens_univers` est une vue matérialisée**, pas une table normale.

**Erreurs rencontrées :**
```
ERROR: "biens_univers" is not a table
ERROR: This operation is not supported for materialized views
ERROR: column "zone_type" does not exist
ERROR: referenced relation "biens_univers" is not a table
```

**Cause :** PostgreSQL ne permet pas d'ajouter des colonnes ou de créer des foreign keys sur des vues matérialisées.

---

## ✅ Solution Automatique

J'ai créé un script de migration qui :
1. ✅ Détecte automatiquement si `biens_univers` est une vue matérialisée
2. ✅ Renomme la vue matérialisée en `biens_univers_old`
3. ✅ Crée une vraie table `biens_univers` avec toutes les colonnes ML
4. ✅ Copie toutes les données existantes
5. ✅ Ajoute les nouvelles colonnes : `zone_type`, `propensity_score`, `local_turnover_12m`, etc.
6. ✅ Crée les tables `commerciaux` et `prospect_assignments`
7. ✅ Vérifie l'intégrité des données

---

## 🚀 Commandes à Exécuter sur le VPS

### Étape 1 : Récupérer le fix

```bash
cd /var/www/prospectscore-pro
git pull origin claude/fix-nginx-api-routing-011CUuF79L1PQr7iT6qe92gN
```

### Étape 2 : Exécuter la migration automatique

```bash
sudo ./scripts/fix-migration.sh
```

**Ce script va faire tout automatiquement :**
- Migration vue matérialisée → table
- Ajout des colonnes ML
- Création des tables commerciaux
- Vérification des données

### Étape 3 : Redémarrer le backend

```bash
sudo docker-compose restart backend
```

### Étape 4 : Vérifier les données

```bash
sudo ./scripts/check_probabilites.sh
```

---

## 📊 Résultat Attendu

Après la migration, vous devriez voir :

```sql
 total_biens | geolocalises | avec_features | forte_probabilite
-------------+--------------+---------------+-------------------
      604622 |       604622 |             0 |                 0
```

**Important :** Les colonnes ML sont maintenant présentes, mais `avec_features = 0` car les features ne sont pas encore calculées.

---

## 🔍 Si vous avez déjà des features calculées

Si vos données contiennent déjà les colonnes `zone_type`, `propensity_score`, etc. (dans l'ancienne vue matérialisée), vous devrez les importer dans la nouvelle table :

```bash
docker exec -i postgres-prospectscore psql -U prospectscore -d prospectscore << 'EOF'
-- Mettre à jour les colonnes ML depuis biens_univers_old si elles existent
UPDATE biens_univers b
SET
    zone_type = o.zone_type,
    local_turnover_12m = o.local_turnover_12m,
    sale_density_12m = o.sale_density_12m,
    propensity_score = o.propensity_score,
    features_calculated = TRUE
FROM biens_univers_old o
WHERE b.id_bien = o.id_bien
  AND o.propensity_score IS NOT NULL;
EOF
```

---

## 🧪 Tests de Vérification

### Test 1 : Vérifier que biens_univers est maintenant une table

```bash
docker exec -i postgres-prospectscore psql -U prospectscore -d prospectscore -c "
SELECT
    CASE
        WHEN EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'biens_univers') THEN '✅ TABLE'
        WHEN EXISTS (SELECT 1 FROM pg_matviews WHERE matviewname = 'biens_univers') THEN '❌ MATERIALIZED VIEW'
        ELSE '❌ NON TROUVÉ'
    END as type_biens_univers;
"
```

**Attendu :** `✅ TABLE`

### Test 2 : Vérifier les colonnes ML

```bash
docker exec -i postgres-prospectscore psql -U prospectscore -d prospectscore -c "
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'biens_univers'
  AND column_name IN ('zone_type', 'propensity_score', 'local_turnover_12m', 'features_calculated')
ORDER BY column_name;
"
```

**Attendu :** 4 colonnes trouvées

### Test 3 : Tester l'API

```bash
curl https://score.2a-immobilier.com/api/features/stats
```

**Attendu :** JSON avec les statistiques

---

## 🎯 Prochaines Étapes

Une fois la migration terminée :

### 1. Calculer les features ML (si nécessaire)

Si vous avez un script de calcul des features ML, exécutez-le maintenant pour remplir les colonnes :
- `zone_type`
- `local_turnover_12m`
- `sale_density_12m`
- `propensity_score`

### 2. Créer votre premier commercial

```bash
curl -X POST https://score.2a-immobilier.com/api/admin/commerciaux/ \
  -H "Content-Type: application/json" \
  -d '{
    "nom": "Dupont",
    "prenom": "Jean",
    "email": "jean.dupont@2a-immobilier.com",
    "telephone": "0601020304",
    "codes_postaux_assignes": ["76260", "76370"],
    "min_propensity_score": 60
  }'
```

### 3. Assigner des prospects

```bash
curl -X POST "https://score.2a-immobilier.com/api/admin/commerciaux/1/assign-prospects?nombre_prospects=20&envoyer_email=true"
```

---

## 🐛 Dépannage

### Si la migration échoue

```bash
# Vérifier les logs PostgreSQL
docker logs postgres-prospectscore --tail 50

# Vérifier les conteneurs
docker ps

# Vérifier la connexion à la base
docker exec -i postgres-prospectscore psql -U prospectscore -d prospectscore -c "SELECT version();"
```

### Si docker-compose restart backend échoue

```bash
# Ajouter l'utilisateur au groupe docker
sudo usermod -aG docker ubuntu
newgrp docker

# Ou utiliser sudo
sudo docker-compose restart backend
```

---

## 📚 Fichiers Créés

- `scripts/migrate_biens_univers.sql` : Script SQL de migration
- `scripts/fix-migration.sh` : Script shell automatique
- `FIX-MIGRATION.md` : Ce guide

---

**Commande unique à copier-coller sur le VPS :**

```bash
cd /var/www/prospectscore-pro && \
git pull origin claude/fix-nginx-api-routing-011CUuF79L1PQr7iT6qe92gN && \
sudo ./scripts/fix-migration.sh && \
sudo docker-compose restart backend && \
sudo ./scripts/check_probabilites.sh
```

✅ Cette commande fait tout automatiquement !

---

**Version** : 2.0.1
**Date** : 2025-11-07
**Auteur** : Claude

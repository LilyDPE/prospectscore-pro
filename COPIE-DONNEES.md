# 📊 Guide de Copie des Données

## 🔍 Problème

La migration `biens_univers` (vue matérialisée → table) a réussi, mais **0 biens copiés** au lieu de 604,622.

**Cause :** La structure de `biens_univers_old` est différente de ce qu'on attendait.

---

## ✅ Solution en 2 Étapes

### Étape 1 : Inspecter la structure (optionnel mais recommandé)

```bash
cd /var/www/prospectscore-pro
git pull origin claude/fix-nginx-api-routing-011CUuF79L1PQr7iT6qe92gN
sudo ./scripts/inspect-structure.sh
```

**Ce que fait ce script :**
- Liste toutes les colonnes de `biens_univers_old`
- Montre des exemples de données
- Identifie les colonnes communes avec `biens_univers`

**Exemple de sortie attendue :**
```
📊 Colonnes dans biens_univers_old:
 column_name | data_type | character_maximum_length
-------------+-----------+-------------------------
 id_bien     | integer   |
 code_postal | varchar   | 5
 commune     | varchar   | 200
 latitude    | float     |
 longitude   | float     |
 geom        | geometry  |
 ...
```

---

### Étape 2 : Copier automatiquement les données

```bash
sudo ./scripts/auto-copy-data.sh
```

**Ce que fait ce script :**
- ✅ Détecte automatiquement les colonnes communes
- ✅ Génère dynamiquement la requête INSERT
- ✅ Copie tous les 604,622 biens
- ✅ Affiche les statistiques de copie

**Résultat attendu :**
```
✅ Copie réussie: 604622 / 604622 biens

📊 Statistiques détaillées:
 total_biens | geolocalises | avec_code_postal | avec_commune
-------------+--------------+------------------+--------------
      604622 |       604622 |           604622 |       604622
```

---

## 🎯 Après la Copie

Une fois les données copiées, vous aurez :
- ✅ 604,622 biens dans `biens_univers`
- ✅ Données de base : code_postal, commune, latitude, longitude, geom, etc.
- ⚠️ Colonnes ML vides : `zone_type`, `propensity_score`, `local_turnover_12m`, etc.

---

## 📈 Étape 3 : Features ML

Les colonnes ML sont maintenant présentes mais vides. Vous devez :

### Option A : Importer des features ML existantes

Si vous avez déjà calculé les features ML ailleurs (CSV, autre base, etc.) :

```sql
-- Exemple : Importer depuis un CSV
COPY biens_univers (
    id_bien,
    zone_type,
    local_turnover_12m,
    sale_density_12m,
    propensity_score
)
FROM '/path/to/features_ml.csv'
WITH (FORMAT csv, HEADER true);

-- Marquer les features comme calculées
UPDATE biens_univers
SET features_calculated = TRUE
WHERE propensity_score IS NOT NULL AND propensity_score > 0;
```

### Option B : Calculer les features ML

Si vous avez un pipeline de calcul des features ML :

```python
# Exemple Python avec votre pipeline ML
import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="prospectscore",
    user="prospectscore",
    password="..."
)

cur = conn.cursor()

# Récupérer les biens
cur.execute("SELECT id_bien, latitude, longitude FROM biens_univers")
biens = cur.fetchall()

# Calculer les features pour chaque bien
for bien in biens:
    id_bien, lat, lon = bien

    # Votre logique de calcul
    zone_type = calculate_zone_type(lat, lon)
    local_turnover = calculate_local_turnover(lat, lon)
    propensity_score = calculate_propensity_score(...)

    # Mettre à jour
    cur.execute("""
        UPDATE biens_univers
        SET zone_type = %s,
            local_turnover_12m = %s,
            propensity_score = %s,
            features_calculated = TRUE
        WHERE id_bien = %s
    """, (zone_type, local_turnover, propensity_score, id_bien))

conn.commit()
```

### Option C : Tester sans features ML

Pour tester le système sans features ML :

```bash
# Créer un commercial
curl -X POST https://score.2a-immobilier.com/api/admin/commerciaux/ \
  -H "Content-Type: application/json" \
  -d '{
    "nom": "Dupont",
    "prenom": "Jean",
    "email": "jean.dupont@2a-immobilier.com",
    "codes_postaux_assignes": ["76260"]
  }'

# Tester l'API
curl https://score.2a-immobilier.com/api/features/stats
```

---

## 🧪 Vérification Finale

Une fois les features ML importées/calculées :

```bash
sudo ./scripts/check_probabilites.sh
```

**Vous devriez voir :**
```
📊 Statistiques générales...
 total_biens | biens_avec_features | pourcentage_features
-------------+---------------------+----------------------
      604622 |              302650 |                50.04

📊 Distribution des scores de propension...
    categorie_score     | nombre_biens | pourcentage
------------------------+--------------+-------------
 🔥 TRES FORT (≥80)     |        12560 |        4.15
 ⭐ FORT (70-79)        |        25230 |        8.34
 ✅ BON (60-69)         |        48470 |       16.02
```

---

## 🚀 Commande Rapide (Tout en Une)

```bash
cd /var/www/prospectscore-pro && \
git pull origin claude/fix-nginx-api-routing-011CUuF79L1PQr7iT6qe92gN && \
sudo ./scripts/auto-copy-data.sh
```

---

## 🐛 Dépannage

### Si auto-copy-data.sh échoue

```bash
# Vérifier les logs PostgreSQL
docker logs postgres-prospectscore --tail 50

# Vérifier que biens_univers_old existe
docker exec -i postgres-prospectscore psql -U prospectscore -d prospectscore -c "\d+ biens_univers_old"
```

### Si 0 biens copiés

Cela signifie qu'il n'y a aucune colonne commune entre `biens_univers_old` et `biens_univers`.
Exécutez `inspect-structure.sh` pour voir la structure exacte.

---

**Version** : 2.0.2
**Date** : 2025-11-07
**Auteur** : Claude

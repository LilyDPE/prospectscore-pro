# Import DVF Historique (2014-2022)

## 🎯 Problème

L'API `data.gouv.fr` ne propose que les données **2023-2025** en téléchargement automatique.

Pour les années **2014-2022**, vous devez télécharger manuellement les fichiers.

## 📥 Solution : Upload Manuel

### Méthode 1 : Via Script (Semi-Automatique)

```bash
cd /home/user/prospectscore-pro
./scripts/import-historical-dvf.sh
```

Ce script :
1. Tente un téléchargement automatique (peut échouer)
2. Vous donne les instructions pour téléchargement manuel si échec

### Méthode 2 : Téléchargement + Upload Manuel (Recommandé)

#### Étape 1 : Télécharger les fichiers DVF historiques

**Source officielle :** https://cadastre.data.gouv.fr/data/etalab-dvf/

Pour chaque année (2014-2022), téléchargez le fichier **full.csv.gz** :

```bash
# Exemple pour 2014
wget https://cadastre.data.gouv.fr/data/etalab-dvf/2014/full.csv.gz

# Ou pour toutes les années d'un coup
for year in {2014..2022}; do
  wget "https://cadastre.data.gouv.fr/data/etalab-dvf/$year/full.csv.gz" -O "dvf_$year.csv.gz"
done
```

> **Note :** Ces fichiers font ~500 Mo chacun (compressés)

#### Étape 2 : Filtrer par département (optionnel)

Si vous ne voulez que certains départements (76, 80, 27, 60...), filtrez :

```bash
# Décompresser
gunzip dvf_2014.csv.gz

# Filtrer les départements 76, 80, 27, 60, 14, 50, 61
head -1 dvf_2014.csv > dvf_2014_filtered.csv
grep -E "^.*,76,|^.*,80,|^.*,27,|^.*,60,|^.*,14,|^.*,50,|^.*,61," dvf_2014.csv >> dvf_2014_filtered.csv

# Recompresser
gzip dvf_2014_filtered.csv
```

#### Étape 3 : Uploader vers votre serveur

**Option A : Via curl**

```bash
# Depuis votre Mac ou serveur local
curl -X POST http://votre-serveur:8003/api/admin/import-dvf-file \
  -F "file=@dvf_2014_filtered.csv.gz"
```

**Option B : Via interface Swagger**

1. Ouvrir : http://localhost:8003/docs
2. Aller à : `POST /api/admin/import-dvf-file`
3. Cliquer sur "Try it out"
4. Upload le fichier
5. Execute

**Option C : Script automatisé**

```bash
#!/bin/bash
# upload_all_historical.sh

for year in {2014..2022}; do
  FILE="dvf_${year}.csv.gz"

  if [ -f "$FILE" ]; then
    echo "📤 Upload $FILE..."

    RESULT=$(curl -X POST http://localhost:8003/api/admin/import-dvf-file \
      -F "file=@$FILE")

    echo "$RESULT" | jq '.'

    sleep 5  # Pause entre chaque upload
  else
    echo "⚠️ Fichier $FILE non trouvé"
  fi
done
```

## 📊 Vérification

Après chaque upload, vérifiez :

```bash
# Nombre de transactions par année
curl http://localhost:8003/api/admin/dvf/stats | jq '.par_type'

# Ou en SQL direct
docker compose exec -T db psql -U prospectscore -d prospectscore -c "
SELECT
    EXTRACT(YEAR FROM date_mutation) as annee,
    COUNT(*) as nb_transactions
FROM transactions_dvf
GROUP BY annee
ORDER BY annee;
"
```

## 🎯 Après l'Import Historique

Une fois que vous avez 2014-2024, lancez :

```bash
# 1. Analyser toutes les transactions (propensity scoring)
curl -X POST http://localhost:8003/api/admin/analyze-propensity \
  -d '{"score_min": 0, "limit": 500000}'

# 2. Détecter les reventes (Ground Truth)
curl -X POST http://localhost:8003/api/admin/reconcile-dvf \
  -d '{"lookback_months": 120}'  # 10 ans de recul

# 3. Vérifier les données ML disponibles
curl http://localhost:8003/api/admin/ml-training-stats

# 4. Premier entraînement ML (si >= 50 échantillons)
curl -X POST http://localhost:8003/api/admin/train-ml-model \
  -d '{"model_type": "random_forest"}'
```

## 📈 Estimation de Temps

| Étape | Temps estimé |
|-------|--------------|
| Téléchargement 9 ans (full) | 30-60 min |
| Filtrage par département (optionnel) | 10-20 min |
| Upload vers API (9 fichiers) | 20-40 min |
| Analyse propensity (500k trans.) | 30-60 min |
| DVF Matching | 5-10 min |
| Premier entraînement ML | 2-5 min |
| **TOTAL** | **~2-3 heures** |

## 🚨 Problèmes Courants

### "File too large" lors de l'upload

Solution : Augmenter la limite FastAPI

```python
# backend/main.py
app = FastAPI(
    title="ProspectScore Pro API",
    max_upload_size=1000 * 1024 * 1024  # 1 GB
)
```

### "Memory error" lors du parsing CSV

Solution : Upload fichier par fichier + redémarrer entre chaque

```bash
for file in dvf_*.csv.gz; do
  curl -X POST http://localhost:8003/api/admin/import-dvf-file -F "file=@$file"
  sleep 10
  docker compose restart backend
  sleep 30
done
```

### Les anciennes URLs ne fonctionnent pas

Les URLs changent selon l'année. Référez-vous à la page officielle :
https://cadastre.data.gouv.fr/data/etalab-dvf/

## ✅ Résumé

1. ✅ Nouveau endpoint créé : `POST /api/admin/import-dvf-file`
2. ✅ Téléchargez manuellement depuis cadastre.data.gouv.fr
3. ✅ Uploadez via curl ou Swagger
4. ✅ Lancez l'analyse + matching + training

**Pour vos 7 départements x 9 ans = ~300-400k transactions historiques**

Cela devrait vous donner **1000-2000 reventes détectées** pour entraîner le ML !

# 📥 Import DVF Historique 2014-2018

Guide pour importer les fichiers DVF historiques au format texte (séparateur `|`).

## 📋 Prérequis

✅ Fichiers `valeursfoncières-YYYY.txt` (2014-2018)
✅ Accès PostgreSQL (local ou prod)
✅ Python 3.8+ **OU** Bash avec psql

---

## 🚀 Méthode 1 : Script Bash (RAPIDE - Recommandé)

**Le plus rapide** : utilise PostgreSQL COPY, ~10x plus rapide que Python.

### 1️⃣ Rendre le script exécutable

```bash
chmod +x scripts/import_dvf_historique_local.sh
```

### 2️⃣ Configurer la connexion

Éditer le script et ajuster ces lignes si besoin :

```bash
DB_HOST="localhost"      # ou IP du serveur prod
DB_PORT="5433"           # 5432 sur prod
DB_NAME="prospectscore"
DB_USER="prospectscore"
export PGPASSWORD="2aimmobilier2025"
```

### 3️⃣ Filtrer les départements (optionnel)

Pour les 6 départements (défaut) :
```bash
DEPARTEMENTS="76|27|80|60|14|62"
```

Pour juste 76 et 80 (plus rapide) :
```bash
DEPARTEMENTS="76|80"
```

### 4️⃣ Lancer l'import

**Sur Mac (depuis ton DD externe) :**
```bash
./scripts/import_dvf_historique_local.sh /Volumes/MonDisque/Recup
```

**Sur le serveur prod :**
```bash
# 1. Copier les fichiers sur le serveur
scp /Volumes/MonDisque/Recup/valeursfoncières-*.txt user@serveur:/tmp/dvf/

# 2. Lancer l'import
ssh user@serveur
cd /var/www/prospectscore-pro
./scripts/import_dvf_historique_local.sh /tmp/dvf
```

---

## 🐍 Méthode 2 : Script Python (Plus flexible)

### 1️⃣ Installer les dépendances

```bash
pip install psycopg2-binary
```

### 2️⃣ Configurer la connexion

Éditer `scripts/import_dvf_historique_local.py` :

```python
DB_CONFIG = {
    'host': 'localhost',  # ou IP du serveur
    'port': 5433,         # 5432 sur prod
    'database': 'prospectscore',
    'user': 'prospectscore',
    'password': '2aimmobilier2025'
}
```

### 3️⃣ Filtrer les départements (optionnel)

```python
# Pour les 6 départements :
DEPARTEMENTS_CIBLES = ['76', '27', '80', '60', '14', '62']

# Pour juste 76 et 80 :
DEPARTEMENTS_CIBLES = ['76', '80']
```

### 4️⃣ Lancer l'import

```bash
python scripts/import_dvf_historique_local.py /Volumes/MonDisque/Recup
```

---

## ⚡ Performances Estimées

| Méthode | Vitesse | Temps 2014-2018 (6 depts) |
|---------|---------|---------------------------|
| **Script Bash (COPY)** | ~50,000 trans/s | **~15-20 minutes** |
| Script Python | ~5,000 trans/s | ~2-3 heures |

**💡 Recommandation : utilise le script Bash pour de meilleures performances.**

---

## 📊 Après l'Import

### 1️⃣ Vérifier les données importées

```bash
psql -U prospectscore -d prospectscore -c "
SELECT
    EXTRACT(YEAR FROM date_mutation) as annee,
    COUNT(*) as transactions,
    COUNT(DISTINCT commune) as communes,
    ROUND(AVG(valeur_fonciere)) as prix_moyen
FROM transactions_dvf
GROUP BY annee
ORDER BY annee DESC;
"
```

### 2️⃣ Calculer les scores de propension

```bash
python scripts/calculate_propensity_scores.py
```

Ou via l'API :
```bash
curl -X POST "https://score.2a-immobilier.com/api/admin/calculate-scores"
```

---

## 🛠️ Dépannage

### ❌ Erreur de connexion PostgreSQL

**Symptôme :** `Connection refused` ou `FATAL: password authentication failed`

**Solutions :**
1. Vérifier que PostgreSQL est démarré : `docker ps | grep postgres`
2. Vérifier le port : `5433` en local, `5432` en prod
3. Vérifier le mot de passe dans le script

### ❌ Encodage des caractères

**Symptôme :** Caractères bizarres (é → Ã©)

**Solution :** Les fichiers DVF sont en `LATIN1` (ISO-8859-1), c'est déjà géré dans les scripts.

### ❌ Doublons détectés

**C'est normal !** Le système utilise `ON CONFLICT DO NOTHING` sur `id_mutation`, donc les doublons sont automatiquement ignorés.

### ❌ Manque de mémoire

**Si l'import plante :**
1. Importer année par année :
   ```bash
   ./scripts/import_dvf_historique_local.sh /chemin/vers/2014/
   ./scripts/import_dvf_historique_local.sh /chemin/vers/2015/
   # etc.
   ```

2. Réduire le batch_size dans le script Python (ligne 100)

---

## 📁 Structure des Fichiers DVF

Format attendu : **CSV avec séparateur `|`**

```
Code service CH|Reference document|...|Date mutation|...|Valeur fonciere|...|Commune|Code departement|Type local|Surface reelle bati|Nombre pieces principales|...
...
```

**Colonnes importantes :**
- `Reference document` → `id_mutation` (clé unique)
- `Date mutation` → format `DD/MM/YYYY`
- `Code departement` → pour filtrage
- `Type local` → filtré sur "Maison" et "Appartement"
- `Valeur fonciere` → doit être > 0

---

## ✅ Checklist Complète

- [ ] Fichiers DVF 2014-2018 téléchargés
- [ ] PostgreSQL accessible
- [ ] Script configuré (DB_HOST, DB_PORT, etc.)
- [ ] Départements filtrés selon besoin
- [ ] Espace disque suffisant (~2 Go pour 6 depts)
- [ ] Import lancé
- [ ] Vérification des statistiques
- [ ] Calcul des scores de propension
- [ ] Tests des requêtes API

---

## 📞 Support

En cas de problème, vérifier :
1. Les logs d'erreur du script
2. Les logs PostgreSQL : `docker logs postgres-prospectscore`
3. La connexion réseau (si serveur distant)

**Bon import ! 🚀**

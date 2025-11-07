# 🗺️ Traduction des Codes INSEE en Noms de Communes

## 🔍 Problème Identifié

Lors de la copie des données, **321,860 biens ont été exclus** car le champ `commune` contient des codes INSEE au lieu de noms de communes.

**Exemple de données problématiques :**
```
commune: ['76481']  ← Code INSEE de Rouen
commune: ['14118']  ← Code INSEE de Caen
```

**Impact :** Seulement 282,758 biens copiés au lieu de 604,622 (47% des données perdues)

---

## ✅ Solution : Traduction Automatique

J'ai créé un processus en 3 étapes pour traduire tous les codes INSEE en vrais noms de communes.

### 📊 Processus de Traduction

**Étape 1 : Traduction Locale**
- Crée une table de référence `ref_communes`
- Extrait les codes INSEE des valeurs comme `['76481']`
- Croise avec les biens qui ont un vrai nom de commune
- Traduit automatiquement les codes INSEE connus

**Étape 2 : API Officielle**
- Utilise l'API geo.api.gouv.fr (gouvernement français)
- Récupère les noms officiels des communes restantes
- Complète la table de référence

**Étape 3 : Copie Finale**
- Recopie tous les biens avec les noms traduits
- Récupère les 321,860 biens perdus
- Total attendu : ~604,000 biens

---

## 🚀 Commande à Exécuter

**Une seule commande fait tout automatiquement :**

```bash
cd /var/www/prospectscore-pro && \
git pull origin claude/fix-nginx-api-routing-011CUuF79L1PQr7iT6qe92gN && \
sudo ./scripts/copy-complete.sh
```

**Ce que fait cette commande :**
1. Récupère les nouveaux scripts depuis GitHub
2. Copie les données avec traduction INSEE locale
3. Récupère les noms manquants via l'API officielle
4. Recopie avec tous les noms traduits
5. Affiche les statistiques finales

---

## 📊 Résultat Attendu

**Avant (avec exclusion des codes INSEE) :**
```
✅ Copie réussie: 282758 biens
⚠️  321,864 biens exclus (codes INSEE)
```

**Après (avec traduction INSEE) :**
```
✅ Copie réussie: ~604,000 biens
✅ Codes INSEE traduits en noms de communes
✅ Récupération de 321,000+ biens
```

**Exemples de traduction :**
- `['76481']` → `Rouen`
- `['14118']` → `Caen`
- `['76351']` → `Le Havre`
- `['80021']` → `Amiens`

---

## 🔧 Détails Techniques

### Table de Référence

```sql
CREATE TABLE ref_communes (
    code_insee VARCHAR(5) PRIMARY KEY,
    nom_commune VARCHAR(200),
    code_postal VARCHAR(5),
    departement VARCHAR(3)
);
```

### API Utilisée

**geo.api.gouv.fr** - API officielle du gouvernement français

```bash
# Exemple d'appel
curl https://geo.api.gouv.fr/communes/76481

# Réponse
{
  "nom": "Rouen",
  "code": "76481",
  "codesPostaux": ["76000", "76100"],
  "codeDepartement": "76"
}
```

### Requête de Copie avec Traduction

```sql
INSERT INTO biens_univers (commune, ...)
SELECT
    CASE
        -- Si commune commence par '[', c'est un code INSEE
        WHEN o.commune LIKE '[%' THEN
            COALESCE(
                r.nom_commune,  -- Nom trouvé dans la table de référence
                'Commune ' || TRIM(BOTH '[]''' FROM o.commune)  -- Fallback
            )
        ELSE o.commune
    END,
    ...
FROM biens_univers_old o
LEFT JOIN ref_communes r ON (
    TRIM(BOTH '[]''' FROM o.commune) = r.code_insee
);
```

---

## 📈 Statistiques Attendues

Après exécution complète :

```
📊 Statistiques détaillées:
 total_biens | codes_insee_non_traduits | pct_noms_valides | geolocalises
-------------+--------------------------+------------------+--------------
      604000 |                      100 |             99.9 |       500000

📊 Top 10 communes:
    commune     | code_postal | nb_biens
----------------+-------------+----------
 Rouen          | 76000       |    15250
 Le Havre       | 76600       |    14820
 Caen           | 14000       |    13540
 Amiens         | 80000       |    10230
 ...
```

---

## 🐛 Dépannage

### Si Python3 n'est pas installé

```bash
# Installer Python3 et pip
sudo apt-get update
sudo apt-get install python3 python3-pip

# Installer les dépendances
pip3 install requests psycopg2-binary
```

### Si l'API est lente

L'API geo.api.gouv.fr peut prendre du temps pour traiter beaucoup de codes INSEE.
Le script inclut une pause de 0.1s entre chaque requête pour ne pas surcharger l'API.

**Temps estimé :** ~30-60 minutes pour traiter tous les codes INSEE manquants

### Exécuter manuellement chaque étape

```bash
# Étape 1 : Copie avec traduction locale
sudo ./scripts/copy-with-insee.sh

# Étape 2 : Récupération via API (optionnel)
python3 scripts/fetch_communes_api.py

# Étape 3 : Recopie finale
sudo ./scripts/copy-with-insee.sh
```

---

## 💡 Prochaines Étapes

Une fois la copie terminée :

1. **Redémarrer le backend**
   ```bash
   sudo docker-compose restart backend
   ```

2. **Calculer les features ML**
   - zone_type (RURAL_ISOLE, RURAL, PERIURBAIN, URBAIN)
   - local_turnover_12m
   - propensity_score

3. **Vérifier les données**
   ```bash
   sudo ./scripts/check_probabilites.sh
   ```

4. **Tester l'API**
   ```bash
   curl https://score.2a-immobilier.com/api/features/stats
   ```

---

**Version** : 2.0.3
**Date** : 2025-11-07
**Auteur** : Claude
**Merci à l'utilisateur** pour avoir identifié que `['76481']` est un code INSEE !

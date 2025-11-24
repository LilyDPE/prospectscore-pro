# 🚀 QuickStart - PropensityPredictorV2

## Démarrage Rapide (5 minutes)

### 1. Démarrer l'Application

#### Option A : Docker (Recommandé)

```bash
# Démarrer tous les services
docker-compose up -d

# Vérifier que tout tourne
docker-compose ps

# Voir les logs
docker-compose logs -f backend
```

#### Option B : Local (Développement)

**Backend :**
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8003
```

**Frontend :**
```bash
cd frontend
npm install
npm start
```

---

### 2. Tester la Version 2

#### Option 1 : Script de Test Automatique 🎯

```bash
./test_v2.sh
```

Ce script va :
- ✅ Vérifier que le backend est accessible
- 📊 Afficher les stats DVF actuelles
- 🔄 Tester la V1 (pour comparaison)
- 🚀 Tester la V2 (nouvelle version)
- 📊 Comparer les résultats V1 vs V2
- 🔥 Afficher les top 5 prospects HOT

**Sortie attendue :**
```
======================================================================
🚀 TEST PROPENSITY PREDICTOR V2
======================================================================

📋 Configuration :
  • API URL: http://localhost:8003
  • Score minimum: 40
  • Limite: 100 transactions

🔍 1. Vérification du backend...
✅ Backend accessible

📊 2. Statistiques DVF actuelles...
{
  "total_transactions": 5234,
  "par_departement": {"76": 3421, "80": 1813},
  "prix_moyen": 245000.50,
  "score_moyen": 52.3
}

🔄 3. Test VERSION 1 (référence)...
✅ V1 terminé :
  • Analysés: 100
  • HOT (≥75): 12
  • URGENT (≥90): 2

🚀 4. Test VERSION 2 (améliorée)...
✅ V2 terminé :
  • Analysés: 100
  • HOT (≥75): 19
  • URGENT (≥90): 4

🔍 Améliorations détectées :
  • Détection reventes corrigée
  • Durée détention calculée dynamiquement
  • Liquidité marché ajoutée
  • Rentabilité locative ajoutée
  • Détection succession ajoutée
  • Saisonnalité ajoutée

📊 5. Comparaison V1 vs V2
======================================================================
Métrique              | V1              | V2              | Différence
----------------------------------------------------------------------
HOT (≥75)            | 12              | 19              | +7
URGENT (≥90)         | 2               | 4               | +2
======================================================================

🎯 Amélioration HOT : +58.3%

🔥 6. Top 5 Prospects HOT
1. 12 Rue de la Plage - Criel-sur-Mer
   Score: 89/100 | Priority: HIGH
   Timeframe: Vente probable sous 6 mois

...

✅ TEST TERMINÉ
```

#### Option 2 : API Manuelle

**Test V2 sur 100 prospects :**
```bash
curl -X POST "http://localhost:8003/api/admin/analyze-propensity-v2?score_min=40&limit=100" | python3 -m json.tool
```

**Récupérer les prospects HOT :**
```bash
curl "http://localhost:8003/api/admin/prospects-hot?limit=10" | python3 -m json.tool
```

**Dashboard complet :**
```bash
curl "http://localhost:8003/api/admin/prospects-summary" | python3 -m json.tool
```

---

### 3. Migration Complète des Données

#### Test sans modification (DRY-RUN)

```bash
python scripts/migrate_to_v2.py --dry-run --score-min 40 --batch-size 100
```

**Affiche :**
- Analyse comparative V1 vs V2 sur 20 transactions
- Exemples de changements de scores
- Impact sur la classification (MEDIUM → HIGH, etc.)
- **Aucune modification en base**

#### Migration Production

```bash
python scripts/migrate_to_v2.py --score-min 0 --batch-size 500
```

Demande confirmation avant de modifier la base.

**Options :**
- `--score-min 0` : Analyser toutes les transactions (0 = pas de filtre)
- `--batch-size 500` : Traiter par lots de 500
- `--dry-run` : Test sans modification

---

## 🎯 Résultats Attendus

### Exemple Réel

**Transaction : Maison 150m² DPE G, détention 9 ans, SCI**

| Version | Score | Priorité | Signaux | Timeframe |
|---------|-------|----------|---------|-----------|
| **V1** | 58 | MEDIUM | 4 | 12 mois |
| **V2** | 87 | HIGH | 8 | 6 mois 🎯 |

**Nouveaux signaux V2 :**
- 💧 Marché en accélération +18% (liquidité forte)
- 💰 Rendement 2.8% (très faible → arbitrage probable)
- 👴 Détention 9 ans (succession envisageable)
- 📈 Valeur 280k€ (optimisation fiscale)
- 📅 Saison haute (printemps)

---

## 📊 Interpréter les Résultats

### Scores de Propension

- **90-100 (URGENT)** 🔥 : Vente IMMINENTE (<3 mois)
  - Action : Contacter AUJOURD'HUI
  - Timing : Fenêtre critique

- **75-89 (HIGH)** 🎯 : Vente probable sous 6 mois
  - Action : Contacter cette semaine
  - Timing : Optimal pour prospection

- **60-74 (MEDIUM)** ⚡ : Vente probable sous 12 mois
  - Action : Suivre de près
  - Timing : Préparer contact dans 1-3 mois

- **40-59 (LOW)** 📋 : Potentiel à surveiller (12-24 mois)
  - Action : Base de données
  - Timing : Recontacter dans 6 mois

### Signaux Prédictifs

**Critiques (forte probabilité) :**
- 🔥 DPE F/G + interdiction location imminente
- 💰 Rendement locatif < 3% (investisseurs)
- 👴 Détention > 25 ans (succession)
- 📊 40%+ de la cohorte vend actuellement

**Moyens (probabilité modérée) :**
- ⏰ Détention 7-12 ans (sweet spot)
- 💧 Marché en accélération
- 📈 Pic de prix atteint
- 🏢 Propriétaire professionnel (SCI)

**Bonus (timing optimal) :**
- 📅 Saison printemps
- 🔄 Historique de reventes régulières
- 🎯 Contraintes multiples convergentes

---

## 🔧 Dépannage

### Backend ne démarre pas

```bash
# Vérifier les logs
docker-compose logs backend

# Ou en local
cd backend
python main.py
```

### Erreur "Module propensity_predictor_v2 not found"

```bash
# Vérifier que le fichier existe
ls backend/services/propensity_predictor_v2.py

# Réinstaller les dépendances
cd backend
pip install -r requirements.txt
```

### Base de données vide

```bash
# Importer des données DVF
curl -X POST "http://localhost:8003/api/admin/import-dvf" \
  -H "Content-Type: application/json" \
  -d '{"departements": ["76", "80"], "years": [2024, 2023]}'

# Vérifier
curl "http://localhost:8003/api/admin/dvf/stats"
```

### Pas de prospects HOT

C'est normal si :
- Données DVF viennent d'être importées (pas encore analysées)
- Score minimum trop élevé

**Solution :**
```bash
# Analyser avec score minimum à 0
curl -X POST "http://localhost:8003/api/admin/analyze-propensity-v2?score_min=0&limit=1000"
```

---

## 📚 Documentation Complète

- **`AMELIORATIONS_PREDICTION.md`** : Analyse technique détaillée des 6 améliorations
- **`GUIDE_MIGRATION_V2.md`** : Guide complet de migration avec exemples
- **`backend/services/propensity_predictor_v2.py`** : Code source commenté (680 lignes)

---

## 🚀 Commandes Essentielles

```bash
# Tester la V2 rapidement
./test_v2.sh

# Migration complète
python scripts/migrate_to_v2.py --dry-run

# API V2
curl -X POST "http://localhost:8003/api/admin/analyze-propensity-v2?score_min=40&limit=100"

# Prospects HOT
curl "http://localhost:8003/api/admin/prospects-hot?limit=20"

# Dashboard
curl "http://localhost:8003/api/admin/prospects-summary"

# Stats DVF
curl "http://localhost:8003/api/admin/dvf/stats"
```

---

## 🎉 C'est Parti !

```bash
# 1. Démarrer
docker-compose up -d

# 2. Tester
./test_v2.sh

# 3. Migrer
python scripts/migrate_to_v2.py --dry-run

# 4. Valider
./test_v2.sh
```

**Bon scoring ! 🎯**

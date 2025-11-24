# Guide d'Auto-Apprentissage ProspectScore Pro

## 🎯 Concept : La Vérité Terrain (Ground Truth)

Le système utilise **deux sources de validation** pour améliorer continuellement ses prédictions :

1. **DVF API** (Demande de Valeurs Foncières) - La **Vérité Absolue**
   - Données officielles de l'État français
   - Délai : ~6 mois après la vente
   - 100% fiable mais retardé

2. **Feedback Agents** - Le **Signal Rapide**
   - Retours des agents terrain en temps réel
   - Feedback immédiat (J+1)
   - Peut contenir des erreurs humaines

### Stratégie Hybride

Les deux sources sont combinées pour obtenir le meilleur des deux mondes :
- Apprentissage rapide avec les feedbacks agents
- Validation et correction à long terme avec DVF

## 🔄 Pipeline d'Auto-Apprentissage

```
┌─────────────────────────────────────────────────────────────────┐
│                    IMPORT DVF MENSUEL                            │
│               (scripts/import-dvf-monthly.sh)                    │
│                                                                   │
│  1. Import nouvelles transactions DVF                            │
│  2. Rapprochement DVF (Ground Truth Detection)                   │
│  3. Vérification données disponibles                             │
│  4. Ré-entraînement ML si >= 50 échantillons                     │
└─────────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  FEEDBACK AGENTS (Temps Réel)                    │
│                  POST /api/admin/feedback                        │
│                                                                   │
│  Agent marque prospect comme:                                    │
│  - Vendu (statut_final = 1)                                      │
│  - Pas vendu / Refus (statut_final = 0)                          │
│  - En négociation (statut_final = 2)                             │
└─────────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              DATASET D'ENTRAÎNEMENT VALIDÉ                       │
│                                                                   │
│  Échantillons avec statut_final connu:                           │
│  - Source DVF : Vérité absolue (6 mois délai)                    │
│  - Source Agent : Signal rapide mais peut être corrigé par DVF   │
└─────────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  RÉ-ENTRAÎNEMENT ML AUTO                         │
│                POST /api/admin/train-ml-model                    │
│                                                                   │
│  RandomForest / GradientBoosting / XGBoost                       │
│  Minimum 50 échantillons validés                                 │
│  Sauvegarde modèle versionnée + latest                           │
└─────────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              NOUVELLES PRÉDICTIONS AMÉLIORÉES                    │
│                                                                   │
│  Le modèle ML remplace progressivement le système de règles      │
│  Précision qui s'améliore au fil du temps                        │
└─────────────────────────────────────────────────────────────────┘
```

## 🛠️ Installation

### 1. Dépendances ML

```bash
cd backend
pip install -r requirements-ml.txt
```

### 2. Migration Base de Données

```bash
# Depuis le serveur
docker-compose exec -T db psql -U prospectscore -d prospectscore < backend/migrations/add_ml_columns.sql
```

### 3. Créer le dossier models

```bash
mkdir -p backend/models
chmod 777 backend/models  # Pour que Docker puisse écrire
```

### 4. Configurer le Cron

Ajouter dans crontab pour import mensuel automatique :

```bash
# Ouvrir crontab
crontab -e

# Ajouter cette ligne (import le 1er de chaque mois à 3h du matin)
0 3 1 * * /home/user/prospectscore-pro/scripts/import-dvf-monthly.sh
```

## 📊 API Endpoints

### Feedback Agent (Temps Réel)

```bash
# Marquer un prospect comme vendu
curl -X POST http://localhost:8003/api/admin/feedback \
  -H 'Content-Type: application/json' \
  -d '{
    "prospect_id": 123,
    "statut_final": 1,
    "feedback_agent": "Vendu 285k€ - Bon contact",
    "prix_vente_reel": 285000,
    "contacted": true
  }'
```

### Rapprochement DVF (Ground Truth)

```bash
# Lance la détection automatique des ventes dans DVF
curl -X POST http://localhost:8003/api/admin/reconcile-dvf \
  -H 'Content-Type: application/json'
```

### Entraînement ML

```bash
# Entraîne un nouveau modèle avec les données validées
curl -X POST http://localhost:8003/api/admin/train-ml-model \
  -H 'Content-Type: application/json' \
  -d '{"model_type": "random_forest"}'

# Autres modèles disponibles:
# - "gradient_boosting"
# - "xgboost" (si installé)
```

### Statistiques Training

```bash
# Voir combien de données validées sont disponibles
curl http://localhost:8003/api/admin/ml-training-stats
```

## 📈 Métriques de Performance

### Consulter l'accuracy actuelle

```sql
-- Dans psql
SELECT * FROM calculate_model_accuracy();
```

### Vue des performances par source

```sql
SELECT * FROM ml_performance_metrics;
```

## 🎛️ Paramètres de Configuration

### dvf_matcher.py

```python
# Matching DVF
min_similarity = 0.7  # Seuil de similarité d'adresse (0-1)
lookback_months = 18  # Période de recherche en arrière
```

### ml_trainer.py

```python
# Entraînement
min_samples = 50  # Minimum d'échantillons pour entraîner
test_size = 0.2   # 20% des données pour validation
```

## 🔍 Monitoring et Debug

### Logs

```bash
# Logs import DVF mensuel
tail -f /var/log/prospectscore/import-*.log

# Logs backend
docker-compose logs -f backend
```

### Test manuel du matching

```bash
docker-compose exec backend python services/dvf_matcher.py
```

### Test manuel du training

```bash
docker-compose exec backend python services/ml_trainer.py
```

## ⚠️ Points d'Attention

### Délai DVF (6 mois)

Le système peut temporairement croire qu'une prédiction est fausse alors que la vente n'est juste pas encore dans DVF. C'est pourquoi on attend **18 mois** avant de marquer un prospect HOT comme "faux positif".

### Balance des Classes

Si trop de "pas vendu" vs "vendu" :
- Utiliser `class_weight='balanced'` dans RandomForest (déjà configuré)
- Ou ajuster le seuil de prédiction

### Qualité du Feedback Agent

Former les agents à donner un feedback précis et objectif. DVF corrigera les erreurs mais avec 6 mois de délai.

## 🚀 Évolution Future

1. **Prédiction du prix de vente** avec régression
2. **Clustering** pour identifier des segments de prospects
3. **Time Series** pour prédire le meilleur moment de contact
4. **NLP** sur les raisons de refus des agents

## 📞 Support

En cas de problème :
1. Vérifier les logs `/var/log/prospectscore/`
2. Consulter les métriques : `GET /api/admin/ml-training-stats`
3. Vérifier que scikit-learn est installé
4. S'assurer que le dossier `backend/models/` existe et est accessible en écriture

---

**Version:** 1.0.0
**Date:** 2025-11-24
**Contact:** ProspectScore Pro Team

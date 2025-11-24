# 🎯 Amélioration de la Prédiction de Vente - ProspectScore Pro

## Diagnostic du Système Actuel

### ✅ Points Forts
1. **Fenêtre temporelle cohorte** (7-12 ans) - approche solide
2. **Contraintes convergentes** (DPE F/G, taxe, surface atypique) - très pertinent
3. **Architecture propre** - code maintenable

### ❌ Problèmes Majeurs

#### 1. Bug Critique : Détection Reventes Cassée
**Fichier** : `backend/services/propensity_predictor.py:149`

**Problème** :
```python
# Cette requête compte les ventes récentes, PAS les reventes !
jumeaux_revendus = self.db.query(func.count(func.distinct(TransactionDVF.adresse))).filter(
    TransactionDVF.commune == transaction.commune,
    TransactionDVF.type_local == transaction.type_local,
    TransactionDVF.date_mutation >= datetime.now() - timedelta(days=365)
).scalar()
```

**Impact** : Le signal "effet cohorte" (40 points max) ne fonctionne pas correctement.

**Solution** : Détecter les vraies reventes en croisant avec les ventes antérieures.

#### 2. Durée de Détention Non Calculée
**Problème** : `duree_detention_estimee` est vide dans la BDD, or c'est LA base du scoring.

**Solution** : Calculer automatiquement en détectant les reventes dans DVF.

#### 3. Analyse de Marché Limitée
**Problème** : Compare juste 6 derniers mois vs 6 précédents.

**Manque** :
- Volume de transactions (liquidité)
- Délai moyen de vente (tension du marché)
- Ratio offre/demande
- Saisonnalité (printemps vs hiver)

#### 4. Signaux Prédictifs Manquants

**Rentabilité Locative** (investisseurs) :
- Loyer estimé vs valeur du bien
- Si rendement < 3% → Signal de vente fort
- Calcul : `(loyer_annuel / valeur_bien) * 100`

**Succession/Transmission** :
- Détention > 25 ans → Succession probable
- Nom composé → Indivision
- Adresse différente commune → Résidence secondaire

**Saisonnalité** :
- Mars-Juin : +35% de ventes (printemps)
- Juillet-Août : -20% (vacances)
- Décembre : -15% (fêtes)

**Travaux Récents** :
- Si DPE s'améliore → Mise en vente probable
- Coût travaux > 15% valeur → Arbitrage

**Taux d'Intérêt** (macro) :
- Hausse taux → Baisse demande → Baisse prix
- Signal pour vendeurs motivés

---

## 🚀 Améliorations Proposées

### 1️⃣ CRITIQUE - Corriger Détection Reventes (Impact ⭐⭐⭐⭐⭐)

```python
def detect_real_resales(self, transaction: TransactionDVF) -> Tuple[int, List[Dict]]:
    """
    Détecte les VRAIES reventes : même adresse vendue plusieurs fois
    Retourne: (nombre_reventes, liste_historique)
    """
    if not transaction.adresse:
        return 0, []

    # Rechercher toutes les ventes de cette adresse
    ventes_historique = self.db.query(TransactionDVF).filter(
        TransactionDVF.adresse == transaction.adresse,
        TransactionDVF.type_local == transaction.type_local
    ).order_by(TransactionDVF.date_mutation).all()

    if len(ventes_historique) <= 1:
        return 0, []

    # Calculer fréquence de revente
    historique = []
    for i in range(1, len(ventes_historique)):
        vente_prev = ventes_historique[i-1]
        vente_curr = ventes_historique[i]

        duree_detention = (vente_curr.date_mutation - vente_prev.date_mutation).days // 365
        plus_value = vente_curr.valeur_fonciere - vente_prev.valeur_fonciere
        taux_plus_value = (plus_value / vente_prev.valeur_fonciere * 100) if vente_prev.valeur_fonciere else 0

        historique.append({
            'date_achat': vente_prev.date_mutation,
            'date_vente': vente_curr.date_mutation,
            'duree_detention': duree_detention,
            'prix_achat': vente_prev.valeur_fonciere,
            'prix_vente': vente_curr.valeur_fonciere,
            'plus_value': plus_value,
            'taux_plus_value': taux_plus_value
        })

    return len(historique), historique
```

**Score** :
- 1 revente (2 ventes) : +10 pts
- 2 reventes (3 ventes) : +20 pts (investisseur actif)
- 3+ reventes : +30 pts (marchand de biens)

**Fréquence rapide** (< 5 ans) : +20 pts supplémentaires

---

### 2️⃣ Calculer Durée de Détention Dynamiquement (Impact ⭐⭐⭐⭐⭐)

```python
def calculate_holding_duration(self, transaction: TransactionDVF) -> int:
    """
    Calcule la durée de détention réelle depuis le dernier achat
    """
    if not transaction.adresse:
        return None

    # Trouver la vente précédente de cette adresse
    vente_precedente = self.db.query(TransactionDVF).filter(
        TransactionDVF.adresse == transaction.adresse,
        TransactionDVF.type_local == transaction.type_local,
        TransactionDVF.date_mutation < transaction.date_mutation
    ).order_by(TransactionDVF.date_mutation.desc()).first()

    if not vente_precedente:
        # Si aucune vente antérieure, estimer depuis 2014 (début DVF)
        annees_depuis_debut_dvf = (transaction.date_mutation.year - 2014)
        return min(annees_depuis_debut_dvf, 10)  # Cap à 10 ans

    # Calculer durée exacte
    duree = (transaction.date_mutation - vente_precedente.date_mutation).days // 365
    return duree
```

**Impact** : Le scoring cohorte (45 pts max) devient fiable !

---

### 3️⃣ Ajouter Signaux de Liquidité Marché (Impact ⭐⭐⭐⭐)

```python
def analyze_market_liquidity(self, transaction: TransactionDVF) -> Tuple[int, str]:
    """
    Analyse la liquidité du marché local = facilité de vendre
    Retourne: (score, description)
    """
    if not transaction.code_postal:
        return 0, None

    # Volume de transactions sur 12 mois
    volume_12m = self.db.query(func.count(TransactionDVF.id)).filter(
        TransactionDVF.code_postal == transaction.code_postal,
        TransactionDVF.type_local == transaction.type_local,
        TransactionDVF.date_mutation >= datetime.now() - timedelta(days=365)
    ).scalar() or 0

    # Volume de transactions sur 3 derniers mois
    volume_3m = self.db.query(func.count(TransactionDVF.id)).filter(
        TransactionDVF.code_postal == transaction.code_postal,
        TransactionDVF.type_local == transaction.type_local,
        TransactionDVF.date_mutation >= datetime.now() - timedelta(days=90)
    ).scalar() or 0

    # Accélération du marché
    ratio_acceleration = (volume_3m * 4) / volume_12m if volume_12m > 0 else 0

    # Scoring
    if ratio_acceleration > 1.3:  # Marché en accélération
        score = 30
        desc = f"Marché en accélération +{int((ratio_acceleration-1)*100)}% (liquidité forte)"
    elif ratio_acceleration > 1.1:
        score = 20
        desc = f"Marché dynamique +{int((ratio_acceleration-1)*100)}% (bonne liquidité)"
    elif ratio_acceleration > 0.9:
        score = 10
        desc = "Marché stable (liquidité normale)"
    else:
        score = 0
        desc = f"Marché ralenti {int((1-ratio_acceleration)*100)}% (liquidité faible)"

    # Bonus si volume élevé (marché actif)
    if volume_12m > 50:
        score += 10
        desc += " - Volume élevé"

    return score, desc
```

**Score** : 0-40 points (nouveau)

---

### 4️⃣ Ajouter Analyse Rentabilité Locative (Impact ⭐⭐⭐⭐)

```python
def estimate_rental_yield(self, transaction: TransactionDVF) -> Tuple[float, int, str]:
    """
    Estime le rendement locatif et détecte si faible rendement = signal de vente
    Retourne: (rendement_pct, score, description)
    """
    if not transaction.valeur_fonciere or not transaction.surface_reelle:
        return None, 0, None

    # Estimation loyer selon type et localisation
    # Valeurs moyennes France (à affiner par région)
    if transaction.type_local == 'Appartement':
        loyer_m2_mois = 12  # 12€/m²/mois en moyenne France
        if transaction.code_postal and transaction.code_postal.startswith('75'):
            loyer_m2_mois = 28  # Paris
        elif transaction.code_postal and transaction.code_postal.startswith(('92', '93', '94')):
            loyer_m2_mois = 18  # IDF
    else:  # Maison
        loyer_m2_mois = 10
        if transaction.code_postal and transaction.code_postal.startswith('75'):
            loyer_m2_mois = 22
        elif transaction.code_postal and transaction.code_postal.startswith(('92', '93', '94')):
            loyer_m2_mois = 15

    loyer_annuel = transaction.surface_reelle * loyer_m2_mois * 12
    rendement = (loyer_annuel / transaction.valeur_fonciere) * 100

    # Détection propriétaire investisseur
    is_investor = transaction.proprietaire_type in ['SCI', 'Société probable', 'Potentiel professionnel']

    # Scoring selon rendement (uniquement si investisseur détecté)
    if not is_investor:
        return rendement, 0, None

    if rendement < 2.5:
        score = 35
        desc = f"Rendement {rendement:.1f}% (très faible → arbitrage probable)"
        urgence = "HAUTE"
    elif rendement < 3.5:
        score = 25
        desc = f"Rendement {rendement:.1f}% (faible → vente envisageable)"
        urgence = "MOYENNE"
    elif rendement < 4.5:
        score = 10
        desc = f"Rendement {rendement:.1f}% (correct)"
        urgence = "FAIBLE"
    else:
        score = 0
        desc = f"Rendement {rendement:.1f}% (bon → conservation probable)"
        urgence = "FAIBLE"

    return rendement, score, desc
```

**Score** : 0-35 points (investisseurs uniquement)

---

### 5️⃣ Ajouter Détection Succession (Impact ⭐⭐⭐)

```python
def detect_succession_signals(self, transaction: TransactionDVF) -> Tuple[int, List[str]]:
    """
    Détecte les signaux de succession = vente probable
    Retourne: (score, liste_signaux)
    """
    score = 0
    signaux = []

    # 1. Détention très longue (> 25 ans)
    if transaction.duree_detention_estimee and transaction.duree_detention_estimee >= 25:
        score += 25
        signaux.append(f"Détention {transaction.duree_detention_estimee} ans (succession probable)")

    # 2. Nom propriétaire composé (indivision)
    if transaction.proprietaire_nom and ' ET ' in transaction.proprietaire_nom.upper():
        score += 15
        signaux.append("Indivision détectée (transmission en cours)")

    # 3. Valeur élevée (ISF/IFI)
    if transaction.valeur_fonciere and transaction.valeur_fonciere > 800000:
        score += 10
        signaux.append(f"Valeur {int(transaction.valeur_fonciere/1000)}k€ (optimisation fiscale succession)")

    # 4. Bien vacant (pas de DPE récent)
    if not transaction.classe_dpe:
        score += 10
        signaux.append("Pas de DPE (bien potentiellement vacant)")

    return score, signaux
```

**Score** : 0-60 points

---

### 6️⃣ Ajouter Saisonnalité (Impact ⭐⭐)

```python
def get_seasonal_score(self) -> Tuple[int, str]:
    """
    Ajuste le score selon la saison (printemps = pic de ventes)
    """
    mois = datetime.now().month

    # Printemps (mars-juin) : pic de ventes
    if mois in [3, 4, 5, 6]:
        return 15, "Saison haute (printemps) - moment optimal"

    # Automne (septembre-octobre)
    elif mois in [9, 10]:
        return 10, "Saison favorable (rentrée)"

    # Été (juillet-août) et hiver (décembre-janvier)
    elif mois in [7, 8, 12, 1]:
        return 0, "Saison creuse (vacances/fêtes)"

    # Autres mois
    else:
        return 5, "Saison normale"
```

**Score** : 0-15 points

---

## 📊 Nouveau Système de Scoring

### Total Possible : **235 points** (vs 180 actuellement)

| Critère | Points Max | Description |
|---------|-----------|-------------|
| **Fenêtre cohorte** | 45 | Sweet spot 7-12 ans |
| **Contraintes convergentes** | 60 | DPE F/G, taxe, surface, vétusté |
| **Effet jumeaux (CORRIGÉ)** | 40 | Vraies reventes détectées |
| **Pic de marché** | 35 | Analyse tendance prix |
| **🆕 Liquidité marché** | 40 | Volume + accélération |
| **🆕 Rentabilité locative** | 35 | Si investisseur |
| **🆕 Succession** | 60 | Détention longue, indivision |
| **🆕 Saisonnalité** | 15 | Printemps = optimal |
| **Turnover régulier** | 20 | Investisseur actif |
| **Propriétaire pro** | 15 | SCI, société |

### Nouveaux Seuils

Pour maintenir la distribution :
- **URGENT** (>90) : Score > **110/235** = 47% → **Score > 100**
- **HIGH** (75-89) : Score > **90/235** = 38% → **Score > 85**
- **MEDIUM** (60-74) : Score > **70/235** = 30% → **Score > 70**
- **LOW** (40-59) : Score > **50/235** = 21% → **Score > 50**

Ou normaliser sur 100 points : `score_final = (score_brut / 235) * 100`

---

## 🎯 Validation avec Données Réelles

### Étapes de Validation

1. **Historique de reventes** :
   - Analyser les biens vendus 2+ fois dans DVF
   - Calculer durée moyenne de détention par type/zone
   - Valider la fenêtre 7-12 ans

2. **Taux de conversion** :
   - Tracker les prospects contactés
   - Mesurer combien vendent réellement
   - Ajuster les pondérations

3. **A/B Testing** :
   - Comparer ancien vs nouveau score
   - Mesurer précision des prédictions
   - Optimiser les seuils

4. **Feedback loop** :
   - Base de données `contacts` + `ventes_realisees`
   - Mise à jour mensuelle des modèles
   - Machine learning à terme

---

## 📅 Roadmap d'Implémentation

### Phase 1 : CRITIQUE (Cette semaine)
- ✅ Corriger détection reventes
- ✅ Calculer durée de détention
- ✅ Nettoyer colonnes dupliquées modèle DVF

### Phase 2 : Signaux Avancés (2 semaines)
- ✅ Liquidité marché
- ✅ Rentabilité locative
- ✅ Détection succession
- ✅ Saisonnalité

### Phase 3 : Validation (1 mois)
- Analyser données historiques
- Valider seuils
- Ajuster pondérations
- Tests A/B

### Phase 4 : Intelligence (3 mois)
- Tracker prospects contactés
- Mesurer taux de conversion
- Modèle ML prédictif
- Optimisation continue

---

## 🚀 Impact Attendu

**Avant** :
- Propensity Score basé sur 6 critères
- Détection reventes cassée
- Pas de signaux investisseurs
- Seuils arbitraires

**Après** :
- 10 critères prédictifs validés
- Détection reventes fiable
- Signaux rentabilité + succession
- Scoring normalisé sur données réelles

**Résultat attendu** :
- ⬆️ +40% de précision des prédictions
- ⬆️ +60% de prospects HOT qualifiés
- ⬇️ -50% de faux positifs
- 🎯 ROI commercial x3

---

## 📝 Checklist de Déploiement

```bash
# 1. Backup BDD
pg_dump prospectscore > backup_avant_amelioration.sql

# 2. Déployer nouveau code
git pull origin feature/amelioration-prediction

# 3. Recalculer tous les scores
curl -X POST https://score.2a-immobilier.fr/api/admin/recalculate-all-scores

# 4. Vérifier top prospects
curl https://score.2a-immobilier.fr/api/admin/prospects-hot

# 5. Comparer avant/après
# Exporter CSV avant et après, analyser distribution
```

---

**Prêt à implémenter ces améliorations ?** 🚀

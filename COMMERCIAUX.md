# 👥 Gestion des Commerciaux - ProspectScore Pro

Système complet de gestion des commerciaux avec assignation automatique des prospects à forte probabilité de vente.

---

## 📋 Vue d'ensemble

### Fonctionnalités

- ✅ **Création/gestion des commerciaux** par l'admin
- ✅ **Assignation de zones** (codes postaux, départements)
- ✅ **Assignation automatique** des prospects à forte probabilité
- ✅ **Interface commerciale** pour suivre les prospects
- ✅ **Statistiques de performance** en temps réel
- ✅ **Historique des actions** commerciales

---

## 🚀 Installation

### 1. Créer les tables

```bash
cd /var/www/prospectscore-pro
docker exec -i postgres-prospectscore psql -U prospectscore -d prospectscore < scripts/create_commerciaux.sql
```

### 2. Redémarrer le backend

```bash
docker-compose restart backend
```

### 3. Tester l'API

```bash
curl https://score.2a-immobilier.com/api/
# Vérifier sections "commerciaux_admin" et "commercial"
```

---

## 👨‍💼 ESPACE ADMINISTRATEUR

### Créer un commercial

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

**Réponse** :
```json
{
  "message": "Commercial Jean Dupont créé avec succès",
  "commercial": {
    "id": 1,
    "nom_complet": "Jean Dupont",
    "email": "jean.dupont@2a-immobilier.com",
    "actif": true,
    "zones": {
      "codes_postaux": ["76260", "76370", "76550"],
      "departements": ["76"]
    },
    "configuration": {
      "capacite_max": 100,
      "min_propensity_score": 60
    }
  }
}
```

### Lister tous les commerciaux

```bash
curl https://score.2a-immobilier.com/api/admin/commerciaux/
```

### Assigner automatiquement des prospects

```bash
curl -X POST "https://score.2a-immobilier.com/api/admin/commerciaux/1/assign-prospects?nombre_prospects=20"
```

**Ce qu'il se passe** :
1. ✅ Recherche les biens dans les zones du commercial
2. ✅ Filtre par propensity_score >= 60 (configurable)
3. ✅ Exclut les biens déjà assignés
4. ✅ Trie par score décroissant
5. ✅ Crée les assignations
6. ✅ Met à jour les stats du commercial

**Réponse** :
```json
{
  "message": "20 prospects assignés à Jean Dupont",
  "prospects_assignes": [
    {
      "bien_id": 12345,
      "adresse": "12 RUE DE LA LIBERATION",
      "code_postal": "76260",
      "propensity_score": 85
    },
    ...
  ]
}
```

### Dashboard admin

```bash
curl https://score.2a-immobilier.com/api/admin/commerciaux/dashboard/stats
```

**Réponse** :
```json
{
  "commerciaux": {
    "total": 5,
    "actifs": 4,
    "inactifs": 1
  },
  "prospects": {
    "total_assignes": 350,
    "par_statut": {
      "NOUVEAU": 120,
      "EN_COURS": 80,
      "CONTACTE": 60,
      "RDV_PRIS": 40,
      "MANDAT_OBTENU": 25,
      "PERDU": 20,
      "ABANDONNE": 5
    },
    "par_commercial": [...]
  },
  "performance": {
    "total_mandats": 25,
    "taux_conversion_global": 7.14
  }
}
```

### Modifier un commercial

```bash
curl -X PUT https://score.2a-immobilier.com/api/admin/commerciaux/1 \
  -H "Content-Type: application/json" \
  -d '{
    "codes_postaux_assignes": ["76260", "76370", "76550", "76910"],
    "capacite_max_prospects": 150
  }'
```

### Désactiver un commercial

```bash
curl -X DELETE https://score.2a-immobilier.com/api/admin/commerciaux/1
```

---

## 🏢 INTERFACE COMMERCIAL

### Mon profil

```bash
curl https://score.2a-immobilier.com/api/commercial/me/1
```

### Mes prospects

```bash
# Tous mes prospects
curl https://score.2a-immobilier.com/api/commercial/mes-prospects/1

# Filtrer par statut
curl "https://score.2a-immobilier.com/api/commercial/mes-prospects/1?statut=NOUVEAU"

# Uniquement les nouveaux
curl https://score.2a-immobilier.com/api/commercial/mes-prospects/1/nouveau

# Uniquement les urgents
curl https://score.2a-immobilier.com/api/commercial/mes-prospects/1/urgent
```

**Réponse** :
```json
{
  "commercial": {
    "id": 1,
    "nom": "Jean Dupont"
  },
  "stats": {
    "total": 85,
    "nouveau": 20,
    "en_cours": 30,
    "contacte": 15,
    "rdv_pris": 12,
    "mandat_obtenu": 5
  },
  "prospects": [
    {
      "id": 101,
      "commercial_id": 1,
      "bien_id": 12345,
      "propensity_score": 85,
      "zone_type": "RURAL",
      "statut": "NOUVEAU",
      "priorite": "HAUTE",
      "dates": {
        "assignation": "2025-11-07T14:30:00",
        "premier_contact": null,
        ...
      },
      "bien": {
        "adresse": "12 RUE DE LA LIBERATION",
        "code_postal": "76260",
        "commune": "CRIEL-SUR-MER",
        "type_local": "Maison",
        "surface_reelle": 95.0,
        "nombre_pieces": 5,
        "last_price": 185000.0,
        "features": {...}
      }
    },
    ...
  ]
}
```

### Mettre à jour un prospect

```bash
# Marquer comme contacté
curl -X POST "https://score.2a-immobilier.com/api/commercial/mes-prospects/1/101/marquer-contacte?notes=Propriétaire+intéressé"

# Planifier un RDV
curl -X POST "https://score.2a-immobilier.com/api/commercial/mes-prospects/1/101/prendre-rdv?date_rdv=2025-11-15T10:00:00&notes=RDV+visite+bien"

# Mise à jour manuelle
curl -X PUT https://score.2a-immobilier.com/api/commercial/mes-prospects/1/101 \
  -H "Content-Type: application/json" \
  -d '{
    "statut": "INTERESSE",
    "notes_commercial": "Propriétaire très motivé pour vendre",
    "action": {
      "type_action": "APPEL",
      "notes": "Discussion de 15min, intéressé par estimation"
    }
  }'
```

### Mes statistiques

```bash
curl https://score.2a-immobilier.com/api/commercial/mes-stats/1
```

**Réponse** :
```json
{
  "commercial": {...},
  "periode_actuelle": {
    "total_prospects": 85,
    "nouveaux_cette_semaine": 12,
    "rdv_a_venir": 5
  },
  "repartition_statuts": {...},
  "objectifs": {
    "capacite_max": 100,
    "prospects_actifs": 85,
    "places_disponibles": 15
  }
}
```

### Mes zones et opportunités

```bash
curl https://score.2a-immobilier.com/api/commercial/mes-zones/1
```

**Réponse** :
```json
{
  "zones_assignees": {
    "codes_postaux": ["76260", "76370", "76550"],
    "departements": ["76"]
  },
  "opportunites": {
    "par_code_postal": [
      {
        "code_postal": "76260",
        "opportunites_disponibles": 45
      },
      {
        "code_postal": "76370",
        "opportunites_disponibles": 32
      }
    ],
    "total_disponible": 77
  }
}
```

---

## 📊 Statuts des Prospects

| Statut | Description | Action suivante |
|--------|-------------|-----------------|
| `NOUVEAU` | Vient d'être assigné | Contacter |
| `EN_COURS` | Prospection en cours | Appeler régulièrement |
| `CONTACTE` | Contact établi | Qualifier l'intérêt |
| `RDV_PRIS` | Rendez-vous planifié | Préparer la visite |
| `INTERESSE` | Intéressé par une vente | Proposer estimation |
| `MANDAT_OBTENU` | Mandat signé ✅ | Diffuser l'annonce |
| `PERDU` | Prospect perdu | Archiver |
| `ABANDONNE` | Prospection abandonnée | Archiver |

---

## 🎯 Workflow Complet

### 1. Admin crée le commercial

```bash
POST /api/admin/commerciaux/
```

### 2. Admin assigne des zones

```json
{
  "codes_postaux_assignes": ["76260", "76370"],
  "min_propensity_score": 60
}
```

### 3. Admin assigne des prospects automatiquement

```bash
POST /api/admin/commerciaux/1/assign-prospects?nombre_prospects=20
```

Le système :
- Sélectionne les 20 meilleurs prospects (propensity_score ≥ 60)
- Dans les zones 76260 et 76370
- Pas encore assignés
- Les assigne au commercial

### 4. Commercial récupère ses nouveaux prospects

```bash
GET /api/commercial/mes-prospects/1/nouveau
```

### 5. Commercial contacte et met à jour

```bash
POST /api/commercial/mes-prospects/1/101/marquer-contacte
```

### 6. Commercial planifie des RDV

```bash
POST /api/commercial/mes-prospects/1/101/prendre-rdv
```

### 7. Admin suit la performance

```bash
GET /api/admin/commerciaux/dashboard/stats
```

---

## 🔄 Assignation Automatique

### Critères de sélection

1. ✅ **Zone géographique** : Dans les codes postaux/départements du commercial
2. ✅ **Score minimum** : propensity_score ≥ min_propensity_score (défaut: 60)
3. ✅ **Disponibilité** : Bien pas encore assigné ou prospect terminé (PERDU, MANDAT_OBTENU)
4. ✅ **Features calculées** : features_calculated = TRUE
5. ✅ **Capacité** : Commercial n'a pas atteint sa capacité_max

### Priorité assignée

- **HAUTE** : propensity_score ≥ 80
- **MOYENNE** : propensity_score ≥ 60
- **BASSE** : propensity_score < 60

---

## 🛠️ Cas d'usage

### Cas 1 : Nouveau commercial

```bash
# 1. Créer le commercial
curl -X POST /api/admin/commerciaux/ -d '{...}'

# 2. Assigner 50 premiers prospects
curl -X POST /api/admin/commerciaux/1/assign-prospects?nombre_prospects=50

# 3. Commercial commence à travailler
curl /api/commercial/mes-prospects/1/nouveau
```

### Cas 2 : Commercial atteint sa capacité

```bash
# Augmenter la capacité
curl -X PUT /api/admin/commerciaux/1 -d '{
  "capacite_max_prospects": 150
}'

# Assigner plus de prospects
curl -X POST /api/admin/commerciaux/1/assign-prospects?nombre_prospects=30
```

### Cas 3 : Nouvelle zone pour un commercial

```bash
# Ajouter des codes postaux
curl -X PUT /api/admin/commerciaux/1 -d '{
  "codes_postaux_assignes": ["76260", "76370", "76550", "76910"]
}'

# Assigner les nouveaux prospects de la zone
curl -X POST /api/admin/commerciaux/1/assign-prospects?nombre_prospects=20
```

---

## 📈 Tableaux de bord

### Vue SQL : Performance des commerciaux

```sql
SELECT * FROM v_performance_commerciaux;
```

### Vue SQL : Prospects par statut

```sql
SELECT * FROM v_prospects_par_statut;
```

---

## ⚙️ Configuration

### Paramètres par commercial

- `capacite_max_prospects` : Nombre max de prospects simultanés (défaut: 100)
- `min_propensity_score` : Score minimum pour assignation automatique (défaut: 60)
- `actif` : Commercial actif ou non

### Règles métier

- Un prospect ne peut être assigné qu'à un seul commercial actif
- Un commercial inactif ne reçoit plus de prospects
- La capacité max est une limite souple (peut être dépassée manuellement)

---

**Version** : 2.0.0
**Date** : 2025-11-07
**Auteur** : Claude

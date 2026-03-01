# Import DVF 2018-2025 + Auto-Update Mensuel

## 📋 Vue d'Ensemble

Ce document explique comment :
1. **Importer les données DVF 2018-2025** (8 années manquantes) pour compléter l'historique
2. **Configurer l'auto-update mensuel** pour maintenir les données à jour automatiquement

## 🎯 Objectif

Enrichir ProspectScore Pro avec 12 années complètes de transactions immobilières (2014-2025) et automatiser les mises à jour mensuelles.

## 📊 Données DVF

**Source** : data.gouv.fr (données officielles DGFiP)
**Format** : CSV (délimiteur `,`, dates ISO `YYYY-MM-DD`, décimales `.`)
**Départements** : 14, 27, 60, 62, 76, 80 (région 2A Immobilier)
**Volume attendu** : ~15-20M transactions supplémentaires (2018-2025)

---

## ⚡ Import Rapide 2018-2025

### Prérequis

- ✅ VPS accessible en SSH
- ✅ PostgreSQL Docker (`postgres-prospectscore`) opérationnel
- ✅ Table `valeurs_foncieres` existante
- ✅ Espace disque : ~10GB libres dans `/tmp` et `/var/lib/docker`
- ✅ Connexion internet stable

### Étape 1 : Se connecter au VPS

```bash
ssh ubuntu@146.59.228.175
```

### Étape 2 : Naviguer vers le projet

```bash
cd /var/www/prospectscore-pro
```

### Étape 3 : Vérifier les scripts

```bash
# Lister les scripts DVF
ls -lh scripts/import_dvf_*

# Vérifier qu'ils sont exécutables
# Si nécessaire :
chmod +x scripts/import_dvf_2018_2025.sh
chmod +x scripts/import_dvf_monthly_improved.sh
```

### Étape 4 : Lancer l'import

```bash
# Exécution avec sudo (pour Docker)
sudo bash scripts/import_dvf_2018_2025.sh
```

**Durée estimée** : 2-4 heures (selon connexion et charge serveur)

### Étape 5 : Suivre l'import en temps réel

Dans un autre terminal :

```bash
# Suivre le log en direct
tail -f /var/log/prospectscore/dvf_import_2018_2025.log
```

### Étape 6 : Vérifier l'import

Une fois terminé :

```bash
# Compter les transactions par année
sudo docker exec postgres-prospectscore psql -U prospectscore -d prospectscore << 'SQL'
SELECT
    LEFT(date_mutation, 4) as annee,
    COUNT(*) as nb_transactions,
    COUNT(DISTINCT code_postal) as nb_codes_postaux,
    COUNT(DISTINCT commune) as nb_communes
FROM valeurs_foncieres
GROUP BY LEFT(date_mutation, 4)
ORDER BY annee;
SQL
```

Vous devriez voir :
```
 annee | nb_transactions | nb_codes_postaux | nb_communes
-------+-----------------+------------------+-------------
 2014  |         2516688 |              ... |         ...
 2015  |         2749830 |              ... |         ...
 2016  |         2936524 |              ... |         ...
 2017  |         3361073 |              ... |         ...
 2018  |         xxxxxxx |              ... |         ...
 2019  |         xxxxxxx |              ... |         ...
 ...
```

---

## 🔄 Configuration Auto-Update Mensuel

### Objectif

Importer automatiquement les nouvelles données DVF chaque mois sans intervention manuelle.

### Fréquence Recommandée

**2ème mercredi du mois à 3h00** (après publication data.gouv.fr)

### Méthode 1 : Cron (Simple)

#### 1. Éditer le crontab

```bash
crontab -e
```

#### 2. Ajouter cette ligne

```bash
# Import DVF mensuel automatique
0 3 8-14 * 3 /var/www/prospectscore-pro/scripts/import_dvf_monthly_improved.sh >> /var/log/prospectscore/dvf_cron.log 2>&1
```

#### 3. Sauvegarder et quitter

- Avec nano : `Ctrl+O` puis `Ctrl+X`
- Avec vim : `:wq`

#### 4. Vérifier le cron

```bash
# Lister les crons actifs
crontab -l

# Vérifier que le service cron est actif
sudo systemctl status cron
```

### Méthode 2 : Systemd Timer (Recommandé)

Voir le fichier `scripts/setup_cron_dvf.md` pour la configuration complète avec systemd.

### Test Manuel

Avant d'activer l'automatisation, testez le script :

```bash
# Test complet
sudo bash scripts/import_dvf_monthly_improved.sh

# Vérifier le log
cat /var/log/prospectscore/dvf_monthly_$(date +%Y%m%d).log
```

---

## 📂 Structure des Fichiers

```
prospectscore-pro/
├── scripts/
│   ├── import_dvf_2018_2025.sh          # Import historique 2018-2025
│   ├── import_dvf_monthly_improved.sh   # Auto-update mensuel
│   ├── setup_cron_dvf.md                # Guide configuration cron
│   └── ...
├── docs/
│   └── IMPORT_DVF_2018_2025.md          # Ce document
└── /var/log/prospectscore/
    ├── dvf_import_2018_2025.log         # Log import historique
    ├── dvf_monthly_YYYYMMDD.log         # Logs mensuels
    └── dvf_cron.log                     # Log global cron
```

---

## 🔍 Vérifications Post-Import

### 1. Total Transactions

```bash
sudo docker exec postgres-prospectscore psql -U prospectscore -d prospectscore -c "
SELECT COUNT(*) as total_transactions FROM valeurs_foncieres;
"
```

**Attendu** : ~25-30M transactions (11.5M 2014-2017 + 15-20M 2018-2025)

### 2. Qualité des Données

```bash
sudo docker exec postgres-prospectscore psql -U prospectscore -d prospectscore << 'SQL'
SELECT
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE valeur_fonciere IS NULL OR valeur_fonciere = '') as missing_prix,
    COUNT(*) FILTER (WHERE date_mutation IS NULL OR date_mutation = '') as missing_date,
    COUNT(*) FILTER (WHERE code_postal IS NULL OR code_postal = '') as missing_cp,
    ROUND(100.0 * COUNT(*) FILTER (WHERE valeur_fonciere IS NOT NULL AND valeur_fonciere != '') / COUNT(*), 2) as qualite_pct
FROM valeurs_foncieres
WHERE LEFT(date_mutation, 4) >= '2018';
SQL
```

**Attendu** : Qualité > 95%

### 3. Distribution par Type de Bien

```bash
sudo docker exec postgres-prospectscore psql -U prospectscore -d prospectscore << 'SQL'
SELECT
    type_local,
    COUNT(*) as nb_transactions,
    ROUND(AVG(REPLACE(valeur_fonciere, ',', '.')::NUMERIC), 0) as prix_moyen
FROM valeurs_foncieres
WHERE LEFT(date_mutation, 4) >= '2018'
  AND type_local != ''
  AND valeur_fonciere != ''
GROUP BY type_local
ORDER BY nb_transactions DESC;
SQL
```

---

## 🛠️ Dépannage

### Problème : "No space left on device"

**Solution** :
```bash
# Vérifier l'espace disque
df -h

# Nettoyer Docker si nécessaire
sudo docker system prune -a

# Nettoyer /tmp
sudo rm -rf /tmp/dvf_*
```

### Problème : "Permission denied"

**Solution** :
```bash
# Vérifier les permissions du script
ls -la scripts/import_dvf_2018_2025.sh

# Rendre exécutable si nécessaire
chmod +x scripts/import_dvf_2018_2025.sh

# Exécuter avec sudo
sudo bash scripts/import_dvf_2018_2025.sh
```

### Problème : "docker: command not found"

**Solution** :
```bash
# Vérifier Docker
sudo systemctl status docker

# Redémarrer Docker si nécessaire
sudo systemctl restart docker
```

### Problème : Import très lent

**Causes possibles** :
1. Connexion internet lente → Vérifier `ping data.gouv.fr`
2. PostgreSQL surchargé → Vérifier `docker stats postgres-prospectscore`
3. Disque lent → Vérifier `iostat -x 1`

**Solution** : Import par années séparées (modifier le script pour une seule année à la fois)

### Problème : Doublons après import

**Vérification** :
```bash
sudo docker exec postgres-prospectscore psql -U prospectscore -d prospectscore << 'SQL'
SELECT id, COUNT(*)
FROM valeurs_foncieres
GROUP BY id
HAVING COUNT(*) > 1;
SQL
```

**Note** : Normalement, `ON CONFLICT DO NOTHING` dans le script empêche les doublons.

---

## 📊 Monitoring

### Logs Disponibles

```bash
# Derniers imports
ls -lt /var/log/prospectscore/dvf_*.log | head -5

# Afficher le dernier log complet
cat $(ls -t /var/log/prospectscore/dvf_*.log | head -1)

# Rechercher des erreurs
grep -i "error\|erreur\|échec" /var/log/prospectscore/dvf_*.log
```

### Stats Rapides

```bash
# Evolution par année
sudo docker exec postgres-prospectscore psql -U prospectscore -d prospectscore << 'SQL'
SELECT
    LEFT(date_mutation, 4) as annee,
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE type_local = 'Maison') as maisons,
    COUNT(*) FILTER (WHERE type_local = 'Appartement') as appartements
FROM valeurs_foncieres
GROUP BY LEFT(date_mutation, 4)
ORDER BY annee DESC
LIMIT 10;
SQL
```

---

## 🚀 Prochaines Étapes (Optionnel)

### Phase 3 : Migration vers `transactions_dvf`

Si vous souhaitez migrer vers la table `transactions_dvf` (format typé DECIMAL, DATE) :

1. Créer un script de migration avec conversion format FR → US
2. Exécuter la migration par batches
3. Activer l'enrichissement automatique (PropensityPredictor, SmartEnricher)

**Documentation** : À venir dans `MIGRATION_DVF.md`

### Phase 4 : Dashboard Monitoring

Créer un dashboard pour suivre :
- Nombre de transactions par département/année
- Taux d'enrichissement
- Scores de propension
- Alertes qualité données

---

## 📞 Support

### En cas de problème

1. **Vérifier les logs** : `/var/log/prospectscore/dvf_*.log`
2. **Tester manuellement** : `sudo bash scripts/import_dvf_2018_2025.sh`
3. **Vérifier PostgreSQL** : `sudo docker ps | grep postgres`
4. **Vérifier l'espace disque** : `df -h`

### Ressources

- **Source de données** : https://files.data.gouv.fr/geo-dvf/latest/csv/
- **Documentation DVF** : https://www.data.gouv.fr/fr/datasets/demandes-de-valeurs-foncieres/
- **README Scripts** : `/scripts/README_IMPORT_HISTORIQUE.md`

---

## ✅ Checklist Succès

- [ ] Import 2018-2025 terminé sans erreurs
- [ ] Total transactions > 25M dans `valeurs_foncieres`
- [ ] Qualité données > 95%
- [ ] Cron configuré et testé manuellement
- [ ] Logs générés correctement
- [ ] Dashboard/stats vérifiés

**Félicitations ! Votre système DVF est maintenant complet et automatisé !** 🎉

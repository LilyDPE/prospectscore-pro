# Configuration CRON pour Import DVF Automatique

## Installation du Cron Job

### Étape 1 : Éditer le crontab de l'utilisateur ubuntu

```bash
crontab -e
```

### Étape 2 : Ajouter cette ligne

```bash
# Import DVF mensuel - 2ème mercredi du mois à 3h00
0 3 8-14 * 3 /var/www/prospectscore-pro/scripts/import_dvf_monthly_improved.sh >> /var/log/prospectscore/dvf_cron.log 2>&1
```

**Explication** :
- `0 3` = à 3h00 du matin
- `8-14` = jours 8 à 14 du mois (le 2ème mercredi tombe forcément dans cette période)
- `* 3` = tous les mois, le mercredi (3 = mercredi)
- Logs redirigés vers `/var/log/prospectscore/dvf_cron.log`

### Étape 3 : Vérifier le cron

```bash
# Lister les crons actifs
crontab -l

# Vérifier les prochaines exécutions (avec cronic)
# Note : cronic n'est pas toujours installé par défaut
```

## Test Manuel

Avant d'activer le cron, testez le script manuellement :

```bash
# Sur le VPS
cd /var/www/prospectscore-pro
sudo bash scripts/import_dvf_monthly_improved.sh
```

Vérifiez le log :

```bash
tail -f /var/log/prospectscore/dvf_monthly_*.log
```

## Alternative : Systemd Timer

Si vous préférez utiliser systemd (plus moderne que cron) :

### 1. Créer le service

Fichier : `/etc/systemd/system/dvf-import-monthly.service`

```ini
[Unit]
Description=Import mensuel DVF (Demandes de Valeurs Foncières)
After=network.target docker.service

[Service]
Type=oneshot
User=ubuntu
WorkingDirectory=/var/www/prospectscore-pro
ExecStart=/bin/bash /var/www/prospectscore-pro/scripts/import_dvf_monthly_improved.sh
StandardOutput=journal
StandardError=journal
TimeoutStartSec=7200

[Install]
WantedBy=multi-user.target
```

### 2. Créer le timer

Fichier : `/etc/systemd/system/dvf-import-monthly.timer`

```ini
[Unit]
Description=Timer pour import DVF mensuel (2ème mercredi à 3h)

[Timer]
# 2ème mercredi du mois à 3h
OnCalendar=Wed *-*-8..14 03:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

### 3. Activer le timer

```bash
# Recharger systemd
sudo systemctl daemon-reload

# Activer (démarrage auto au boot)
sudo systemctl enable dvf-import-monthly.timer

# Démarrer
sudo systemctl start dvf-import-monthly.timer

# Vérifier
sudo systemctl status dvf-import-monthly.timer

# Voir les prochaines exécutions
sudo systemctl list-timers dvf-import-monthly.timer
```

### 4. Test manuel du service

```bash
sudo systemctl start dvf-import-monthly.service
sudo journalctl -u dvf-import-monthly.service -f
```

## Monitoring

### Vérifier les logs

```bash
# Logs du dernier import
ls -lt /var/log/prospectscore/dvf_monthly_*.log | head -1

# Afficher le dernier log
cat $(ls -t /var/log/prospectscore/dvf_monthly_*.log | head -1)

# Suivre en temps réel
tail -f /var/log/prospectscore/dvf_cron.log
```

### Stats rapides

```bash
# Compter les transactions par année
sudo docker exec postgres-prospectscore psql -U prospectscore -d prospectscore -c "
SELECT
    LEFT(date_mutation, 4) as annee,
    COUNT(*) as nb_transactions
FROM valeurs_foncieres
GROUP BY LEFT(date_mutation, 4)
ORDER BY annee DESC
LIMIT 10;
"
```

## Gestion des Erreurs

### Si le cron ne s'exécute pas

1. Vérifier que le service cron est actif :
   ```bash
   sudo systemctl status cron
   ```

2. Vérifier les logs système :
   ```bash
   sudo grep CRON /var/log/syslog
   ```

3. Vérifier les permissions :
   ```bash
   ls -la /var/www/prospectscore-pro/scripts/import_dvf_monthly_improved.sh
   # Doit être exécutable : -rwxr-xr-x
   ```

### Si l'import échoue

1. Vérifier l'espace disque :
   ```bash
   df -h
   ```

2. Vérifier que PostgreSQL est accessible :
   ```bash
   sudo docker ps | grep postgres
   ```

3. Tester manuellement :
   ```bash
   sudo bash scripts/import_dvf_monthly_improved.sh
   ```

## Rotation des Logs

Pour éviter que les logs ne prennent trop de place, configurez logrotate :

Fichier : `/etc/logrotate.d/prospectscore`

```
/var/log/prospectscore/*.log {
    weekly
    rotate 12
    compress
    delaycompress
    missingok
    notifempty
    create 0644 ubuntu ubuntu
}
```

Tester :

```bash
sudo logrotate -f /etc/logrotate.d/prospectscore
```

## Email d'Alerte (Optionnel)

Pour recevoir un email en cas d'échec, ajoutez en fin du script cron :

```bash
0 3 8-14 * 3 /var/www/prospectscore-pro/scripts/import_dvf_monthly_improved.sh || echo "Import DVF échoué le $(date)" | mail -s "[ALERT] Import DVF Échoué" admin@prospectscore.com
```

**Note** : Nécessite un serveur mail configuré (postfix, sendmail, ou autre).

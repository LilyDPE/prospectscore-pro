# 🔧 Correction du Routing Nginx - ProspectScore Pro

## 🎯 Problème identifié

**Symptôme**: https://score.2a-immobilier.com/api/ retourne "Not Found" (404)

**Cause**:
1. FastAPI n'avait pas de route pour `/api/` exactement (seulement `/api/auth/*`, `/api/prospects/*`, etc.)
2. La configuration Nginx pouvait être optimisée pour mieux gérer le proxy

## ✅ Solutions appliquées

### 1. Ajout d'une route `/api/` dans FastAPI

**Fichier**: `backend/main.py`

Ajout d'un endpoint racine pour l'API qui retourne les informations de base et la liste des endpoints disponibles :

```python
@app.get("/api/")
def api_root():
    """Endpoint racine de l'API"""
    return {
        "app": "ProspectScore Pro API",
        "version": "1.0.0",
        "status": "operational",
        "endpoints": {
            "docs": "/api/docs",
            "health": "/api/",
            "auth": "/api/auth/*",
            "prospects": "/api/prospects/*",
            "stats": "/api/stats/dashboard",
            "public": "/api/public/*"
        }
    }
```

### 2. Configuration Nginx optimisée

**Fichier**: `nginx.conf`

Améliorations apportées :
- ✅ Gestion correcte de `/api/` avec trailing slash
- ✅ Keepalive pour de meilleures performances
- ✅ Timeouts configurés
- ✅ Headers HTTP/2 et WebSocket
- ✅ Configuration HTTPS avec TLS 1.2/1.3
- ✅ Health check endpoint
- ✅ Logs dédiés pour le débogage

**Points clés** :
```nginx
# Proxy vers le backend avec trailing slash
location /api/ {
    proxy_pass http://prospectscore_backend/api/;
    # ... headers ...
}
```

## 🚀 Déploiement sur le VPS

### Méthode 1 : Script automatique (recommandé)

```bash
# Sur le VPS, dans le répertoire du projet
sudo ./update-nginx.sh
```

Le script va :
1. ✅ Sauvegarder la configuration actuelle
2. ✅ Copier la nouvelle configuration
3. ✅ Tester la validité de la config
4. ✅ Recharger Nginx
5. ✅ Vérifier la connectivité

### Méthode 2 : Manuelle

```bash
# 1. Sauvegarder l'ancienne config
sudo cp /etc/nginx/sites-available/prospectscore-pro /etc/nginx/sites-available/prospectscore-pro.backup

# 2. Copier la nouvelle config
sudo cp nginx.conf /etc/nginx/sites-available/prospectscore-pro

# 3. Tester la configuration
sudo nginx -t

# 4. Recharger Nginx
sudo systemctl reload nginx

# 5. Vérifier le statut
sudo systemctl status nginx
```

### Méthode 3 : Redémarrer les conteneurs Docker

Si vous avez modifié `main.py`, redémarrez le backend :

```bash
cd /var/www/prospectscore-pro  # ou le chemin de votre projet
docker-compose restart backend
```

## 🧪 Tests après déploiement

### 1. Tester l'endpoint racine de l'API

```bash
curl -v https://score.2a-immobilier.com/api/
```

**Résultat attendu** :
```json
{
  "app": "ProspectScore Pro API",
  "version": "1.0.0",
  "status": "operational",
  "endpoints": {
    "docs": "/api/docs",
    "health": "/api/",
    "auth": "/api/auth/*",
    "prospects": "/api/prospects/*",
    "stats": "/api/stats/dashboard",
    "public": "/api/public/*"
  }
}
```

### 2. Tester les autres endpoints

```bash
# Stats publiques
curl https://score.2a-immobilier.com/api/public/stats

# Documentation
curl https://score.2a-immobilier.com/docs

# Départements
curl https://score.2a-immobilier.com/api/public/departements
```

### 3. Tester depuis le navigateur

Ouvrir dans un navigateur :
- https://score.2a-immobilier.com/api/
- https://score.2a-immobilier.com/docs (documentation interactive)
- https://score.2a-immobilier.com/api/public/stats

## 📊 Diagnostic en cas de problème

### Vérifier que les conteneurs fonctionnent

```bash
docker ps
```

Vous devriez voir :
- `prospectscore-backend` (port 8003)
- `prospectscore-frontend` (port 3003)
- `postgres-prospectscore` (port 5433)

### Vérifier les logs du backend

```bash
docker logs prospectscore-backend --tail 50
```

### Vérifier les logs Nginx

```bash
# Logs d'erreur
sudo tail -f /var/log/nginx/prospectscore_error.log

# Logs d'accès
sudo tail -f /var/log/nginx/prospectscore_access.log
```

### Tester en local sur le VPS

```bash
# Backend directement
curl http://localhost:8003/api/

# Via Nginx
curl http://localhost/api/
```

## 🔍 Détails techniques

### Architecture du routing

```
Client
  ↓
Nginx (port 80/443)
  ├─ /api/* → Backend FastAPI (port 8003)
  ├─ /docs → Backend FastAPI (port 8003)
  └─ /* → Frontend React (port 3003)
```

### Routes FastAPI disponibles

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/` | GET | Root (page d'accueil) |
| `/api/` | GET | **NOUVEAU** - Info API |
| `/api/auth/register` | POST | Inscription |
| `/api/auth/login` | POST | Connexion |
| `/api/prospects/search` | POST | Recherche prospects |
| `/api/public/stats` | GET | Stats publiques |
| `/docs` | GET | Documentation interactive |

## 📝 Changements apportés

### Fichiers modifiés

1. ✅ `backend/main.py` - Ajout de la route `/api/`
2. ✅ `nginx.conf` - Nouvelle configuration Nginx optimisée
3. ✅ `update-nginx.sh` - Script de déploiement automatique

### Fichiers créés

1. ✅ `NGINX-FIX.md` - Cette documentation

## ✨ Améliorations futures possibles

1. **Features ML** : Créer l'endpoint `GET /api/prospects/{id}/features` mentionné dans le plan
2. **Monitoring** : Ajouter des endpoints de health check détaillés
3. **Cache** : Configurer un cache Nginx pour les requêtes publiques
4. **Rate limiting** : Limiter le nombre de requêtes par IP
5. **Compression** : Activer gzip pour les réponses JSON

## 🆘 Support

Si le problème persiste après le déploiement :

1. Vérifier les logs (voir section Diagnostic)
2. Vérifier que tous les conteneurs sont démarrés
3. Vérifier la configuration DNS (score.2a-immobilier.com doit pointer vers le VPS)
4. Vérifier le firewall (ports 80 et 443 ouverts)

---

**Date de création** : 2025-11-07
**Auteur** : Claude
**Version** : 1.0.0

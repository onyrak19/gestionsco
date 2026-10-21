# Mise en ligne sur Render (offre gratuite)

Ce dossier est prêt pour un déploiement par **Blueprint** : Render lit `render.yaml`, crée une base
PostgreSQL et un site web (Docker), puis démarre l'application.

## Ce qui a été préparé

| Fichier | Rôle |
|---|---|
| `Dockerfile` | Compile l'interface React, installe Django, démarre avec gunicorn. |
| `.dockerignore` | Garde les secrets (`.env`) et les fichiers locaux hors de l'image. |
| `render.yaml` | Décrit la base PostgreSQL gratuite et le site web gratuit (région **Singapour**). |
| `backend/gestion_scolaire/settings.py` | Lit `DATABASE_URL`, hôtes autorisés, CSRF, HTTPS derrière le proxy, WhiteNoise, journaux. |
| `backend/gestion_scolaire/dburl.py` | Lecture de `DATABASE_URL` (testée). |
| `backend/accounts/management/commands/creer_admin.py` | Crée le compte administrateur au démarrage. |
| `backend/requirements.txt` | Ajoute `psycopg`, `gunicorn`, `whitenoise` ; `mysqlclient` passe dans `requirements-mysql.txt`. |
| `.gitignore`, `.gitattributes` | Évitent d'envoyer `.env`, `node_modules`, etc. ; fins de ligne Unix. |

En local, **rien ne change** : sans `DATABASE_URL`, l'application utilise SQLite (ou MySQL si
`DB_ENGINE=mysql` est dans votre `backend/.env`).

## Variables d'environnement (sur Render)

| Variable | Valeur | Origine |
|---|---|---|
| `DATABASE_URL` | adresse de la base | automatique (`render.yaml`) |
| `DJANGO_SECRET_KEY` | clé aléatoire | automatique (`generateValue`) |
| `DJANGO_DEBUG` | `False` | `render.yaml` |
| `RESEAU_LOCAL` | `False` | `render.yaml` |
| `TIME_ZONE` | `Indian/Antananarivo` | `render.yaml` |
| `DEVISE` | `Ar` | `render.yaml` |
| `ADMIN_USERNAME` | `admin` (modifiable) | `render.yaml` |
| `ADMIN_PASSWORD` | **votre mot de passe** (8 caractères minimum) | demandé par Render à la création |
| `ADMIN_RESET_PASSWORD` | `False` | passez à `True` pour remplacer le mot de passe (oublié), puis remettez `False` |

`RENDER_EXTERNAL_HOSTNAME` et `PORT` sont fournis par Render lui-même.

## Limites de l'offre gratuite (à connaître)

1. **La base PostgreSQL gratuite expire 30 jours après sa création** (14 jours de grâce pour passer à un
   plan payant, sinon elle est supprimée avec ses données). C'est donc adapté à un **essai / une démonstration**,
   pas à l'usage réel d'une école. Pour une utilisation durable : plan payant de Render, ou une base PostgreSQL
   gratuite hébergée ailleurs (il suffit de remplacer la variable `DATABASE_URL`).
2. **Mise en veille** : après 15 minutes sans visite, le site s'endort ; la visite suivante prend environ
   une minute.
3. **Photos d'élèves et pièces jointes non conservées** : le disque d'un service gratuit est effacé à chaque
   redémarrage, mise en veille ou nouveau déploiement. Les photos disparaissent (l'application affiche alors
   « introuvable » sans planter). Les disques persistants sont réservés aux plans payants.
4. **Pas de terminal** sur l'offre gratuite : migrations et création de l'administrateur sont faites
   automatiquement au démarrage.
5. **Pas de sauvegarde automatique** de la base gratuite : utilisez régulièrement
   *Import / Export* dans l'application.
6. **Django 4.2** (version fixée par le projet) est arrivé en fin de support en avril 2026 (à vérifier sur djangoproject.com) :
   prévoyez une mise à jour vers une version supportée avant un usage réel.

## Dépannage rapide

- **Le déploiement échoue** : onglet *Logs* du service sur Render, copiez les dernières lignes.
- **« DisallowedHost »** : l'adresse utilisée n'est pas dans `DJANGO_ALLOWED_HOSTS` (domaine personnalisé).
- **Mot de passe administrateur oublié** : variable `ADMIN_RESET_PASSWORD=True` + nouveau `ADMIN_PASSWORD`,
  redéployez, puis remettez `False`.
- **Première page très lente** : le site se réveille (voir limite 2).

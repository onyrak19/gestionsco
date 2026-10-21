import importlib.util
import os
from pathlib import Path
from datetime import timedelta

from django.core.exceptions import ImproperlyConfigured

from .dburl import config_depuis_url

BASE_DIR = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Lecture de la configuration (variables d'environnement / fichier .env)
# ---------------------------------------------------------------------------
def _charger_fichier_env():
    """Charge backend/.env s'il existe (sans dépendance externe)."""
    fichier = BASE_DIR / '.env'
    if not fichier.exists():
        return
    for ligne in fichier.read_text(encoding='utf-8').splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith('#') or '=' not in ligne:
            continue
        cle, _, valeur = ligne.partition('=')
        os.environ.setdefault(cle.strip(), valeur.strip().strip('"').strip("'"))


_charger_fichier_env()


def env(nom, defaut=''):
    # Une variable absente OU vide (ex. « DJANGO_SECRET_KEY= » dans .env) donne la valeur par défaut
    return os.environ.get(nom) or defaut


def env_bool(nom, defaut=False):
    return env(nom, str(defaut)).strip().lower() in ('1', 'true', 'yes', 'on')


def env_list(nom, defaut=''):
    return [v.strip() for v in env(nom, defaut).split(',') if v.strip()]


# ---------------------------------------------------------------------------
# Sécurité
# ---------------------------------------------------------------------------
_CLE_DEV = 'django-insecure-gestion-scolaire-v1-changez-en-production'
SECRET_KEY = env('DJANGO_SECRET_KEY', _CLE_DEV)
DEBUG = env_bool('DJANGO_DEBUG', True)

# Réseau local : l'application est ouverte aux autres appareils du même Wi-Fi
# (téléphones, tablettes, autres ordinateurs). Actif par défaut en développement.
# En ligne (internet) : mettez RESEAU_LOCAL=False et listez vos domaines.
RESEAU_LOCAL = env_bool('RESEAU_LOCAL', DEBUG)
if RESEAU_LOCAL:
    ALLOWED_HOSTS = ['*']   # l'adresse IP du PC change selon le réseau
else:
    ALLOWED_HOSTS = env_list('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1')

# --- Hébergement sur Render ---------------------------------------------------
# Render fournit RENDER_EXTERNAL_HOSTNAME (ex. gestionsco.onrender.com) et RENDER=true.
SUR_RENDER = env_bool('RENDER', False)
RENDER_HOTE = env('RENDER_EXTERNAL_HOSTNAME')
if RENDER_HOTE and '*' not in ALLOWED_HOSTS and RENDER_HOTE not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(RENDER_HOTE)

# Origines autorisées pour les formulaires protégés par CSRF (ex. connexion à /admin/) :
# l'adresse Render et les domaines listés dans DJANGO_ALLOWED_HOSTS, en https.
CSRF_TRUSTED_ORIGINS = env_list('CSRF_TRUSTED_ORIGINS')
for _hote in ([RENDER_HOTE] if RENDER_HOTE else []) + env_list('DJANGO_ALLOWED_HOSTS', ''):
    _origine = f'https://{_hote}'
    if _hote not in ('*', 'localhost', '127.0.0.1') and _origine not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(_origine)

# Derrière le proxy de Render : le navigateur parle en https, Django reçoit du http
# accompagné de l'en-tête X-Forwarded-Proto. (La redirection http -> https est faite par Render.)
if not DEBUG and not RESEAU_LOCAL:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(env('SECURE_HSTS_SECONDS', '0'))   # à activer volontairement

if not DEBUG and SECRET_KEY == _CLE_DEV:
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY doit être défini (dans backend/.env) quand DJANGO_DEBUG=False."
    )

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'accounts',
    'school',
    'journal',
    'finance',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# WhiteNoise sert les fichiers statiques de l'interface d'administration Django (/admin/).
# Actif seulement en production et si le paquet est installé : en local, rien ne change.
UTILISE_WHITENOISE = (not DEBUG) and importlib.util.find_spec('whitenoise') is not None
if UTILISE_WHITENOISE:
    MIDDLEWARE.insert(2, 'whitenoise.middleware.WhiteNoiseMiddleware')   # juste après SecurityMiddleware

ROOT_URLCONF = 'gestion_scolaire.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'gestion_scolaire.wsgi.application'

# ---------------------------------------------------------------------------
# Base de données, par ordre de priorité :
#   1. DATABASE_URL (PostgreSQL) : mise en ligne sur Render ;
#   2. DB_ENGINE=mysql : MySQL local (réglages DB_NAME, DB_USER, ...) ;
#   3. sinon SQLite (fichier backend/db.sqlite3) : rien à installer ni à configurer.
# ---------------------------------------------------------------------------
DATABASE_URL = env('DATABASE_URL')
if SUR_RENDER and not DATABASE_URL:
    # Sans cette vérification, l'application démarrerait sur un fichier SQLite effacé
    # à chaque redémarrage : on préfère un échec clair.
    raise ImproperlyConfigured(
        "DATABASE_URL est absent : vérifiez le lien avec la base PostgreSQL dans render.yaml."
    )

if DATABASE_URL:
    try:
        DATABASES = {'default': config_depuis_url(DATABASE_URL)}
    except ValueError as erreur:
        raise ImproperlyConfigured(f"DATABASE_URL est invalide : {erreur}.")
elif env('DB_ENGINE', 'sqlite').lower() == 'sqlite':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': env('DB_NAME', 'gestion_scolaire_v1'),
            'USER': env('DB_USER', 'root'),
            'PASSWORD': env('DB_PASSWORD', ''),
            'HOST': env('DB_HOST', '127.0.0.1'),
            'PORT': env('DB_PORT', '3306'),
            'OPTIONS': {
                'charset': 'utf8mb4',
                'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            },
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'fr-fr'
# Fuseau horaire de l'établissement (ex. Europe/Paris, Africa/Dakar, Indian/Antananarivo)
TIME_ZONE = env('TIME_ZONE', 'Europe/Paris')
USE_I18N = True
USE_TZ = True
# « django-static » et non « static » : l'adresse /static/ est réservée aux fichiers
# de l'interface React (voir gestion_scolaire/frontend.py).
STATIC_URL = 'django-static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {
        'BACKEND': (
            'whitenoise.storage.CompressedStaticFilesStorage' if UTILISE_WHITENOISE
            else 'django.contrib.staticfiles.storage.StaticFilesStorage'
        ),
    },
}

# Fichiers envoyés (photos, pièces jointes) : jamais servis publiquement,
# seulement via les adresses protégées de l'API.
MEDIA_URL = 'media/'
MEDIA_ROOT = Path(env('MEDIA_ROOT', str(BASE_DIR / 'media')))

# Interface React compilée (npm run build), servie par Django pour le réseau local
FRONTEND_BUILD_DIR = BASE_DIR.parent / 'frontend' / 'build'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Devise affichée sur les reçus et les états (ex. Ar, €, FCFA)
DEVISE = env('DEVISE', 'Ar')

# Moyenne annuelle minimale pour être « passant » à la clôture de l'année
SEUIL_PASSAGE = float(env('SEUIL_PASSAGE', '10'))

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        # Comme JWTAuthentication, mais refuse aussi les enseignants dont le
        # compte n'est plus « validé » (désactivé, refusé, en attente).
        'accounts.authentication.StatutJWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    # Notes renvoyées comme nombres (12.5) et non comme chaînes ("12.50")
    'COERCE_DECIMAL_TO_STRING': False,
    # Limite les tentatives de connexion / d'inscription (anti force brute)
    'DEFAULT_THROTTLE_RATES': {
        'login': env('THROTTLE_LOGIN', '10/min'),
        'inscription': env('THROTTLE_INSCRIPTION', '5/hour'),
    },
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=2),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'AUTH_HEADER_TYPES': ('Bearer',),
}

CORS_ALLOWED_ORIGINS = env_list(
    'CORS_ALLOWED_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000'
)
CORS_ALLOW_CREDENTIALS = True
if RESEAU_LOCAL:
    # Interface ouverte depuis un autre appareil (http://192.168.x.x:3000, http://nom-du-pc:3000...)
    CORS_ALLOWED_ORIGIN_REGEXES = [
        r'^https?://localhost(:\d+)?$',
        r'^https?://127\.0\.0\.1(:\d+)?$',
        r'^https?://192\.168\.\d{1,3}\.\d{1,3}(:\d+)?$',
        r'^https?://10\.\d{1,3}\.\d{1,3}\.\d{1,3}(:\d+)?$',
        r'^https?://172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}(:\d+)?$',
        r'^https?://[A-Za-z0-9-]+(\.local)?(:\d+)?$',   # nom de l'ordinateur sur le réseau
    ]

# ---------------------------------------------------------------------------
# Journaux (logs) : en production, tout va sur la sortie standard, que Render affiche
# dans l'onglet « Logs » (sans cela, les erreurs 500 n'y apparaîtraient pas).
# ---------------------------------------------------------------------------
if not DEBUG:
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'handlers': {'console': {'class': 'logging.StreamHandler'}},
        'root': {'handlers': ['console'], 'level': env('LOG_LEVEL', 'INFO')},
        'loggers': {
            'django.request': {'handlers': ['console'], 'level': 'ERROR', 'propagate': False},
        },
    }

"""Lecture de DATABASE_URL (PostgreSQL) sans dépendance externe.

Ce module ne dépend pas de Django : il est simple à tester (voir test_dburl.py).
Les messages d'erreur ne recopient JAMAIS l'adresse (elle contient le mot de passe).
"""
from urllib.parse import parse_qs, unquote, urlsplit

SCHEMAS_POSTGRES = ('postgres', 'postgresql')


def config_depuis_url(url, conn_max_age=60):
    """Transforme « postgresql://utilisateur:mot_de_passe@hote:5432/base »
    en dictionnaire pour DATABASES['default']."""
    parties = urlsplit((url or '').strip())
    if parties.scheme not in SCHEMAS_POSTGRES:
        raise ValueError("l'adresse doit commencer par postgresql:// (ou postgres://)")
    nom = unquote(parties.path.lstrip('/'))
    if not nom:
        raise ValueError("le nom de la base est absent de l'adresse")
    if not parties.hostname:
        raise ValueError("l'hôte est absent de l'adresse")
    try:
        port = parties.port
    except ValueError:
        raise ValueError("le port de l'adresse n'est pas un nombre valide")

    config = {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': nom,
        'USER': unquote(parties.username or ''),
        'PASSWORD': unquote(parties.password or ''),
        'HOST': parties.hostname,
        'PORT': str(port) if port else '',
        # Connexions réutilisées 60 s, et vérifiées avant usage : la base gratuite
        # de Render peut être redémarrée à tout moment.
        'CONN_MAX_AGE': conn_max_age,
        'CONN_HEALTH_CHECKS': True,
    }
    sslmode = parse_qs(parties.query).get('sslmode')
    if sslmode:
        config['OPTIONS'] = {'sslmode': sslmode[0]}
    return config

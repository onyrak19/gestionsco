# ============================================================================
# Gestion Scolaire : une seule image Docker (interface React + API Django)
# Construite par Render à partir de ce fichier (voir render.yaml).
# ============================================================================

# ---- Étape 1 : compilation de l'interface React ----------------------------
FROM node:24-slim AS interface
WORKDIR /interface
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/public ./public
COPY frontend/src ./src
# CI=false : de simples avertissements ne doivent pas faire échouer la compilation
ENV CI=false GENERATE_SOURCEMAP=false
RUN npm run build

# ---- Étape 2 : serveur Django ---------------------------------------------
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Même disposition de dossiers que sur votre PC : /app/backend et /app/frontend/build
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install -r requirements.txt

COPY backend/ ./
COPY --from=interface /interface/build /app/frontend/build

# Fichiers statiques de /admin/ (la clé ci-dessous ne sert qu'à cette commande)
RUN DJANGO_DEBUG=False DJANGO_SECRET_KEY=cle-temporaire-de-compilation \
    python manage.py collectstatic --noinput

# Utilisateur sans droits particuliers ; media/ = photos et pièces jointes
RUN useradd --create-home appuser \
    && mkdir -p /app/backend/media \
    && chown -R appuser:appuser /app/backend/media
USER appuser

# Au démarrage : migrations -> compte administrateur -> serveur.
# Render fournit le port dans la variable PORT (10000 par défaut).
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py creer_admin && exec gunicorn gestion_scolaire.wsgi:application --bind 0.0.0.0:${PORT:-10000} --workers 1 --threads 4 --timeout 120 --access-logfile -"]

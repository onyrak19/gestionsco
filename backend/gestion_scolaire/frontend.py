"""Sert l'interface React compilée (frontend/build) depuis Django.

Ainsi un seul programme (python manage.py runserver 0.0.0.0:8000) suffit pour
tout le réseau local : les téléphones et les autres ordinateurs ouvrent
http://<adresse du PC>:8000 et n'ont rien à installer."""
import mimetypes
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse

from .chemins import resoudre

MESSAGE_NON_COMPILE = (
    "L'interface n'est pas encore compilée.\n"
    "Dans le dossier frontend, lancez :  npm install  puis  npm run build\n"
    "(ou utilisez lancer_reseau.py qui le fait pour vous).\n"
)


def servir_frontend(request, chemin=''):
    racine = Path(settings.FRONTEND_BUILD_DIR)
    index = racine / 'index.html'
    if not index.is_file():
        return HttpResponse(MESSAGE_NON_COMPILE, status=503, content_type='text/plain; charset=utf-8')

    fichier = resoudre(racine, chemin)
    if fichier is None:
        if '.' in Path(chemin).name:      # fichier précis introuvable (ex. /static/js/x.js)
            raise Http404()
        fichier = index                   # page de l'application (React gère l'adresse)

    type_mime = mimetypes.guess_type(str(fichier))[0] or 'application/octet-stream'
    reponse = FileResponse(open(fichier, 'rb'), content_type=type_mime)
    if fichier == index:
        reponse['Cache-Control'] = 'no-cache'
    elif chemin.startswith('static/'):    # noms de fichiers à empreinte : cache longue durée
        reponse['Cache-Control'] = 'public, max-age=31536000, immutable'
    return reponse

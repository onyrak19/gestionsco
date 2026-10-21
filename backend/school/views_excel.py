"""Écran « Import / Export » : export Excel, modèles à remplir, import avec aperçu."""
from django.http import HttpResponse
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone

from journal import services as journal

from . import excel_outils as xo
from . import export_import as ei
from .permissions import IsAdmin


def _filtres(donnees):
    try:
        return ei.Filtres.depuis(donnees)
    except ValueError as exc:
        raise ValidationError({'detail': str(exc)})


def _reponse_xlsx(octets, nom_fichier):
    reponse = HttpResponse(octets, content_type=xo.TYPE_XLSX)
    reponse['Content-Disposition'] = f'attachment; filename="{nom_fichier}"'
    return reponse


class ExportCatalogueView(APIView):
    """Jeux de données exportables et leur nombre de lignes, selon les filtres.
    GET ?annee=<id>&classes=<id>&classes=<id>&trimestre=<1-3>"""
    permission_classes = [IsAdmin]

    def get(self, request):
        brut = request.query_params.getlist('classes') + request.query_params.getlist('classes[]')
        f = _filtres({
            'annee': request.query_params.get('annee'),
            'classes': [c for element in brut for c in element.split(',') if c],   # 1&classes=2, 1,2 ou classes[]
            'trimestre': request.query_params.get('trimestre'),
        })
        return Response({'jeux': ei.catalogue(f)})


class ExportView(APIView):
    """Corps : {jeux: ['eleves', ...] | 'tous', annee, classes: [ids], trimestre}
    Retourne un classeur Excel (.xlsx)."""
    permission_classes = [IsAdmin]

    def post(self, request):
        data = request.data
        f = _filtres(data)
        jeux = data.get('jeux')
        if jeux == 'tous':
            jeux = list(ei.JEUX)
        if not isinstance(jeux, list) or not jeux:
            raise ValidationError({'jeux': "Choisissez au moins un jeu de données (ou « tous »)."})
        try:
            octets, comptes = ei.construire_export(jeux, f, journal.nom_complet(request.user))
        except ValueError as exc:
            raise ValidationError({'jeux': str(exc)})
        total = sum(nb for _nom, nb, _desc in comptes)
        journal.enregistrer(
            request, 'export', 'impression',
            f"{journal.acteur(request.user)} a exporté vers Excel : "
            + ', '.join(f"{nom} ({nb})" for nom, nb, _d in comptes)
            + f" — {total} ligne(s) ; filtres : {f.resume()}.",
        )
        return _reponse_xlsx(octets, f"export-gestion-scolaire-{timezone.localdate():%Y-%m-%d}.xlsx")


class ImportJeuxView(APIView):
    """Types de données importables, avec leurs colonnes (pour l'écran d'import)."""
    permission_classes = [IsAdmin]

    def get(self, request):
        return Response({'jeux': [{
            'cle': cle,
            'libelle': ei.JEUX[cle].libelle,
            'resume': ei.MODELES[cle]['resume'],
            'notes': ei.MODELES[cle]['notes'],
            'colonnes': [{'titre': t, 'obligatoire': o, 'aide': a, 'exemple': e}
                         for t, o, a, e in ei.MODELES[cle]['colonnes']],
        } for cle in ei.JEUX_IMPORTABLES]})


class ImportModeleView(APIView):
    """Classeur Excel vide à remplir pour un type de données."""
    permission_classes = [IsAdmin]

    def get(self, request, cle):
        if cle not in ei.JEUX_IMPORTABLES:
            raise ValidationError({'detail': "Ce type de données ne peut pas être importé."})
        return _reponse_xlsx(ei.construire_modele(cle), f"modele-import-{cle}.xlsx")


class ImportView(APIView):
    """Importe un fichier Excel. Multipart : jeu, fichier, apercu ('true' = vérifier sans rien
    enregistrer), ignorer_erreurs ('true' = importer les lignes valides malgré les erreurs)."""
    permission_classes = [IsAdmin]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        cle = request.data.get('jeu')
        if cle not in ei.JEUX_IMPORTABLES:
            raise ValidationError({'jeu': "Choisissez le type de données à importer."})
        fichier = request.FILES.get('fichier')
        if fichier is None:
            raise ValidationError({'fichier': "Choisissez un fichier Excel (.xlsx)."})
        if not fichier.name.lower().endswith('.xlsx'):
            raise ValidationError({'fichier': "Le fichier doit être un classeur Excel au format .xlsx."})
        try:
            entetes, lignes = xo.lire_classeur(fichier.read(xo.TAILLE_MAX_FICHIER + 1),
                                               feuille_attendue=ei.JEUX[cle].libelle)
            apercu = str(request.data.get('apercu', 'true')).lower() != 'false'
            ignorer = str(request.data.get('ignorer_erreurs', 'false')).lower() == 'true'
            rapport = ei.importer(cle, entetes, lignes, request.user, appliquer=not apercu, ignorer_erreurs=ignorer)
        except ValueError as exc:
            raise ValidationError({'fichier': str(exc)})

        if rapport.applique and (rapport.crees or rapport.mis_a_jour):
            journal.enregistrer(
                request, 'import', 'creation',
                f"{journal.acteur(request.user)} a importé « {fichier.name} » ({ei.JEUX[cle].libelle}) : "
                f"{rapport.crees} créé(s), {rapport.mis_a_jour} mis à jour, {rapport.ignores} ignoré(s)"
                + (f", {len(rapport.erreurs)} ligne(s) refusée(s)" if rapport.erreurs else '') + '.',
            )
        donnees = rapport.en_dict()
        donnees.update({'jeu': cle, 'apercu': apercu})
        return Response(donnees)

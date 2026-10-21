from datetime import date, datetime, time, timedelta

from django.db.models import Q
from django.utils import timezone
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdminRole

from .models import Activite
from .serializers import ActiviteSerializer


class PaginationJournal(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


def _date_param(request, nom):
    valeur = request.query_params.get(nom)
    if not valeur:
        return None
    try:
        return date.fromisoformat(valeur)
    except ValueError:
        raise ValidationError({nom: 'Date invalide (format AAAA-MM-JJ).'})


def _debut_du_jour(jour):
    return timezone.make_aware(datetime.combine(jour, time.min))


class JournalListView(generics.ListAPIView):
    """Journal d'activité (administrateur seulement), du plus récent au plus ancien.

    Filtres : ?q= (texte libre) &utilisateur=<id> &categorie= &action= &annee=<libellé>
    &date_debut=AAAA-MM-JJ &date_fin=AAAA-MM-JJ &page= &page_size="""
    permission_classes = [IsAdminRole]
    serializer_class = ActiviteSerializer
    pagination_class = PaginationJournal

    def get_queryset(self):
        qs = Activite.objects.all()
        p = self.request.query_params

        utilisateur = p.get('utilisateur')
        if utilisateur:
            try:
                qs = qs.filter(utilisateur_id=int(utilisateur))
            except ValueError:
                raise ValidationError({'utilisateur': 'Doit être un nombre entier.'})
        if p.get('categorie'):
            qs = qs.filter(categorie=p['categorie'])
        if p.get('action'):
            qs = qs.filter(action=p['action'])
        if p.get('annee'):
            qs = qs.filter(annee=p['annee'])

        debut, fin = _date_param(self.request, 'date_debut'), _date_param(self.request, 'date_fin')
        if debut:
            qs = qs.filter(date__gte=_debut_du_jour(debut))
        if fin:
            qs = qs.filter(date__lt=_debut_du_jour(fin + timedelta(days=1)))

        q = (p.get('q') or '').strip()
        if q:
            qs = qs.filter(
                Q(description__icontains=q) | Q(utilisateur_nom__icontains=q)
                | Q(eleve__icontains=q) | Q(classe__icontains=q) | Q(matiere__icontains=q)
            )
        return qs


class JournalFiltresView(APIView):
    """Valeurs proposées dans les filtres de la fenêtre du journal."""
    permission_classes = [IsAdminRole]

    def get(self, request):
        utilisateurs = (
            Activite.objects.filter(utilisateur__isnull=False)
            .values('utilisateur_id', 'utilisateur_nom').distinct().order_by('utilisateur_nom')
        )
        # un même utilisateur renommé peut apparaître deux fois : on garde la dernière graphie
        vus = {}
        for u in utilisateurs:
            vus[u['utilisateur_id']] = u['utilisateur_nom']
        annees = (
            Activite.objects.exclude(annee='').values_list('annee', flat=True)
            .distinct().order_by('-annee')
        )
        return Response({
            'utilisateurs': [{'id': i, 'nom': n} for i, n in vus.items()],
            'categories': [{'value': v, 'label': l} for v, l in Activite.CATEGORIES],
            'actions': [{'value': v, 'label': l} for v, l in Activite.ACTIONS],
            'annees': list(annees),
        })

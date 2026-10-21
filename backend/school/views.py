from datetime import date, timedelta

from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Prefetch, Q
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from journal import services as journal

from . import pdf
from .calculs import (
    ConfigResolver, appreciation, cloturer_annee, resultats_classe,
)
from .models import (
    AnneeScolaire, Classe, ConfigMatiere, Matiere, Eleve, Etablissement,
    Inscription, Affectation, Note, PieceJointe, arrondi,
)
from .fichiers import type_mime_de
from .niveaux import NIVEAUX, NIVEAUX_AVEC_SERIE, SERIES
from .permissions import IsAdmin, IsEnseignantOrAdmin, user_is_admin
from .serializers import (
    AnneeScolaireSerializer, ClasseSerializer, MatiereSerializer,
    EleveSerializer, InscriptionSerializer, AffectationSerializer,
    NoteSerializer, NoteUpsertSerializer, EtablissementSerializer,
    ConfigEcritureSerializer, DecisionSerializer, ClotureSerializer,
    PieceJointeSerializer, creer_pieces, lire_pieces_envoyees,
)


# ---------- Outils ----------
def int_param(request, nom):
    """Lit un paramètre d'URL entier (?classe=3). Retourne None s'il est absent,
    et une erreur 400 (au lieu d'une erreur 500) s'il n'est pas un entier."""
    valeur = request.query_params.get(nom)
    if valeur in (None, ''):
        return None
    try:
        return int(valeur)
    except (TypeError, ValueError):
        raise ValidationError({nom: 'Doit être un nombre entier.'})


def entier(valeur, nom):
    try:
        return int(valeur)
    except (TypeError, ValueError):
        raise ValidationError({nom: 'Doit être un nombre entier.'})


def lecture_authentifiee_ecriture_admin(request):
    """Lecture : tout utilisateur connecté. Écriture : administrateur."""
    if request.method == 'POST':
        return [IsAdmin()]
    return [permissions.IsAuthenticated()]


def classes_de_l_enseignant(user):
    return Affectation.objects.filter(enseignant=user)


TRIMESTRES_LIBELLES = {1: '1er trimestre', 2: '2e trimestre', 3: '3e trimestre'}


class JournalMixin:
    """Inscrit dans le journal d'activité les créations, modifications et
    suppressions faites par les vues génériques."""
    journal_categorie = ''
    journal_champs = {}          # {champ: libellé affiché} suivis lors d'une modification

    def journal_libelle(self, obj):
        return str(obj)

    def journal_contexte(self, obj):
        return {}

    def journal_detail_creation(self, obj):
        return ''

    def journal_valeurs(self, obj):
        return {champ: getattr(obj, champ, None) for champ in self.journal_champs}

    def journal_extra(self, avant, apres):
        return ''

    def _ecrire(self, action, texte, obj, contexte=None):
        journal.enregistrer(
            self.request, self.journal_categorie, action, texte,
            cible_id=getattr(obj, 'pk', None),
            **(contexte if contexte is not None else self.journal_contexte(obj)),
        )

    def perform_create(self, serializer):
        obj = serializer.save()
        detail = self.journal_detail_creation(obj)
        self._ecrire('creation', f"{journal.acteur(self.request.user)} a créé "
                                 f"{self.journal_libelle(obj)}{detail}.", obj)
        return obj

    def perform_update(self, serializer):
        avant = self.journal_valeurs(serializer.instance)
        obj = serializer.save()
        apres = self.journal_valeurs(obj)
        changements = ' ; '.join(x for x in (
            journal.difference(avant, apres, self.journal_champs),
            self.journal_extra(avant, apres),
        ) if x)
        if changements:
            self._ecrire('modification', f"{journal.acteur(self.request.user)} a modifié "
                                         f"{self.journal_libelle(obj)} : {changements}.", obj)
        return obj

    def perform_destroy(self, instance):
        libelle, contexte, pk = self.journal_libelle(instance), self.journal_contexte(instance), instance.pk
        instance.delete()
        journal.enregistrer(
            self.request, self.journal_categorie, 'suppression',
            f"{journal.acteur(self.request.user)} a supprimé {libelle}.", cible_id=pk, **contexte,
        )


# ---------- ÉTABLISSEMENT / RÉFÉRENTIEL ----------
class EtablissementView(JournalMixin, generics.RetrieveUpdateAPIView):
    serializer_class = EtablissementSerializer
    journal_categorie = 'etablissement'
    journal_champs = {'nom': 'nom', 'directeur': 'directeur', 'adresse': 'adresse',
                      'ville': 'ville', 'telephone': 'téléphone', 'email': 'email'}

    def journal_libelle(self, obj):
        return "les informations de l'établissement"

    def get_object(self):
        return Etablissement.obtenir()

    def get_permissions(self):
        if self.request.method == 'GET':
            return [permissions.IsAuthenticated()]
        return [IsAdmin()]


class NiveauxView(APIView):
    """Listes utilisées par les formulaires (niveaux, séries proposées)."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response({
            'niveaux': NIVEAUX,
            'niveaux_avec_serie': list(NIVEAUX_AVEC_SERIE),
            'series': SERIES,
        })


# ---------- ANNÉE SCOLAIRE ----------
class AnneeScolaireListView(JournalMixin, generics.ListCreateAPIView):
    queryset = AnneeScolaire.objects.all()
    serializer_class = AnneeScolaireSerializer
    journal_categorie = 'annee'

    def journal_libelle(self, obj):
        return f"l'année scolaire {obj.libelle}"

    def journal_contexte(self, obj):
        return {'annee': obj.libelle}

    def get_permissions(self):
        return lecture_authentifiee_ecriture_admin(self.request)


class AnneeScolaireDetailView(JournalMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = AnneeScolaire.objects.all()
    serializer_class = AnneeScolaireSerializer
    permission_classes = [IsAdmin]
    journal_categorie = 'annee'
    journal_champs = {'libelle': 'libellé', 'date_debut': 'début', 'date_fin': 'fin',
                      'active': 'année en cours'}

    def journal_libelle(self, obj):
        return f"l'année scolaire {obj.libelle}"

    def journal_contexte(self, obj):
        return {'annee': obj.libelle}


class AnneeActiveView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        a = AnneeScolaire.objects.filter(active=True).first()
        if not a:
            return Response({'error': 'Aucune année active'}, status=404)
        return Response(AnneeScolaireSerializer(a).data)


class AnneeCloturerView(generics.GenericAPIView):
    """Clôture une année : exige le mot de passe de l'administrateur connecté.
    Calcule la moyenne annuelle et la décision (passant / redoublant) de chaque élève."""
    permission_classes = [IsAdmin]
    serializer_class = ClotureSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'   # anti force brute du mot de passe

    def post(self, request, pk):
        annee = get_object_or_404(AnneeScolaire, pk=pk)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not request.user.check_password(serializer.validated_data['password']):
            raise PermissionDenied('Mot de passe administrateur incorrect.')
        if annee.cloturee:
            raise ValidationError('Cette année est déjà clôturée.')
        resume = cloturer_annee(annee)
        journal.enregistrer(
            request, 'annee', 'cloture',
            f"{journal.acteur(request.user)} a clôturé l'année scolaire {annee.libelle} : "
            f"{resume['passant']} passant(s), {resume['redoublant']} redoublant(s), "
            f"{resume['non_decide']} à décider.",
            annee=annee.libelle, cible_id=annee.pk,
        )
        return Response({'annee': AnneeScolaireSerializer(annee).data, 'resume': resume})


# ---------- CLASSE ----------
class ClasseJournalMixin(JournalMixin):
    journal_categorie = 'classe'
    journal_champs = {'nom': 'nom', 'niveau': 'niveau', 'serie': 'série', 'numero': 'numéro'}

    def journal_libelle(self, obj):
        return f"la classe {obj.nom} ({obj.annee_scolaire.libelle})"

    def journal_contexte(self, obj):
        return {'annee': obj.annee_scolaire.libelle, 'classe': obj.nom}


class ClasseListView(ClasseJournalMixin, generics.ListCreateAPIView):
    serializer_class = ClasseSerializer

    def get_queryset(self):
        qs = Classe.objects.select_related('annee_scolaire').annotate(nb_eleves=Count('inscriptions'))
        annee_id = int_param(self.request, 'annee')
        if annee_id:
            qs = qs.filter(annee_scolaire_id=annee_id)
        return qs

    def get_serializer_context(self):
        contexte = super().get_serializer_context()
        contexte['resolver'] = ConfigResolver()
        return contexte

    def get_permissions(self):
        return lecture_authentifiee_ecriture_admin(self.request)


class ClasseDetailView(ClasseJournalMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Classe.objects.select_related('annee_scolaire').annotate(nb_eleves=Count('inscriptions'))
    serializer_class = ClasseSerializer
    permission_classes = [IsAdmin]

    def get_serializer_context(self):
        contexte = super().get_serializer_context()
        contexte['resolver'] = ConfigResolver()
        return contexte


class ConfigMatieresView(APIView):
    """Matières enseignées + coefficients d'un niveau (et d'une série).

    La configuration s'applique à TOUTES les classes de même niveau et même
    série pour l'année scolaire (ex. toutes les 5ème ; toutes les Premières S).
    GET ?classe=<id> | PUT {classe, matieres: [{matiere, coefficient}]}"""
    permission_classes = [IsAdmin]

    @staticmethod
    def _clef(classe):
        if not classe.niveau:
            raise ValidationError(
                "Cette classe n'a pas de niveau : modifiez-la pour choisir son niveau "
                "avant de configurer ses matières.")
        return classe.annee_scolaire, classe.niveau, classe.serie

    def _reponse(self, classe):
        annee, niveau, serie = self._clef(classe)
        propres = ConfigMatiere.objects.filter(annee_scolaire=annee, niveau=niveau, serie=serie)
        propose = False
        config = {c.matiere_id: c.coefficient for c in propres}
        if not config:
            # Pas encore configuré cette année : on propose celle de l'année précédente
            ancienne = ConfigMatiere.objects.filter(
                niveau=niveau, serie=serie, annee_scolaire__date_debut__lt=annee.date_debut
            ).order_by('-annee_scolaire__date_debut').first()
            if ancienne:
                config = {c.matiere_id: c.coefficient for c in ConfigMatiere.objects.filter(
                    annee_scolaire=ancienne.annee_scolaire, niveau=niveau, serie=serie)}
                propose = True
        classes = Classe.objects.filter(annee_scolaire=annee, niveau=niveau, serie=serie)
        return Response({
            'classe': classe.id, 'annee': annee.libelle, 'annee_cloturee': annee.cloturee,
            'niveau': niveau, 'serie': serie,
            'configuree': bool(propres), 'propose': propose,
            'classes': [{'id': c.id, 'nom': c.nom} for c in classes],
            'matieres': [{
                'matiere': m.id, 'nom': m.nom, 'code': m.code,
                'enseignee': m.id in config,
                'coefficient': config.get(m.id, m.coefficient),
            } for m in Matiere.objects.all()],
        })

    def get(self, request):
        classe_id = int_param(request, 'classe')
        if not classe_id:
            raise ValidationError({'classe': 'Paramètre obligatoire.'})
        return self._reponse(get_object_or_404(Classe.objects.select_related('annee_scolaire'), pk=classe_id))

    @transaction.atomic
    def put(self, request):
        serializer = ConfigEcritureSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        classe = serializer.validated_data['classe']
        annee, niveau, serie = self._clef(classe)
        if annee.cloturee:
            raise ValidationError(f"L'année {annee.libelle} est clôturée : configuration figée.")

        voulues = {e['matiere'].id: e['coefficient'] for e in serializer.validated_data['matieres']}
        ConfigMatiere.objects.filter(
            annee_scolaire=annee, niveau=niveau, serie=serie
        ).exclude(matiere_id__in=voulues.keys()).delete()
        for matiere_id, coef in voulues.items():
            ConfigMatiere.objects.update_or_create(
                annee_scolaire=annee, niveau=niveau, serie=serie, matiere_id=matiere_id,
                defaults={'coefficient': coef},
            )
        titre = f"{niveau} {serie}".strip()
        journal.enregistrer(
            request, 'classe', 'modification',
            f"{journal.acteur(request.user)} a configuré les matières de {titre} "
            f"({annee.libelle}) : {len(voulues)} matière(s) enseignée(s), coefficients enregistrés.",
            annee=annee.libelle, classe=classe.nom, cible_id=classe.pk,
        )
        return self._reponse(classe)


class ReleveClasseView(APIView):
    """Relevé de notes d'une classe (tous les élèves × toutes les matières).
    ?trimestre=1|2|3|annuel  &ordre=alpha|numero|rang"""
    permission_classes = [IsAdmin]

    def get(self, request, pk):
        classe = get_object_or_404(Classe.objects.select_related('annee_scolaire'), pk=pk)
        trim = request.query_params.get('trimestre', '1')
        if trim not in ('1', '2', '3', 'annuel'):
            raise ValidationError({'trimestre': 'Valeurs possibles : 1, 2, 3, annuel.'})
        cle = 'annuelle' if trim == 'annuel' else int(trim)

        donnees = resultats_classe(classe)
        lignes = []
        for r in donnees['resultats'].values():
            ins = r['inscription']
            notes = {}
            for m, _coef in donnees['matieres']:
                if trim == 'annuel':
                    vals = [n.moyenne_matiere for t in (1, 2, 3)
                            for n in [r['notes'][t].get(m.id)] if n and n.moyenne_matiere is not None]
                    notes[m.id] = arrondi(sum(vals) / len(vals)) if vals else None
                else:
                    n = r['notes'][cle].get(m.id)
                    notes[m.id] = n.moyenne_matiere if n else None
            lignes.append({
                'inscription': ins.id, 'numero': ins.numero,
                'nom': ins.eleve.nom, 'prenom': ins.eleve.prenom, 'matricule': ins.eleve.matricule,
                'notes': notes,
                'generale': r['annuelle'] if trim == 'annuel' else r['generales'].get(cle),
                'rang': r['rangs'].get(cle), 'decision': ins.decision,
            })
        ordre = request.query_params.get('ordre', 'alpha')
        if ordre == 'numero':
            lignes.sort(key=lambda l: (l['numero'] or 0))
        elif ordre == 'rang':
            lignes.sort(key=lambda l: (l['rang'] is None, l['rang'] or 0, l['nom'].lower()))
        else:
            lignes.sort(key=lambda l: (l['nom'].lower(), l['prenom'].lower()))

        return Response({
            'classe': {'id': classe.id, 'nom': classe.nom, 'annee': classe.annee_scolaire.libelle},
            'trimestre': trim,
            'matieres': [{'id': m.id, 'nom': m.nom, 'code': m.code, 'coefficient': coef}
                         for m, coef in donnees['matieres']],
            'eleves': lignes,
            'stats': donnees['stats'][cle],
        })


# ---------- MATIÈRE ----------
class MatiereJournalMixin(JournalMixin):
    journal_categorie = 'matiere'
    journal_champs = {'nom': 'nom', 'coefficient': 'coefficient par défaut'}

    def journal_libelle(self, obj):
        return f"la matière {obj.nom}"

    def journal_contexte(self, obj):
        return {'matiere': obj.nom}

    def journal_detail_creation(self, obj):
        return f" (coefficient par défaut {obj.coefficient})"


class MatiereListView(MatiereJournalMixin, generics.ListCreateAPIView):
    queryset = Matiere.objects.all()
    serializer_class = MatiereSerializer

    def get_permissions(self):
        return lecture_authentifiee_ecriture_admin(self.request)


class MatiereDetailView(MatiereJournalMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Matiere.objects.all()
    serializer_class = MatiereSerializer
    permission_classes = [IsAdmin]


# ---------- ÉLÈVE ----------
class EleveJournalMixin(JournalMixin):
    journal_categorie = 'eleve'
    journal_champs = {'nom': 'nom', 'prenom': 'prénom', 'date_naissance': 'date de naissance',
                      'sexe': 'sexe', 'actif': 'actif',
                      'parent_nom': 'parent / tuteur', 'parent_mobile': 'mobile du parent',
                      'parent2_nom': 'parent / tuteur 2', 'parent2_mobile': 'mobile du parent 2'}

    def journal_libelle(self, obj):
        return f"l'élève {obj.nom_complet}"

    def journal_contexte(self, obj):
        return {'eleve': obj.nom_complet}

    def journal_valeurs(self, obj):
        valeurs = super().journal_valeurs(obj)
        valeurs['photo_token'] = obj.photo_token
        return valeurs

    def journal_extra(self, avant, apres):
        if avant['photo_token'] == apres['photo_token']:
            return ''
        if not apres['photo_token']:
            return 'photo retirée'
        return 'photo ajoutée' if not avant['photo_token'] else 'photo remplacée'

    def journal_detail_creation(self, obj):
        return ' (avec photo)' if obj.photo else ''


class EleveListView(EleveJournalMixin, generics.ListCreateAPIView):
    serializer_class = EleveSerializer
    permission_classes = [IsAdmin]

    def get_queryset(self):
        qs = Eleve.objects.prefetch_related(Prefetch(
            'inscriptions',
            queryset=Inscription.objects.select_related('classe', 'annee_scolaire')
            .order_by('-annee_scolaire__date_debut'),
            to_attr='insc_all',
        ))
        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(
                Q(nom__icontains=search)
                | Q(prenom__icontains=search)
                | Q(matricule__icontains=search)
            )
        if self.request.query_params.get('ordre') == 'matricule':
            return qs.order_by('matricule', 'nom')
        return qs.order_by('nom', 'prenom')


class EleveDetailView(EleveJournalMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Eleve.objects.all()
    serializer_class = EleveSerializer
    permission_classes = [IsAdmin]


class EleveDossierView(APIView):
    """Dossier d'un élève : identité + parcours (classe, décision, moyennes par année)."""
    permission_classes = [IsAdmin]

    def get(self, request, pk):
        eleve = get_object_or_404(Eleve, pk=pk)
        resolver, cache, parcours = ConfigResolver(), {}, []
        inscriptions = eleve.inscriptions.select_related(
            'classe__annee_scolaire', 'annee_scolaire'
        ).prefetch_related(
            Prefetch('pieces', queryset=PieceJointe.objects.select_related('ajoute_par'))
        ).order_by('-annee_scolaire__date_debut')
        for ins in inscriptions:
            if ins.classe_id not in cache:
                cache[ins.classe_id] = resultats_classe(ins.classe, resolver)
            donnees = cache[ins.classe_id]
            r = donnees['resultats'][ins.id]
            cloturee = ins.annee_scolaire.cloturee
            parcours.append({
                'inscription': ins.id,
                'annee_id': ins.annee_scolaire_id, 'annee': ins.annee_scolaire.libelle,
                'annee_cloturee': cloturee,
                'classe_id': ins.classe_id, 'classe': ins.classe.nom,
                'niveau': ins.classe.niveau, 'serie': ins.classe.serie,
                'numero': ins.numero, 'decision': ins.decision,
                'moyennes': {f"T{t}": r['generales'].get(t) for t in (1, 2, 3)},
                'moyenne_annuelle': (float(ins.moyenne_annuelle)
                                     if cloturee and ins.moyenne_annuelle is not None else r['annuelle']),
                'rang_annuel': r['rangs'].get('annuelle'), 'effectif': donnees['effectif'],
                'pieces': PieceJointeSerializer(ins.pieces.all(), many=True).data,
            })
        return Response({
            'eleve': EleveSerializer(eleve).data,
            'parcours': parcours,
            'statut': parcours[0]['decision'] if parcours else None,
        })


# ---------- INSCRIPTION ----------
class InscriptionListView(generics.ListCreateAPIView):
    """Administrateur : toutes les inscriptions (lecture + création).
    Enseignant : lecture seule, uniquement les classes où il est affecté.
    ?classe= &annee= &ordre=alpha|numero

    La création accepte du JSON, ou du multipart avec des pièces jointes
    facultatives (champs « fichiers » et « libelles »)."""
    serializer_class = InscriptionSerializer

    def perform_create(self, serializer):
        ins = serializer.save()
        nb = ins.pieces.count()
        journal.enregistrer(
            self.request, 'inscription', 'creation',
            f"{journal.acteur(self.request.user)} a inscrit {ins.eleve.nom_complet} en "
            f"{ins.classe.nom} ({ins.annee_scolaire.libelle}) — n° {ins.numero}, matricule "
            f"{ins.eleve.matricule}" + (f", {nb} pièce(s) jointe(s)" if nb else '') + '.',
            annee=ins.annee_scolaire.libelle, classe=ins.classe.nom,
            eleve=ins.eleve.nom_complet, cible_id=ins.pk,
        )

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAdmin()]
        return [IsEnseignantOrAdmin()]

    def get_queryset(self):
        qs = Inscription.objects.select_related(
            'eleve', 'classe__annee_scolaire', 'annee_scolaire'
        ).prefetch_related(
            Prefetch('pieces', queryset=PieceJointe.objects.select_related('ajoute_par'))
        )
        classe_id = int_param(self.request, 'classe')
        annee_id = int_param(self.request, 'annee')
        if classe_id:
            qs = qs.filter(classe_id=classe_id)
        if annee_id:
            qs = qs.filter(annee_scolaire_id=annee_id)

        if not user_is_admin(self.request.user):
            qs = qs.filter(Exists(
                Affectation.objects.filter(
                    enseignant=self.request.user, classe_id=OuterRef('classe_id')
                )
            ))
        if self.request.query_params.get('ordre') == 'numero':
            return qs.order_by('classe__nom', 'numero')
        return qs.order_by('classe__nom', 'eleve__nom', 'eleve__prenom')


class InscriptionDetailView(generics.RetrieveDestroyAPIView):
    queryset = Inscription.objects.select_related('eleve', 'classe__annee_scolaire')
    serializer_class = InscriptionSerializer
    permission_classes = [IsAdmin]

    def perform_destroy(self, instance):
        eleve, classe, annee = instance.eleve.nom_complet, instance.classe.nom, instance.annee_scolaire.libelle
        pk = instance.pk
        instance.delete()
        journal.enregistrer(
            self.request, 'inscription', 'suppression',
            f"{journal.acteur(self.request.user)} a supprimé l'inscription de {eleve} en "
            f"{classe} ({annee}) : ses notes et pièces jointes de l'année sont supprimées.",
            annee=annee, classe=classe, eleve=eleve, cible_id=pk,
        )


class InscriptionDecisionView(generics.GenericAPIView):
    """Corrige à la main la décision (passant / redoublant) d'une année clôturée."""
    permission_classes = [IsAdmin]
    serializer_class = DecisionSerializer

    def patch(self, request, pk):
        ins = get_object_or_404(
            Inscription.objects.select_related('annee_scolaire', 'classe', 'eleve'), pk=pk)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not ins.annee_scolaire.cloturee:
            raise ValidationError("La décision est prise automatiquement à la clôture de l'année.")
        ancienne = ins.decision
        ins.decision = serializer.validated_data['decision']
        ins.save(update_fields=['decision'])
        journal.enregistrer(
            request, 'inscription', 'modification',
            f"{journal.acteur(request.user)} a corrigé la décision de {ins.eleve.nom_complet} "
            f"({ins.classe.nom}, {ins.annee_scolaire.libelle}) : {ancienne} → {ins.decision}.",
            annee=ins.annee_scolaire.libelle, classe=ins.classe.nom,
            eleve=ins.eleve.nom_complet, cible_id=ins.pk,
        )
        return Response(InscriptionSerializer(ins).data)


# ---------- AFFECTATION ----------
class AffectationJournalMixin(JournalMixin):
    journal_categorie = 'affectation'
    journal_champs = {'enseignant': 'enseignant', 'matiere': 'matière', 'classe': 'classe'}

    def journal_valeurs(self, obj):
        return {'enseignant': obj.enseignant.get_full_name() or obj.enseignant.username,
                'matiere': obj.matiere.nom, 'classe': obj.classe.nom}

    def journal_libelle(self, obj):
        ens = obj.enseignant.get_full_name() or obj.enseignant.username
        return f"l'affectation de {ens} à {obj.matiere.nom} en {obj.classe.nom} ({obj.annee_scolaire.libelle})"

    def journal_contexte(self, obj):
        return {'annee': obj.annee_scolaire.libelle, 'classe': obj.classe.nom, 'matiere': obj.matiere.nom}


class AffectationListView(AffectationJournalMixin, generics.ListCreateAPIView):
    """Une matière n'a qu'un seul enseignant par classe (refusé sinon)."""
    serializer_class = AffectationSerializer
    permission_classes = [IsAdmin]

    def get_queryset(self):
        qs = Affectation.objects.select_related(
            'enseignant', 'matiere', 'classe', 'annee_scolaire'
        )
        ens_id = int_param(self.request, 'enseignant')
        annee_id = int_param(self.request, 'annee')
        classe_id = int_param(self.request, 'classe')
        if ens_id:
            qs = qs.filter(enseignant_id=ens_id)
        if annee_id:
            qs = qs.filter(annee_scolaire_id=annee_id)
        if classe_id:
            qs = qs.filter(classe_id=classe_id)
        return qs


class AffectationDetailView(AffectationJournalMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Affectation.objects.select_related(
        'enseignant', 'matiere', 'classe', 'annee_scolaire'
    )
    serializer_class = AffectationSerializer
    permission_classes = [IsAdmin]


class MesAffectationsView(generics.ListAPIView):
    """Affectations de l'enseignant connecté.
    Par défaut : année scolaire active (les affectations sont à redéfinir chaque
    année). ?annee=<id> pour une autre année, ?annee=all pour toutes."""
    serializer_class = AffectationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Affectation.objects.filter(
            enseignant=self.request.user
        ).select_related('enseignant', 'matiere', 'classe', 'annee_scolaire')

        annee = self.request.query_params.get('annee')
        if annee == 'all':
            return qs
        if annee:
            return qs.filter(annee_scolaire_id=int_param(self.request, 'annee'))
        active = AnneeScolaire.objects.filter(active=True).first()
        return qs.filter(annee_scolaire=active) if active else qs.none()


# ---------- NOTES ----------
class NoteListView(generics.ListAPIView):
    """Lecture des notes. La création/modification passe uniquement par
    /notes/upsert/ (qui contrôle l'affectation de l'enseignant)."""
    serializer_class = NoteSerializer
    permission_classes = [IsEnseignantOrAdmin]

    def get_queryset(self):
        qs = Note.objects.select_related(
            'inscription__eleve', 'matiere', 'inscription__classe'
        )
        classe_id = int_param(self.request, 'classe')
        matiere_id = int_param(self.request, 'matiere')
        trimestre = int_param(self.request, 'trimestre')
        if classe_id:
            qs = qs.filter(inscription__classe_id=classe_id)
        if matiere_id:
            qs = qs.filter(matiere_id=matiere_id)
        if trimestre:
            qs = qs.filter(trimestre=trimestre)

        if not user_is_admin(self.request.user):
            # Un enseignant ne voit que les notes de ses (classe, matière).
            qs = qs.filter(Exists(
                Affectation.objects.filter(
                    enseignant=self.request.user,
                    classe_id=OuterRef('inscription__classe_id'),
                    matiere_id=OuterRef('matiere_id'),
                )
            ))
        return qs


class NoteUpsertView(generics.GenericAPIView):
    """Crée ou met à jour la note d'un élève (inscription) pour une matière
    et un trimestre. Les 4 valeurs (j1, j2, j3, examen) sont remplacées ;
    une valeur vide efface la note. 0 est une note valide.
    L'administrateur peut saisir pour n'importe quelle classe."""
    permission_classes = [IsEnseignantOrAdmin]
    serializer_class = NoteUpsertSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        inscription = data['inscription']
        matiere = data['matiere']
        classe = inscription.classe

        if classe.annee_scolaire.cloturee:
            raise PermissionDenied(
                "Cette année scolaire est clôturée : les notes ne sont plus modifiables."
            )

        if not user_is_admin(request.user):
            autorise = Affectation.objects.filter(
                enseignant=request.user, classe=classe, matiere=matiere,
            ).exists()
            if not autorise:
                raise PermissionDenied("Vous n'êtes pas affecté à cette classe/matière.")

        if ConfigResolver().coefficient(matiere, classe) is None:
            raise ValidationError({
                'matiere': f"{matiere.nom} n'est pas enseignée en {classe.nom} "
                           f"(voir la configuration des matières de la classe)."
            })

        champs = ('j1', 'j2', 'j3', 'examen')
        ancienne = Note.objects.filter(
            inscription=inscription, matiere=matiere, trimestre=data['trimestre']).first()
        avant = {c: getattr(ancienne, c) for c in champs} if ancienne else None

        note, _ = Note.objects.update_or_create(
            inscription=inscription,
            matiere=matiere,
            trimestre=data['trimestre'],
            defaults={
                'j1': data.get('j1'),
                'j2': data.get('j2'),
                'j3': data.get('j3'),
                'examen': data.get('examen'),
                'saisi_par': request.user,
            },
        )
        note.refresh_from_db()   # les valeurs redeviennent des Decimal
        self._journaliser(request, note, avant, champs)
        return Response(NoteSerializer(note).data)

    @staticmethod
    def _journaliser(request, note, avant, champs):
        """Une ligne de journal par saisie réellement modifiée (pas de bruit si
        les valeurs sont identiques)."""
        libelles = {'j1': 'J1', 'j2': 'J2', 'j3': 'J3', 'examen': 'Examen'}
        apres = {c: getattr(note, c) for c in champs}
        ins = note.inscription
        eleve = ins.eleve.nom_complet
        cadre = (f"{note.matiere.nom} — {ins.classe.nom}, {ins.annee_scolaire.libelle}, "
                 f"{TRIMESTRES_LIBELLES[note.trimestre]}")
        if avant is None:
            saisies = ' ; '.join(
                f"{libelles[c]} = {journal.valeur_lisible(v)}" for c, v in apres.items() if v is not None)
            if not saisies:
                return
            texte = f"a saisi la note de {eleve} (n° {ins.numero}) en {cadre} : {saisies}"
        else:
            changements = journal.difference(avant, apres, libelles)
            if not changements:
                return
            texte = f"a modifié la note de {eleve} (n° {ins.numero}) en {cadre} : {changements}"
        journal.enregistrer(
            request, 'note', 'creation' if avant is None else 'modification',
            f"{journal.acteur(request.user)} {texte}.",
            annee=ins.annee_scolaire.libelle, classe=ins.classe.nom,
            matiere=note.matiere.nom, eleve=eleve, cible_id=note.pk,
        )


class MoyennesEleveView(generics.GenericAPIView):
    """Moyennes d'un élève par matière et par trimestre, et moyenne générale
    (pondérée par les coefficients configurés pour sa classe).
    ?annee=<id> ; par défaut l'année active."""
    permission_classes = [IsEnseignantOrAdmin]

    def get(self, request, eleve_id):
        eleve = get_object_or_404(Eleve, pk=eleve_id)

        annee_id = int_param(request, 'annee')
        if annee_id is None:
            active = AnneeScolaire.objects.filter(active=True).first()
            annee_id = active.id if active else None

        inscriptions = Inscription.objects.filter(eleve=eleve)
        if annee_id:
            inscriptions = inscriptions.filter(annee_scolaire_id=annee_id)

        if not user_is_admin(request.user):
            inscriptions = inscriptions.filter(Exists(
                Affectation.objects.filter(
                    enseignant=request.user, classe_id=OuterRef('classe_id')
                )
            ))
            if not inscriptions.exists():
                raise PermissionDenied("Cet élève n'est pas dans une de vos classes.")

        liste = list(inscriptions.select_related('classe__annee_scolaire', 'annee_scolaire')
                     .order_by('-annee_scolaire__date_debut'))
        if annee_id is None:
            liste = liste[:1]   # sans année : la plus récente seulement

        resolver = ConfigResolver()
        par_matiere, generales, annuelle = {}, {}, None
        for ins in liste:
            r = resultats_classe(ins.classe, resolver)['resultats'][ins.id]
            for t, notes in r['notes'].items():
                for n in notes.values():
                    par_matiere.setdefault(n.matiere.nom, {})[f"T{t}"] = n.moyenne_matiere
            generales.update({f"T{t}": g for t, g in r['generales'].items()})
            annuelle = r['annuelle']

        return Response({
            'eleve': eleve.id,
            'annee': annee_id,
            'par_matiere': par_matiere,
            'moyenne_generale': generales,
            'moyenne_annuelle': annuelle,
        })


# ---------- IMPRESSIONS PDF (administrateur) ----------
def _etablissement():
    e = Etablissement.obtenir()
    return {'nom': e.nom, 'adresse': e.adresse, 'ville': e.ville,
            'telephone': e.telephone, 'email': e.email, 'directeur': e.directeur}


def _reponse_pdf(octets, nom_fichier):
    reponse = HttpResponse(octets, content_type='application/pdf')
    reponse['Content-Disposition'] = f'inline; filename="{nom_fichier}"'
    return reponse


def _inscriptions_a_imprimer(request):
    """Élèves à imprimer : une liste d'inscriptions, ou toute une classe, ou toute une année.
    Corps JSON : {inscriptions: [..]} | {classe: id} | {annee: id}, + ordre: alpha|numero."""
    data = request.data
    qs = Inscription.objects.select_related('eleve', 'classe__annee_scolaire', 'annee_scolaire')
    if data.get('inscriptions') is not None:
        ids = data['inscriptions']
        if not isinstance(ids, list):
            raise ValidationError({'inscriptions': 'Doit être une liste.'})
        qs = qs.filter(id__in=[entier(i, 'inscriptions') for i in ids])
    elif data.get('classes') is not None:
        ids = data['classes']
        if not isinstance(ids, list):
            raise ValidationError({'classes': 'Doit être une liste.'})
        qs = qs.filter(classe_id__in=[entier(i, 'classes') for i in ids])
    elif data.get('classe'):
        qs = qs.filter(classe_id=entier(data['classe'], 'classe'))
    elif data.get('annee'):
        qs = qs.filter(annee_scolaire_id=entier(data['annee'], 'annee'))
    else:
        raise ValidationError(
            {'detail': "Indiquez les élèves à imprimer (inscriptions, classes ou annee)."})
    if data.get('ordre') == 'numero':
        qs = qs.order_by('classe__nom', 'numero')
    else:
        qs = qs.order_by('classe__nom', 'eleve__nom', 'eleve__prenom')
    liste = list(qs[:5000])
    if not liste:
        raise ValidationError({'detail': 'Aucun élève à imprimer.'})
    return liste


def _octets_photo(eleve):
    """Contenu de la photo de l'élève (None s'il n'en a pas ou si le fichier manque)."""
    if not eleve.photo:
        return None
    try:
        with eleve.photo.open('rb') as fichier:
            return fichier.read()
    except (OSError, ValueError):
        return None


def _journal_impression(request, nature, liste, complement=''):
    classes = sorted({i.classe.nom for i in liste})
    annees = sorted({i.annee_scolaire.libelle for i in liste})
    noms = ', '.join(classes[:6]) + (f" et {len(classes) - 6} autre(s)" if len(classes) > 6 else '')
    journal.enregistrer(
        request, 'impression', 'impression',
        f"{journal.acteur(request.user)} a imprimé {len(liste)} {nature}{complement} — "
        f"{len(classes)} classe(s) : {noms} ({', '.join(annees)}).",
        annee=annees[0] if len(annees) == 1 else '',
        classe=classes[0] if len(classes) == 1 else '',
    )


class PdfCartesView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request):
        liste = _inscriptions_a_imprimer(request)
        cartes = [{
            'nom': i.eleve.nom, 'prenom': i.eleve.prenom, 'matricule': i.eleve.matricule,
            'classe': i.classe.nom, 'annee': i.annee_scolaire.libelle, 'numero': i.numero,
            'date_naissance': i.eleve.date_naissance, 'photo': _octets_photo(i.eleve),
        } for i in liste]
        octets = pdf.cartes_pdf(cartes, _etablissement())
        _journal_impression(request, "carte(s) d'élève", liste)
        return _reponse_pdf(octets, 'cartes-eleves.pdf')


class PdfCertificatsView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request):
        liste = _inscriptions_a_imprimer(request)
        certificats = [{
            'nom': i.eleve.nom, 'prenom': i.eleve.prenom, 'sexe': i.eleve.sexe,
            'matricule': i.eleve.matricule, 'date_naissance': i.eleve.date_naissance,
            'classe': i.classe.nom, 'annee': i.annee_scolaire.libelle,
        } for i in liste]
        octets = pdf.certificats_pdf(certificats, _etablissement(), date.today())
        _journal_impression(request, 'certificat(s) de scolarité', liste)
        return _reponse_pdf(octets, 'certificats-scolarite.pdf')


class PdfBulletinsView(APIView):
    """Corps : {inscriptions | classes: [ids] | classe | annee, trimestre: 1|2|3, ordre}
    Avec `classes` (ou `annee`), tous les bulletins sont réunis dans un seul PDF."""
    permission_classes = [IsAdmin]

    def post(self, request):
        trimestre = entier(request.data.get('trimestre'), 'trimestre')
        if trimestre not in (1, 2, 3):
            raise ValidationError({'trimestre': 'Valeurs possibles : 1, 2, 3.'})
        liste = _inscriptions_a_imprimer(request)

        resolver, cache, bulletins = ConfigResolver(), {}, []
        for ins in liste:
            if ins.classe_id not in cache:
                cache[ins.classe_id] = resultats_classe(ins.classe, resolver)
            donnees = cache[ins.classe_id]
            r = donnees['resultats'][ins.id]

            lignes, total_points, total_coef = [], 0.0, 0
            for matiere, coef in donnees['matieres']:
                n = r['notes'][trimestre].get(matiere.id)
                moy = n.moyenne_matiere if n else None
                points = moy * coef if moy is not None else None
                if moy is not None:
                    total_points += points
                    total_coef += coef
                lignes.append({
                    'matiere': matiere.nom, 'coef': coef,
                    'j1': n.j1 if n else None, 'j2': n.j2 if n else None, 'j3': n.j3 if n else None,
                    'moy_j': n.moyenne_journaliere if n else None,
                    'examen': n.examen if n else None, 'moyenne': moy, 'points': points,
                })
            generale = r['generales'].get(trimestre)
            clot = ins.annee_scolaire.cloturee
            bulletins.append({
                'nom': ins.eleve.nom, 'prenom': ins.eleve.prenom, 'sexe': ins.eleve.sexe,
                'matricule': ins.eleve.matricule, 'date_naissance': ins.eleve.date_naissance,
                'photo': _octets_photo(ins.eleve),
                'classe': ins.classe.nom, 'numero': ins.numero,
                'annee': ins.annee_scolaire.libelle, 'effectif': donnees['effectif'],
                'trimestre': trimestre, 'lignes': lignes,
                'total_points': total_points, 'total_coef': total_coef,
                'generale': generale, 'rang': r['rangs'].get(trimestre),
                'stats': donnees['stats'][trimestre],
                'generales': r['generales'], 'annuelle': r['annuelle'],
                'appreciation': appreciation(generale),
                'decision': ins.decision if clot else None,
            })
        octets = pdf.bulletins_pdf(bulletins, _etablissement())
        _journal_impression(request, f"bulletin(s) du {TRIMESTRES_LIBELLES[trimestre]}", liste)
        return _reponse_pdf(octets, f'bulletins-T{trimestre}.pdf')


class PdfFichesAppelView(APIView):
    """Corps : {classes: [ids] | annee: id, semaine: 'AAAA-MM-JJ' (optionnel), ordre}"""
    permission_classes = [IsAdmin]

    def post(self, request):
        data = request.data
        qs = Classe.objects.select_related('annee_scolaire')
        if data.get('classes') is not None:
            if not isinstance(data['classes'], list):
                raise ValidationError({'classes': 'Doit être une liste.'})
            qs = qs.filter(id__in=[entier(i, 'classes') for i in data['classes']])
        elif data.get('annee'):
            qs = qs.filter(annee_scolaire_id=entier(data['annee'], 'annee'))
        else:
            raise ValidationError({'detail': 'Indiquez les classes (classes ou annee).'})

        debut = None
        if data.get('semaine'):
            try:
                jour = date.fromisoformat(str(data['semaine']))
            except ValueError:
                raise ValidationError({'semaine': 'Date invalide (format AAAA-MM-JJ).'})
            debut = jour - timedelta(days=jour.weekday())   # on revient au lundi

        tri = ('numero',) if data.get('ordre') == 'numero' else ('eleve__nom', 'eleve__prenom')
        fiches = []
        for classe in qs.order_by('nom'):
            eleves = classe.inscriptions.select_related('eleve').order_by(*tri)
            fiches.append({
                'classe': classe.nom, 'annee': classe.annee_scolaire.libelle,
                'eleves': [{'numero': i.numero, 'nom': i.eleve.nom, 'prenom': i.eleve.prenom}
                           for i in eleves],
            })
        if not fiches:
            raise ValidationError({'detail': 'Aucune classe à imprimer.'})
        octets = pdf.fiches_appel_pdf(fiches, debut, _etablissement())
        noms = ', '.join(f['classe'] for f in fiches[:6]) + (' …' if len(fiches) > 6 else '')
        journal.enregistrer(
            request, 'impression', 'impression',
            f"{journal.acteur(request.user)} a imprimé {len(fiches)} fiche(s) d'appel : {noms}.",
        )
        return _reponse_pdf(octets, 'fiches-appel.pdf')


# ---------- PHOTO D'ÉLÈVE ----------
class ElevePhotoView(APIView):
    """Image de la photo d'un élève. Administrateur : tous les élèves.
    Enseignant : seulement les élèves de ses classes.
    (Les photos ne sont jamais servies publiquement : le navigateur envoie son jeton.)"""
    permission_classes = [IsEnseignantOrAdmin]

    def get(self, request, pk):
        eleve = get_object_or_404(Eleve, pk=pk)
        if not user_is_admin(request.user):
            autorise = Inscription.objects.filter(eleve=eleve).filter(Exists(
                Affectation.objects.filter(enseignant=request.user, classe_id=OuterRef('classe_id'))
            )).exists()
            if not autorise:
                raise PermissionDenied("Cet élève n'est pas dans une de vos classes.")
        if not eleve.photo:
            raise NotFound("Cet élève n'a pas de photo.")
        try:
            fichier = eleve.photo.open('rb')
        except (OSError, ValueError):
            raise NotFound("La photo est introuvable sur le serveur.")
        reponse = FileResponse(fichier, content_type='image/jpeg')
        reponse['Cache-Control'] = 'private, max-age=86400'   # le jeton change à chaque nouvelle photo
        return reponse


# ---------- PIÈCES JOINTES ----------
class InscriptionPiecesView(APIView):
    """Ajoute une ou plusieurs pièces jointes à une inscription existante.
    Corps multipart : fichiers (un ou plusieurs), libelles (un par fichier, facultatif)."""
    permission_classes = [IsAdmin]

    def post(self, request, pk):
        ins = get_object_or_404(
            Inscription.objects.select_related('eleve', 'classe', 'annee_scolaire'), pk=pk)
        if ins.annee_scolaire.cloturee:
            raise ValidationError(
                f"L'année {ins.annee_scolaire.libelle} est clôturée : le dossier ne peut plus être modifié.")
        pieces = lire_pieces_envoyees(request)
        if not pieces:
            raise ValidationError({'fichiers': 'Choisissez au moins un fichier.'})
        with transaction.atomic():
            creees = creer_pieces(ins, pieces, request.user)
        noms = ', '.join(p.libelle or p.nom_original for p in creees)
        journal.enregistrer(
            request, 'piece_jointe', 'creation',
            f"{journal.acteur(request.user)} a ajouté {len(creees)} pièce(s) jointe(s) au dossier de "
            f"{ins.eleve.nom_complet} ({ins.classe.nom}, {ins.annee_scolaire.libelle}) : {noms}.",
            annee=ins.annee_scolaire.libelle, classe=ins.classe.nom,
            eleve=ins.eleve.nom_complet, cible_id=ins.pk,
        )
        return Response(PieceJointeSerializer(creees, many=True).data, status=201)


class PieceJointeView(APIView):
    """GET : télécharge / affiche la pièce jointe. DELETE : la supprime."""
    permission_classes = [IsAdmin]

    @staticmethod
    def _piece(pk):
        return get_object_or_404(PieceJointe.objects.select_related(
            'inscription__eleve', 'inscription__classe', 'inscription__annee_scolaire'), pk=pk)

    def get(self, request, pk):
        piece = self._piece(pk)
        try:
            fichier = piece.fichier.open('rb')
        except (OSError, ValueError):
            raise NotFound("Le fichier est introuvable sur le serveur.")
        return FileResponse(
            fichier, filename=piece.nom_original, as_attachment=False,
            content_type=piece.type_mime or type_mime_de(piece.nom_original),
        )

    def delete(self, request, pk):
        piece = self._piece(pk)
        ins = piece.inscription
        if ins.annee_scolaire.cloturee:
            raise ValidationError(
                f"L'année {ins.annee_scolaire.libelle} est clôturée : le dossier ne peut plus être modifié.")
        nom = piece.libelle or piece.nom_original
        piece.delete()
        journal.enregistrer(
            request, 'piece_jointe', 'suppression',
            f"{journal.acteur(request.user)} a supprimé la pièce jointe « {nom} » du dossier de "
            f"{ins.eleve.nom_complet} ({ins.classe.nom}, {ins.annee_scolaire.libelle}).",
            annee=ins.annee_scolaire.libelle, classe=ins.classe.nom,
            eleve=ins.eleve.nom_complet, cible_id=ins.pk,
        )
        return Response(status=204)

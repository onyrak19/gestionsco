"""API des finances : tarifs, encaissements, dépenses/entrées, salaires, bilan, impressions."""
from datetime import date

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from journal import services as journal
from school.models import AnneeScolaire, Classe, Inscription
from school.niveaux import NIVEAUX_AVEC_SERIE, rang_niveau
from school.permissions import IsAdmin
from school.views import JournalMixin, _etablissement, _inscriptions_a_imprimer, entier, int_param

from . import bilan as bilan_mod
from . import pdf, services
from .models import (
    AvanceSalaire, CategorieFinance, Employe, LignePaiement, MODES_PAIEMENT, Mouvement, Paiement,
    PaieSalaire, Tarif,
)
from .serializers import (
    AnnulationSerializer, AvanceSerializer, CategorieSerializer, EmployeSerializer,
    MouvementSerializer, PaiementEntreeSerializer, SalaireEntreeSerializer, SalaireGroupeSerializer,
    TarifNiveauSerializer, TarifsCopieSerializer, nom_utilisateur, paiement_dict, paie_dict,
)
from .outils import libelle_mois, montant_fr


# ---------------------------------------------------------------------------
# Outils
# ---------------------------------------------------------------------------
def devise():
    return getattr(settings, 'DEVISE', 'Ar')


def argent(valeur):
    return montant_fr(valeur, devise())


def annee_demandee(request, nom='annee'):
    """Année choisie (?annee=<id> ou champ « annee » du corps), sinon l'année en cours."""
    brut = request.query_params.get(nom)
    corps = getattr(request, 'data', None)
    if brut in (None, '') and hasattr(corps, 'get'):
        brut = corps.get(nom)
    if brut not in (None, ''):
        return get_object_or_404(AnneeScolaire, pk=entier(brut, nom))
    active = AnneeScolaire.objects.filter(active=True).first()
    if not active:
        raise ValidationError({nom: "Aucune année scolaire en cours : choisissez une année."})
    return active


def param_date(request, nom):
    valeur = request.query_params.get(nom) or (request.data.get(nom) if hasattr(request, 'data') else None)
    if not valeur:
        return None
    try:
        return date.fromisoformat(str(valeur)[:10])
    except ValueError:
        raise ValidationError({nom: 'Date invalide (format AAAA-MM-JJ).'})


def periode(request):
    """(début, fin) : dates données, sinon dates de l'année choisie (ou en cours)."""
    debut, fin = param_date(request, 'date_debut'), param_date(request, 'date_fin')
    if debut and fin:
        if fin < debut:
            raise ValidationError({'date_fin': 'La date de fin précède la date de début.'})
        return debut, fin
    annee = annee_demandee(request)
    return debut or annee.date_debut, fin or annee.date_fin


def reponse_pdf(octets, nom_fichier, telecharger=False):
    reponse = HttpResponse(octets, content_type='application/pdf')
    mode = 'attachment' if str(telecharger).lower() in ('1', 'true', 'oui') else 'inline'
    reponse['Content-Disposition'] = f'{mode}; filename="{nom_fichier}"'
    return reponse


def vrai(valeur):
    return str(valeur).lower() in ('1', 'true', 'oui', 'yes')


def verifier_annee_ouverte(annee):
    if annee.cloturee:
        raise ValidationError(f"L'année {annee.libelle} est clôturée : ses tarifs sont figés.")


# ---------------------------------------------------------------------------
# Paramètres de l'écran
# ---------------------------------------------------------------------------
class ParametresView(APIView):
    """Listes et réglages utiles aux formulaires (types, modes, mois de l'année...)."""
    permission_classes = [IsAdmin]

    def get(self, request):
        annee = AnneeScolaire.objects.filter(active=True).first()
        return Response({
            'devise': devise(),
            'types_paiement': [{'value': v, 'label': l} for v, l in Paiement.TYPES],
            'modes_paiement': [{'value': v, 'label': l} for v, l in MODES_PAIEMENT],
            'types_tarif': [{'value': v, 'label': l} for v, l in Tarif.TYPES],
            'annee_active': None if not annee else {
                'id': annee.id, 'libelle': annee.libelle,
                'mois': [{'mois': services.mois_cle(m), 'libelle': libelle_mois(m)}
                         for m in services.mois_de_l_annee(annee)],
            },
            'mois_courant': services.mois_cle(services.premier_du_mois(services.aujourd_hui())),
        })


# ---------------------------------------------------------------------------
# Tarifs (droits d'inscription, écolages, autres frais) par niveau
# ---------------------------------------------------------------------------
class TarifsView(APIView):
    """GET ?annee=<id> : un bloc par niveau (et série) avec ses classes et ses tarifs.
    PUT : remplace les tarifs d'un niveau
          {annee, niveau, serie, droit_inscription, ecolage_mensuel, autres: [{libelle, montant}],
           appliquer_a_toutes_series}
    Quand l'année n'a encore aucun tarif, les tarifs de l'année précédente sont proposés
    (« propose »: true) sans être enregistrés."""
    permission_classes = [IsAdmin]

    @staticmethod
    def _bloc(classes=None):
        return {'classes': classes or [], 'droit_inscription': None, 'ecolage_mensuel': None,
                'autres': [], 'configure': False, 'propose': False}

    def get(self, request):
        return self._reponse(annee_demandee(request))

    def _reponse(self, annee):
        blocs = {}
        classes = (Classe.objects.filter(annee_scolaire=annee).exclude(niveau='')
                   .annotate(nb=Count('inscriptions')).order_by('nom'))
        for c in classes:
            bloc = blocs.setdefault((c.niveau, c.serie), self._bloc())
            bloc['classes'].append({'id': c.id, 'nom': c.nom, 'effectif': c.nb})

        tarifs = list(Tarif.objects.filter(annee_scolaire=annee))
        propose = False
        if not tarifs:
            precedent = (Tarif.objects.filter(annee_scolaire__date_debut__lt=annee.date_debut)
                         .order_by('-annee_scolaire__date_debut').first())
            if precedent:
                tarifs = list(Tarif.objects.filter(annee_scolaire=precedent.annee_scolaire))
                propose = True
        for t in tarifs:
            if propose and (t.niveau, t.serie) not in blocs:
                continue          # on ne propose que pour les niveaux qui existent cette année
            bloc = blocs.setdefault((t.niveau, t.serie), self._bloc())
            bloc['configure'], bloc['propose'] = not propose, propose
            if t.type == 'droit':
                bloc['droit_inscription'] = services.num(t.montant)
            elif t.type == 'ecolage':
                bloc['ecolage_mensuel'] = services.num(t.montant)
            else:
                bloc['autres'].append({'id': t.id if not propose else None, 'libelle': t.libelle,
                                       'montant': services.num(t.montant)})

        def ordre(cle):
            rang = rang_niveau(cle[0])
            return (rang if rang is not None else 999, cle[0], cle[1])
        niveaux = [{'niveau': n, 'serie': s, 'effectif': sum(c['effectif'] for c in b['classes']), **b}
                   for (n, s), b in sorted(blocs.items(), key=lambda kv: ordre(kv[0]))]
        return Response({
            'annee': {'id': annee.id, 'libelle': annee.libelle, 'cloturee': annee.cloturee},
            'devise': devise(), 'niveaux': niveaux,
            'niveaux_avec_serie': list(NIVEAUX_AVEC_SERIE),
        })

    @transaction.atomic
    def put(self, request):
        s = TarifNiveauSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        annee = d['annee']
        verifier_annee_ouverte(annee)
        niveau, serie = d['niveau'].strip(), d.get('serie', '').strip().upper()

        if d['appliquer_a_toutes_series']:
            series = set(Classe.objects.filter(annee_scolaire=annee, niveau=niveau).values_list('serie', flat=True))
            series = sorted(series) or [serie]
        else:
            if niveau in NIVEAUX_AVEC_SERIE and not serie:
                raise ValidationError({'serie': "La série est obligatoire pour ce niveau (ex. L, S, OSE)."})
            series = [serie if niveau in NIVEAUX_AVEC_SERIE else '']

        voulus = {}
        if d.get('droit_inscription') is not None:
            voulus[('droit', '')] = d['droit_inscription']
        if d.get('ecolage_mensuel') is not None:
            voulus[('ecolage', '')] = d['ecolage_mensuel']
        for a in d.get('autres', []):
            voulus[('autre', a['libelle'].strip())] = a['montant']

        for s_ in series:
            existants = {(t.type, t.libelle): t for t in
                         Tarif.objects.filter(annee_scolaire=annee, niveau=niveau, serie=s_)}
            for cle, t in existants.items():
                if cle in voulus:
                    continue
                if t.type == 'autre' and LignePaiement.objects.filter(tarif=t).exists():
                    raise ValidationError(
                        f"Le frais « {t.libelle} » a déjà été encaissé : il ne peut plus être supprimé.")
                t.delete()
            for (type_, libelle), montant in voulus.items():
                Tarif.objects.update_or_create(
                    annee_scolaire=annee, niveau=niveau, serie=s_, type=type_, libelle=libelle,
                    defaults={'montant': montant})
        cible = f"{niveau} {', '.join(x for x in series if x)}".strip()
        noms = {'droit': "droit d'inscription", 'ecolage': 'écolage'}
        details = [f"{noms.get(type_, libelle)} {argent(montant)}" for (type_, libelle), montant in voulus.items()]
        journal.enregistrer(
            request, 'finance', 'modification',
            f"{journal.acteur(request.user)} a défini les tarifs de {cible} ({annee.libelle}) : "
            f"{', '.join(details) or 'aucun tarif'}.", annee=annee.libelle)
        return self._reponse(annee)


class TarifsCopierView(APIView):
    """Copie les tarifs d'une année vers une autre. Corps : {de, vers, ecraser}."""
    permission_classes = [IsAdmin]

    @transaction.atomic
    def post(self, request):
        s = TarifsCopieSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        source, cible, ecraser = s.validated_data['de'], s.validated_data['vers'], s.validated_data['ecraser']
        if source.id == cible.id:
            raise ValidationError("Choisissez deux années différentes.")
        verifier_annee_ouverte(cible)
        copies, ignores = 0, set()
        for t in Tarif.objects.filter(annee_scolaire=source):
            deja = Tarif.objects.filter(annee_scolaire=cible, niveau=t.niveau, serie=t.serie).exists()
            if deja and not ecraser:
                ignores.add(f"{t.niveau} {t.serie}".strip())
                continue
            Tarif.objects.update_or_create(
                annee_scolaire=cible, niveau=t.niveau, serie=t.serie, type=t.type, libelle=t.libelle,
                defaults={'montant': t.montant})
            copies += 1
        journal.enregistrer(
            request, 'finance', 'creation',
            f"{journal.acteur(request.user)} a copié les tarifs de {source.libelle} vers {cible.libelle} "
            f"({copies} tarif(s)).", annee=cible.libelle)
        return Response({'copies': copies, 'niveaux_ignores': sorted(ignores)})


# ---------------------------------------------------------------------------
# Situation des élèves et encaissements
# ---------------------------------------------------------------------------
def _mois_reference(request):
    brut = request.query_params.get('au')
    return services.lire_mois(brut, 'au') if brut else None


def _resume_situation(ins, sit):
    e = ins.eleve
    ec = sit['ecolage']
    return {
        'inscription': ins.id, 'eleve': e.id, 'nom': e.nom, 'prenom': e.prenom, 'matricule': e.matricule,
        'parent_nom': e.parent_nom, 'parent_mobile': e.parent_mobile,
        'classe': ins.classe_id, 'classe_nom': ins.classe.nom, 'niveau': ins.classe.niveau,
        'serie': ins.classe.serie, 'numero': ins.numero,
        'tarif_defini': sit['tarif_defini'],
        'droit_montant': sit['droit']['montant'], 'droit_paye': sit['droit']['paye'],
        'ecolage_mensuel': ec['mensuel'], 'nb_mois_payes': ec['nb_payes'], 'nb_mois_impayes': ec['nb_impayes'],
        'mois_impayes': [m['mois'] for m in ec['mois'] if m['statut'] == 'impaye'],
        'total_paye': sit['total_paye'], 'du_a_ce_jour': sit['du_a_ce_jour'], 'reste_annee': sit['reste_annee'],
    }


class SituationsView(APIView):
    """Liste des élèves d'une année avec leur situation de paiement.
    ?annee= &classe= &q= &statut=impayes|a_jour &au=AAAA-MM (mois de référence, défaut : ce mois)"""
    permission_classes = [IsAdmin]

    def get(self, request):
        annee = annee_demandee(request)
        qs = Inscription.objects.filter(annee_scolaire=annee).select_related('eleve', 'classe', 'annee_scolaire')
        classe = int_param(request, 'classe')
        if classe:
            qs = qs.filter(classe_id=classe)
        q = (request.query_params.get('q') or '').strip()
        if q:
            qs = qs.filter(Q(eleve__nom__icontains=q) | Q(eleve__prenom__icontains=q)
                           | Q(eleve__matricule__icontains=q))
        qs = qs.order_by('classe__nom', 'eleve__nom', 'eleve__prenom')
        lignes = [_resume_situation(i, s) for i, s in services.situations_pour(qs, _mois_reference(request))]
        statut = request.query_params.get('statut')
        if statut == 'impayes':
            lignes = [l for l in lignes if (l['du_a_ce_jour'] or 0) > 0]
        elif statut == 'a_jour':
            lignes = [l for l in lignes if (l['du_a_ce_jour'] or 0) <= 0 and l['tarif_defini']]
        return Response({
            'annee': {'id': annee.id, 'libelle': annee.libelle},
            'total_du': services.num(sum((services.dec(l['du_a_ce_jour'] or 0) for l in lignes), services.ZERO)),
            'eleves': lignes,
        })


class SituationEleveView(APIView):
    """Détail financier d'une inscription : droit, mois d'écolage payés / non payés, autres frais."""
    permission_classes = [IsAdmin]

    def get(self, request, pk):
        ins = get_object_or_404(
            Inscription.objects.select_related('eleve', 'classe', 'annee_scolaire'), pk=pk)
        sit = dict(services.situations_pour([ins], _mois_reference(request))[0][1])
        e = ins.eleve
        sit['eleve'] = {'id': e.id, 'nom': e.nom, 'prenom': e.prenom, 'matricule': e.matricule,
                        'parent_nom': e.parent_nom, 'parent_mobile': e.parent_mobile,
                        'parent2_nom': e.parent2_nom, 'parent2_mobile': e.parent2_mobile}
        sit['classe'] = {'id': ins.classe_id, 'nom': ins.classe.nom, 'niveau': ins.classe.niveau,
                         'serie': ins.classe.serie}
        sit['devise'] = devise()
        return Response(sit)


class PaiementListCreateView(APIView):
    """GET : liste des paiements. ?annee= &classe= &inscription= &type= &date_debut= &date_fin=
    &q= &annule=true|false.
    POST : encaisse un paiement. Le montant n'est JAMAIS saisi : il vient du tarif du niveau.
      {inscription, type: droit|ecolage|autre, mois: ['2026-09', ...] (écolage), tarif: <id> (autre),
       date, mode, reference, observation, apercu: true (calcule sans enregistrer)}"""
    permission_classes = [IsAdmin]

    def get(self, request):
        qs = (Paiement.objects.select_related('saisi_par', 'annule_par').prefetch_related('lignes'))
        p = request.query_params
        if int_param(request, 'annee'):
            qs = qs.filter(annee_scolaire_id=int_param(request, 'annee'))
        if int_param(request, 'classe'):
            qs = qs.filter(inscription__classe_id=int_param(request, 'classe'))
        if int_param(request, 'inscription'):
            qs = qs.filter(inscription_id=int_param(request, 'inscription'))
        if p.get('type'):
            qs = qs.filter(type=p['type'])
        debut, fin = param_date(request, 'date_debut'), param_date(request, 'date_fin')
        if debut:
            qs = qs.filter(date__gte=debut)
        if fin:
            qs = qs.filter(date__lte=fin)
        if p.get('annule') in ('true', 'false'):
            qs = qs.filter(annule=vrai(p['annule']))
        q = (p.get('q') or '').strip()
        if q:
            qs = qs.filter(Q(eleve_nom__icontains=q) | Q(matricule__icontains=q) | Q(numero__icontains=q))
        liste = list(qs[:1000])
        return Response({
            'total': services.num(sum((x.montant_total for x in liste if not x.annule), services.ZERO)),
            'paiements': [paiement_dict(x) for x in liste],
        })

    def post(self, request):
        s = PaiementEntreeSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        ins = d['inscription']
        if d['apercu']:
            lignes, total = services.preparer_paiement(ins, d['type'], d.get('mois'), d.get('tarif'))
            return Response({
                'apercu': True, 'eleve': ins.eleve.nom_complet, 'classe': ins.classe.nom,
                'type': d['type'], 'total': services.num(total),
                'lignes': [{'libelle': l['libelle'], 'mois': services.mois_cle(l['mois']) if l['mois'] else None,
                            'montant': services.num(l['montant'])} for l in lignes],
            })
        paiement = services.creer_paiement(
            ins, d['type'], mois=d.get('mois'), tarif_id=d.get('tarif'), date_paiement=d.get('date'),
            mode=d['mode'], reference=d['reference'], observation=d['observation'], user=request.user)
        journal.enregistrer(
            request, 'paiement', 'creation',
            f"{journal.acteur(request.user)} a encaissé {argent(paiement.montant_total)} "
            f"({paiement.get_type_display().lower()}) de {paiement.eleve_nom} — reçu {paiement.numero}.",
            annee=paiement.annee_libelle, classe=paiement.classe_nom, eleve=paiement.eleve_nom,
            cible_id=paiement.id)
        paiement = Paiement.objects.select_related('saisi_par', 'annule_par').prefetch_related('lignes').get(pk=paiement.pk)
        return Response(paiement_dict(paiement), status=201)


def _paiement(pk):
    return get_object_or_404(
        Paiement.objects.select_related('saisi_par', 'annule_par').prefetch_related('lignes'), pk=pk)


class PaiementDetailView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request, pk):
        return Response(paiement_dict(_paiement(pk)))


class PaiementAnnulerView(APIView):
    """Annule un paiement (il reste visible, barré « annulé »). Corps : {motif}."""
    permission_classes = [IsAdmin]

    def post(self, request, pk):
        s = AnnulationSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        paiement = _paiement(pk)
        services.annuler_paiement(paiement, s.validated_data['motif'], request.user)
        journal.enregistrer(
            request, 'paiement', 'suppression',
            f"{journal.acteur(request.user)} a annulé le paiement {paiement.numero} de {paiement.eleve_nom} "
            f"({argent(paiement.montant_total)}) : {paiement.motif_annulation}.",
            annee=paiement.annee_libelle, classe=paiement.classe_nom, eleve=paiement.eleve_nom,
            cible_id=paiement.id)
        return Response(paiement_dict(_paiement(pk)))


class PaiementRecuView(APIView):
    """Reçu PDF d'un paiement. ?telecharger=1 pour forcer le téléchargement."""
    permission_classes = [IsAdmin]

    def get(self, request, pk):
        p = _paiement(pk)
        recu = {
            'numero': p.numero, 'date': p.date, 'eleve': p.eleve_nom, 'matricule': p.matricule,
            'classe': p.classe_nom, 'annee': p.annee_libelle, 'type_libelle': p.get_type_display(),
            'lignes': [{'libelle': l.libelle, 'montant': l.montant} for l in p.lignes.all()],
            'total': p.montant_total, 'mode_libelle': p.get_mode_display(), 'reference': p.reference,
            'observation': p.observation, 'caissier': nom_utilisateur(p.saisi_par),
            'annule': p.annule, 'motif_annulation': p.motif_annulation,
        }
        octets = pdf.recu_pdf(recu, _etablissement(), devise())
        journal.enregistrer(
            request, 'impression', 'impression',
            f"{journal.acteur(request.user)} a imprimé le reçu {p.numero} de {p.eleve_nom}.",
            annee=p.annee_libelle, classe=p.classe_nom, eleve=p.eleve_nom, cible_id=p.id)
        return reponse_pdf(octets, f"recu-{p.numero}.pdf", request.query_params.get('telecharger'))


# ---------------------------------------------------------------------------
# Catégories, dépenses et entrées d'argent
# ---------------------------------------------------------------------------
class CategorieListView(JournalMixin, generics.ListCreateAPIView):
    """Catégories de dépenses et d'entrées. ?sens=depense|entree &actif=true"""
    serializer_class = CategorieSerializer
    permission_classes = [IsAdmin]
    journal_categorie = 'finance'

    def get_queryset(self):
        qs = CategorieFinance.objects.all()
        p = self.request.query_params
        if p.get('sens'):
            qs = qs.filter(sens=p['sens'])
        if p.get('actif') in ('true', 'false'):
            qs = qs.filter(actif=vrai(p['actif']))
        return qs

    def journal_libelle(self, obj):
        return f"la catégorie « {obj.nom} » ({obj.get_sens_display().lower()})"


class CategorieDetailView(JournalMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = CategorieFinance.objects.all()
    serializer_class = CategorieSerializer
    permission_classes = [IsAdmin]
    journal_categorie = 'finance'
    journal_champs = {'nom': 'nom', 'sens': 'sens', 'actif': 'active'}

    def journal_libelle(self, obj):
        return f"la catégorie « {obj.nom} » ({obj.get_sens_display().lower()})"

    def perform_destroy(self, instance):
        if instance.mouvements.exists():
            raise ValidationError(
                "Cette catégorie est utilisée par des opérations : désactivez-la plutôt que de la supprimer.")
        super().perform_destroy(instance)


class MouvementListView(JournalMixin, generics.ListCreateAPIView):
    """Dépenses et entrées d'argent. ?sens= &categorie= &imprevu=true &date_debut= &date_fin= &q="""
    serializer_class = MouvementSerializer
    permission_classes = [IsAdmin]
    journal_categorie = 'finance'

    def get_queryset(self):
        qs = Mouvement.objects.select_related('categorie', 'saisi_par')
        p = self.request.query_params
        if p.get('sens'):
            qs = qs.filter(categorie__sens=p['sens'])
        if int_param(self.request, 'categorie'):
            qs = qs.filter(categorie_id=int_param(self.request, 'categorie'))
        if p.get('imprevu') in ('true', 'false'):
            qs = qs.filter(imprevu=vrai(p['imprevu']))
        debut, fin = param_date(self.request, 'date_debut'), param_date(self.request, 'date_fin')
        if debut:
            qs = qs.filter(date__gte=debut)
        if fin:
            qs = qs.filter(date__lte=fin)
        q = (p.get('q') or '').strip()
        if q:
            qs = qs.filter(Q(libelle__icontains=q) | Q(reference__icontains=q) | Q(notes__icontains=q))
        return qs

    def journal_libelle(self, obj):
        genre = "l'entrée d'argent" if obj.sens == 'entree' else ('la dépense imprévue' if obj.imprevu else 'la dépense')
        return f"{genre} « {obj.libelle} » ({argent(obj.montant)})"


class MouvementDetailView(JournalMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Mouvement.objects.select_related('categorie', 'saisi_par')
    serializer_class = MouvementSerializer
    permission_classes = [IsAdmin]
    journal_categorie = 'finance'
    journal_champs = {'date': 'date', 'categorie': 'catégorie', 'libelle': 'libellé', 'montant': 'montant',
                      'imprevu': 'imprévu', 'reference': 'référence'}

    def journal_libelle(self, obj):
        return f"l'opération « {obj.libelle} » ({argent(obj.montant)})"


# ---------------------------------------------------------------------------
# Employés, avances, salaires
# ---------------------------------------------------------------------------
class EmployeListView(JournalMixin, generics.ListCreateAPIView):
    """Employés (enseignants et personnel). ?actif=true &q="""
    serializer_class = EmployeSerializer
    permission_classes = [IsAdmin]
    journal_categorie = 'salaire'

    def get_queryset(self):
        qs = Employe.objects.all()
        p = self.request.query_params
        if p.get('actif') in ('true', 'false'):
            qs = qs.filter(actif=vrai(p['actif']))
        q = (p.get('q') or '').strip()
        if q:
            qs = qs.filter(Q(nom__icontains=q) | Q(prenom__icontains=q) | Q(poste__icontains=q))
        return qs

    def journal_libelle(self, obj):
        return f"l'employé {obj.nom_complet}"


class EmployeDetailView(JournalMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Employe.objects.all()
    serializer_class = EmployeSerializer
    permission_classes = [IsAdmin]
    journal_categorie = 'salaire'
    journal_champs = {'nom': 'nom', 'prenom': 'prénom', 'poste': 'poste', 'telephone': 'téléphone',
                      'salaire_mensuel': 'salaire mensuel', 'actif': 'actif'}

    def journal_libelle(self, obj):
        return f"l'employé {obj.nom_complet}"

    def perform_destroy(self, instance):
        if instance.paies.exists() or instance.avances.exists():
            raise ValidationError(
                "Cet employé a des salaires ou des avances enregistrés : désactivez-le plutôt que de le supprimer.")
        super().perform_destroy(instance)


class EmployeSituationView(APIView):
    """Avances à rembourser et mois déjà payés d'un employé (pour préparer sa paie)."""
    permission_classes = [IsAdmin]

    def get(self, request, pk):
        emp = get_object_or_404(Employe, pk=pk)
        en_cours = services.avances_en_cours(emp)
        return Response({
            'employe': EmployeSerializer(emp).data,
            'salaire_mensuel': services.num(emp.salaire_mensuel),
            'avances': [{'id': a.id, 'date': a.date.isoformat(), 'montant': services.num(a.montant),
                         'restant': services.num(reste), 'motif': a.motif} for a, reste in en_cours],
            'total_avances': services.num(sum((r for _a, r in en_cours), services.ZERO)),
            'mois_payes': sorted(services.mois_cle(m) for m in services.mois_deja_payes(emp)),
        })


class AvanceListView(JournalMixin, generics.ListCreateAPIView):
    """Avances sur salaire. ?employe=<id> &annulee=true|false"""
    serializer_class = AvanceSerializer
    permission_classes = [IsAdmin]
    journal_categorie = 'salaire'

    def get_queryset(self):
        qs = AvanceSalaire.objects.select_related('employe', 'saisi_par').prefetch_related('retenues__paie')
        if int_param(self.request, 'employe'):
            qs = qs.filter(employe_id=int_param(self.request, 'employe'))
        a = self.request.query_params.get('annulee')
        if a in ('true', 'false'):
            qs = qs.filter(annulee=vrai(a))
        return qs

    def journal_libelle(self, obj):
        return f"une avance de {argent(obj.montant)} à {obj.employe.nom_complet}"


class AvanceAnnulerView(APIView):
    """Annule une avance (impossible si une partie a déjà été retenue sur une paie)."""
    permission_classes = [IsAdmin]

    def post(self, request, pk):
        avance = get_object_or_404(AvanceSalaire.objects.select_related('employe'), pk=pk)
        if avance.annulee:
            raise ValidationError("Cette avance est déjà annulée.")
        if avance.retenues.filter(paie__annule=False).exists():
            raise ValidationError("Une partie de cette avance a déjà été retenue sur une paie : "
                                  "annulez d'abord cette paie.")
        avance.annulee = True
        avance.save(update_fields=['annulee'])
        journal.enregistrer(
            request, 'salaire', 'suppression',
            f"{journal.acteur(request.user)} a annulé l'avance de {argent(avance.montant)} "
            f"de {avance.employe.nom_complet}.", cible_id=avance.id)
        return Response(AvanceSerializer(avance).data)


def _paie(pk):
    return get_object_or_404(
        PaieSalaire.objects.select_related('saisi_par', 'annule_par')
        .prefetch_related('lignes', 'retenues'), pk=pk)


class SalaireListCreateView(APIView):
    """GET : paies. ?employe= &mois=AAAA-MM &date_debut= &date_fin= &annule=true|false
    POST : paie d'un employé. Le montant vient du salaire de l'employé.
      {employe, mois: ['2025-12', '2026-01'], date, mode,
       exceptionnel: true, montant_exceptionnel, motif_exceptionnel   (autre montant, avec motif),
       retenue_avance (facultatif : par défaut toutes les avances dues), autres_retenues, motif_retenues,
       apercu: true (calcule sans enregistrer)}"""
    permission_classes = [IsAdmin]

    def get(self, request):
        qs = PaieSalaire.objects.select_related('saisi_par', 'annule_par').prefetch_related('lignes', 'retenues')
        p = request.query_params
        if int_param(request, 'employe'):
            qs = qs.filter(employe_id=int_param(request, 'employe'))
        if p.get('mois'):
            qs = qs.filter(lignes__mois=services.lire_mois(p['mois'])).distinct()
        debut, fin = param_date(request, 'date_debut'), param_date(request, 'date_fin')
        if debut:
            qs = qs.filter(date__gte=debut)
        if fin:
            qs = qs.filter(date__lte=fin)
        if p.get('annule') in ('true', 'false'):
            qs = qs.filter(annule=vrai(p['annule']))
        liste = list(qs[:1000])
        return Response({
            'total_net': services.num(sum((x.net_paye for x in liste if not x.annule), services.ZERO)),
            'paies': [paie_dict(x) for x in liste],
        })

    def post(self, request):
        s = SalaireEntreeSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        emp = d['employe']
        prepare = services.preparer_salaire(
            emp, d.get('mois'), exceptionnel=d['exceptionnel'],
            montant_exceptionnel=d.get('montant_exceptionnel'), motif_exceptionnel=d['motif_exceptionnel'],
            retenue_avance=d.get('retenue_avance'), autres_retenues=d.get('autres_retenues') or 0,
            motif_retenues=d['motif_retenues'])
        if d['apercu']:
            return Response({
                'apercu': True, 'employe': emp.nom_complet,
                'mois': [{'mois': services.mois_cle(m), 'libelle': libelle_mois(m)} for m in prepare['mois']],
                'salaire_mensuel': services.num(prepare['salaire_mensuel']),
                'brut': services.num(prepare['brut']),
                'retenue_avance': services.num(prepare['retenue_avance']),
                'autres_retenues': services.num(prepare['autres_retenues']),
                'net': services.num(prepare['net']),
                'avances_disponibles': services.num(prepare['avances_disponibles']),
                'exceptionnel': prepare['exceptionnel'],
            })
        paie = services.creer_salaire(emp, prepare, d.get('date'), d['mode'], d['observation'], request.user)
        detail = ''
        if paie.retenue_avances:
            detail += f", dont {argent(paie.retenue_avances)} d'avance retenue"
        if paie.autres_retenues:
            detail += f", {argent(paie.autres_retenues)} de retenue ({paie.motif_retenues})"
        if paie.exceptionnel:
            detail += f" — situation exceptionnelle : {paie.motif_exceptionnel}"
        journal.enregistrer(
            request, 'salaire', 'creation',
            f"{journal.acteur(request.user)} a payé {argent(paie.net_paye)} net à {paie.employe_nom} "
            f"(brut {argent(paie.montant_brut)}{detail}) — {paie.numero}.", cible_id=paie.id)
        return Response(paie_dict(_paie(paie.pk)), status=201)


class SalaireDetailView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request, pk):
        return Response(paie_dict(_paie(pk)))


class SalaireAnnulerView(APIView):
    """Annule une paie : les avances retenues redeviennent dues. Corps : {motif}."""
    permission_classes = [IsAdmin]

    def post(self, request, pk):
        s = AnnulationSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        paie = _paie(pk)
        services.annuler_salaire(paie, s.validated_data['motif'], request.user)
        journal.enregistrer(
            request, 'salaire', 'suppression',
            f"{journal.acteur(request.user)} a annulé la paie {paie.numero} de {paie.employe_nom} "
            f"({argent(paie.net_paye)}) : {paie.motif_annulation}.", cible_id=paie.id)
        return Response(paie_dict(_paie(pk)))


class SalaireFicheView(APIView):
    """Fiche de paie PDF."""
    permission_classes = [IsAdmin]

    def get(self, request, pk):
        p = _paie(pk)
        donnees = {
            'numero': p.numero, 'date': p.date, 'employe': p.employe_nom, 'poste': p.poste,
            'mois': [libelle_mois(l.mois) for l in p.lignes.all()],
            'salaire_mensuel': p.salaire_mensuel, 'brut': p.montant_brut,
            'retenue_avances': p.retenue_avances, 'autres_retenues': p.autres_retenues,
            'motif_retenues': p.motif_retenues, 'net': p.net_paye, 'mode_libelle': p.get_mode_display(),
            'exceptionnel': p.exceptionnel, 'motif_exceptionnel': p.motif_exceptionnel, 'annule': p.annule,
        }
        octets = pdf.fiche_paie_pdf(donnees, _etablissement(), devise())
        journal.enregistrer(
            request, 'impression', 'impression',
            f"{journal.acteur(request.user)} a imprimé la fiche de paie {p.numero} de {p.employe_nom}.",
            cible_id=p.id)
        return reponse_pdf(octets, f"fiche-paie-{p.numero}.pdf", request.query_params.get('telecharger'))


class SalaireGroupeView(APIView):
    """Paie de plusieurs employés en un clic, pour les mêmes mois.
    {employes: [ids] | 'tous', mois: [...], date, mode,
     retenues: {"<id employé>": {montant, motif}} (retenues en plus des avances), apercu: true}
    Les avances sont retenues automatiquement ; les mois déjà payés sont ignorés ; une erreur sur un
    employé n'empêche pas de payer les autres."""
    permission_classes = [IsAdmin]

    def post(self, request):
        s = SalaireGroupeSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        if d['employes'] == 'tous':
            employes = list(Employe.objects.filter(actif=True))
        else:
            employes = list(Employe.objects.filter(id__in=d['employes']))
            if len(employes) != len(set(d['employes'])):
                raise ValidationError({'employes': "Un ou plusieurs employés sont introuvables."})
        if not employes:
            raise ValidationError({'employes': "Aucun employé à payer."})
        retenues = {int(k): v for k, v in (d.get('retenues') or {}).items() if str(k).isdigit()}
        resultats, brut, net = services.payer_groupe(
            employes, d['mois'], d.get('date'), d['mode'], retenues, appliquer=not d['apercu'], user=request.user)
        nb_payes = sum(1 for r in resultats if r['statut'] == 'paye')
        if not d['apercu'] and nb_payes:
            journal.enregistrer(
                request, 'salaire', 'creation',
                f"{journal.acteur(request.user)} a payé {nb_payes} salaire(s) en un clic "
                f"({', '.join(services.libelle_mois(m) for m in services.lire_mois_liste(d['mois']))}) — "
                f"net total {argent(net)}.")
        return Response({
            'apercu': d['apercu'], 'resultats': resultats,
            'total_brut': services.num(brut), 'total_net': services.num(net),
            'nb_payes': nb_payes, 'nb_erreurs': sum(1 for r in resultats if r['statut'] == 'erreur'),
        })


# ---------------------------------------------------------------------------
# Bilan
# ---------------------------------------------------------------------------
class BilanView(APIView):
    """Entrées, dépenses (dont imprévus et salaires) et solde d'une période.
    ?date_debut= &date_fin= ou ?annee=<id> (défaut : année en cours)."""
    permission_classes = [IsAdmin]

    def get(self, request):
        debut, fin = periode(request)
        return Response(bilan_mod.bilan(debut, fin))


# ---------------------------------------------------------------------------
# Impressions PDF
# ---------------------------------------------------------------------------
def _cartes_donnees(inscriptions, mois_reference=None):
    cartes = []
    for ins, sit in services.situations_pour(inscriptions, mois_reference):
        e = ins.eleve
        cartes.append({
            'nom': e.nom, 'prenom': e.prenom, 'matricule': e.matricule, 'classe': ins.classe.nom,
            'annee': ins.annee_scolaire.libelle, 'parent_nom': e.parent_nom, 'parent_mobile': e.parent_mobile,
            'droit': sit['droit'], 'mois': sit['ecolage']['mois'],
            'total_paye': sit['total_paye'], 'du_a_ce_jour': sit['du_a_ce_jour'],
            'edite_le': services.aujourd_hui(),
        })
    return cartes


class PdfCartesEcolageView(APIView):
    """Cartes d'écolage (2 par page) avec le suivi mois par mois.
    Corps : {inscriptions: [ids] | classes: [ids] | classe: id | annee: id, ordre: alpha|numero}"""
    permission_classes = [IsAdmin]

    def post(self, request):
        liste = _inscriptions_a_imprimer(request)
        cartes = _cartes_donnees(liste)
        octets = pdf.cartes_ecolage_pdf(cartes, _etablissement(), devise())
        classes = sorted({i.classe.nom for i in liste})
        journal.enregistrer(
            request, 'impression', 'impression',
            f"{journal.acteur(request.user)} a imprimé {len(liste)} carte(s) d'écolage — "
            f"{', '.join(classes[:6])}{' …' if len(classes) > 6 else ''}.",
            classe=classes[0] if len(classes) == 1 else '')
        return reponse_pdf(octets, 'cartes-ecolage.pdf', request.data.get('telecharger'))


class PdfImpayesView(APIView):
    """Liste des élèves qui ont des écolages ou droits impayés.
    Corps : {annee, classes: [ids] (facultatif), au: 'AAAA-MM' (facultatif)}"""
    permission_classes = [IsAdmin]

    def post(self, request):
        data = request.data
        annee = annee_demandee(request)
        qs = Inscription.objects.filter(annee_scolaire=annee).select_related('eleve', 'classe', 'annee_scolaire')
        if data.get('classes'):
            if not isinstance(data['classes'], list):
                raise ValidationError({'classes': 'Doit être une liste.'})
            qs = qs.filter(classe_id__in=[entier(c, 'classes') for c in data['classes']])
        ref = services.lire_mois(data['au'], 'au') if data.get('au') else None
        qs = qs.order_by('classe__nom', 'eleve__nom', 'eleve__prenom')
        lignes, total = [], services.ZERO
        for ins, sit in services.situations_pour(qs, ref):
            du = services.dec(sit['du_a_ce_jour'] or 0)
            if du <= 0:
                continue
            total += du
            e = ins.eleve
            impayes = [m['libelle'] for m in sit['ecolage']['mois'] if m['statut'] == 'impaye']
            if not sit['droit']['paye'] and sit['droit']['montant']:
                impayes.insert(0, "Droit d'inscription")
            lignes.append([ins.classe.nom, f"{e.nom.upper()} {e.prenom}",
                           ' · '.join(v for v in (e.parent_nom, e.parent_mobile) if v) or '—',
                           ', '.join(impayes), argent(du)])
        au = libelle_mois(ref) if ref else libelle_mois(services.premier_du_mois(services.aujourd_hui()))
        octets = pdf.document_pdf(
            _etablissement(), 'Liste des impayés', f"Année scolaire {annee.libelle} — situation jusqu'à {au}",
            [('tableau', ['Classe', 'Élève', 'Parent / tuteur', 'Impayé', 'Montant dû'], lignes,
              [1.2, 2.6, 2.6, 5, 1.6], ['L', 'L', 'L', 'L', 'R'],
              ['', f"{len(lignes)} élève(s)", '', 'TOTAL DÛ', argent(total)] if lignes else None)],
            paysage=True)
        journal.enregistrer(
            request, 'impression', 'impression',
            f"{journal.acteur(request.user)} a imprimé la liste des impayés ({len(lignes)} élève(s), {argent(total)}).",
            annee=annee.libelle)
        return reponse_pdf(octets, 'impayes.pdf', data.get('telecharger'))


class PdfRapportView(APIView):
    """Rapport financier d'une période : bilan + journal de caisse.
    Corps : {date_debut, date_fin} ou {annee}"""
    permission_classes = [IsAdmin]

    def post(self, request):
        debut, fin = periode(request)
        b = bilan_mod.bilan(debut, fin)
        resume = [
            ('Droits, écolages et autres frais des élèves', argent(b['entrees']['scolarite']['total'])),
            ("Autres entrées d'argent", argent(b['entrees']['total_autres'])),
            ('TOTAL DES ENTRÉES', argent(b['entrees']['total'])),
            ('Dépenses de fonctionnement', argent(b['depenses']['total_fonctionnement'])),
            ('   dont imprévus', argent(b['depenses']['imprevus'])),
            ('Salaires payés (net)', argent(b['depenses']['salaires'])),
            ('Avances sur salaire données', argent(b['depenses']['avances'])),
            ('TOTAL DES DÉPENSES', argent(b['depenses']['total'])),
            ('SOLDE DE LA PÉRIODE', argent(b['solde'])),
        ]
        categories = [[c['categorie'], argent(c['total'])] for c in b['depenses']['categories']]
        entrees = [[c['categorie'], argent(c['total'])] for c in b['entrees']['autres']]
        caisse = bilan_mod.journal_caisse(debut, fin)
        lignes = [[l[0].strftime('%d/%m/%Y'), l[2], l[3], l[4], argent(l[5]) if l[5] else '',
                   argent(l[6]) if l[6] else ''] for l in caisse]
        blocs = [('titre', 'Résumé'), ('paires', resume)]
        if categories:
            blocs += [('titre', 'Dépenses par catégorie'),
                      ('tableau', ['Catégorie', 'Montant'], categories, [4, 1.5], ['L', 'R'], None)]
        if entrees:
            blocs += [('titre', "Entrées d'argent par catégorie"),
                      ('tableau', ['Catégorie', 'Montant'], entrees, [4, 1.5], ['L', 'R'], None)]
        blocs += [('titre', 'Journal de caisse'),
                  ('tableau', ['Date', 'Nature', 'Libellé', 'Pièce', 'Entrée', 'Sortie'], lignes,
                   [1.2, 2.6, 5, 1.6, 1.6, 1.6], ['L', 'L', 'L', 'L', 'R', 'R'],
                   ['', '', '', 'TOTAL', argent(b['entrees']['total']), argent(b['depenses']['total'])]
                   if lignes else None)]
        octets = pdf.document_pdf(
            _etablissement(), 'Rapport financier',
            f"Du {debut.strftime('%d/%m/%Y')} au {fin.strftime('%d/%m/%Y')}", blocs, paysage=True)
        journal.enregistrer(
            request, 'impression', 'impression',
            f"{journal.acteur(request.user)} a imprimé le rapport financier du "
            f"{debut.strftime('%d/%m/%Y')} au {fin.strftime('%d/%m/%Y')}.")
        return reponse_pdf(octets, 'rapport-financier.pdf', request.data.get('telecharger'))


class PdfEtatSalairesView(APIView):
    """État des salaires payés pour un mois (ou une période de paiement).
    Corps : {mois: 'AAAA-MM'} (mois payé) ou {date_debut, date_fin} (dates de paiement)."""
    permission_classes = [IsAdmin]

    def post(self, request):
        data = request.data
        qs = PaieSalaire.objects.filter(annule=False).prefetch_related('lignes')
        if data.get('mois'):
            mois = services.lire_mois(data['mois'])
            qs = qs.filter(lignes__mois=mois).distinct()
            titre_periode = libelle_mois(mois)
        else:
            debut, fin = periode(request)
            qs = qs.filter(date__range=(debut, fin))
            titre_periode = f"paiements du {debut.strftime('%d/%m/%Y')} au {fin.strftime('%d/%m/%Y')}"
        liste = list(qs.order_by('employe_nom', 'date'))
        lignes = [[p.employe_nom, p.poste, ', '.join(libelle_mois(l.mois) for l in p.lignes.all()) or 'Exceptionnel',
                   argent(p.montant_brut), argent(p.retenue_avances + p.autres_retenues), argent(p.net_paye), p.numero]
                  for p in liste]
        brut = sum((p.montant_brut for p in liste), services.ZERO)
        ret = sum((p.retenue_avances + p.autres_retenues for p in liste), services.ZERO)
        net = sum((p.net_paye for p in liste), services.ZERO)
        octets = pdf.document_pdf(
            _etablissement(), 'État des salaires', titre_periode.capitalize(),
            [('tableau', ['Employé', 'Poste', 'Mois payés', 'Brut', 'Retenues', 'Net payé', 'N°'], lignes,
              [2.4, 1.6, 3, 1.5, 1.5, 1.5, 1.5], ['L', 'L', 'L', 'R', 'R', 'R', 'L'],
              ['TOTAL', f"{len(liste)} paie(s)", '', argent(brut), argent(ret), argent(net), ''] if lignes else None)],
            paysage=True)
        journal.enregistrer(
            request, 'impression', 'impression',
            f"{journal.acteur(request.user)} a imprimé l'état des salaires ({titre_periode}).")
        return reponse_pdf(octets, 'etat-salaires.pdf', data.get('telecharger'))


class ImpressionsView(APIView):
    """Catalogue de TOUTES les impressions de l'application (élèves et finances), pour l'écran
    unique « Impressions » : où les appeler et avec quels paramètres."""
    permission_classes = [IsAdmin]

    def get(self, request):
        base_eleves = "inscriptions: [ids] | classes: [ids] | classe: id | annee: id, ordre: alpha|numero"
        return Response({'groupes': [
            {'cle': 'eleves', 'titre': 'Élèves et scolarité', 'documents': [
                {'cle': 'cartes', 'libelle': "Cartes d'élève", 'methode': 'POST',
                 'url': '/api/school/pdf/cartes/', 'parametres': base_eleves},
                {'cle': 'bulletins', 'libelle': 'Bulletins', 'methode': 'POST',
                 'url': '/api/school/pdf/bulletins/', 'parametres': base_eleves + ', trimestre: 1|2|3'},
                {'cle': 'certificats', 'libelle': 'Certificats de scolarité', 'methode': 'POST',
                 'url': '/api/school/pdf/certificats/', 'parametres': base_eleves},
                {'cle': 'fiches_appel', 'libelle': "Fiches d'appel", 'methode': 'POST',
                 'url': '/api/school/pdf/fiches-appel/', 'parametres': "classes: [ids] | annee: id, semaine: AAAA-MM-JJ"},
            ]},
            {'cle': 'finances', 'titre': 'Finances', 'documents': [
                {'cle': 'cartes_ecolage', 'libelle': "Cartes d'écolage (suivi mensuel)", 'methode': 'POST',
                 'url': '/api/finance/pdf/cartes-ecolage/', 'parametres': base_eleves},
                {'cle': 'recu', 'libelle': 'Reçu de paiement', 'methode': 'GET',
                 'url': '/api/finance/paiements/<id>/recu/', 'parametres': 'telecharger=1 (facultatif)'},
                {'cle': 'impayes', 'libelle': 'Liste des impayés', 'methode': 'POST',
                 'url': '/api/finance/pdf/impayes/', 'parametres': "annee: id, classes: [ids], au: AAAA-MM"},
                {'cle': 'rapport', 'libelle': 'Rapport financier (bilan + journal de caisse)', 'methode': 'POST',
                 'url': '/api/finance/pdf/rapport/', 'parametres': "annee: id | date_debut, date_fin"},
                {'cle': 'fiche_paie', 'libelle': 'Fiche de paie', 'methode': 'GET',
                 'url': '/api/finance/salaires/<id>/fiche/', 'parametres': 'telecharger=1 (facultatif)'},
                {'cle': 'etat_salaires', 'libelle': 'État des salaires', 'methode': 'POST',
                 'url': '/api/finance/pdf/etat-salaires/', 'parametres': "mois: AAAA-MM | date_debut, date_fin"},
            ]},
        ]})

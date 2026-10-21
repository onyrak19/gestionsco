"""Logique métier des finances : mois de l'année, montants automatiques, paiements,
salaires, avances et retenues. Aucune vue ici : les vues appellent ces fonctions.

Les erreurs destinées à l'utilisateur sont des `ValidationError` (réponse 400).
"""
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .outils import MOIS_FR, libelle_mois, mois_cle, montant_fr  # noqa: F401
from .models import (
    AvanceSalaire, LignePaie, LignePaiement, Paiement, PaieSalaire, RetenueAvance, Tarif,
)

ZERO = Decimal('0.00')


# ---------------------------------------------------------------------------
# Nombres et dates
# ---------------------------------------------------------------------------
def dec(valeur, nom='montant'):
    """Décimal à 2 chiffres (virgule ou point acceptés) ; ValidationError si invalide."""
    if isinstance(valeur, Decimal):
        d = valeur
    else:
        try:
            d = Decimal(str(valeur).strip().replace(',', '.').replace(' ', ''))
        except (InvalidOperation, AttributeError):
            raise ValidationError({nom: 'Doit être un nombre.'})
    if not d.is_finite():
        raise ValidationError({nom: 'Doit être un nombre.'})
    return d.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def num(valeur):
    """Nombre JSON (float) à partir d'un Decimal ; None reste None."""
    return None if valeur is None else float(valeur)


def aujourd_hui():
    return timezone.localdate()


def premier_du_mois(d):
    return d.replace(day=1)


def mois_suivant(d):
    return (d.replace(day=28) + timedelta(days=4)).replace(day=1)


def lire_mois(valeur, nom='mois'):
    """'2026-09', '2026-09-15' ou une date -> premier jour du mois."""
    if isinstance(valeur, date):
        return premier_du_mois(valeur)
    texte = str(valeur or '').strip()
    try:
        annee, mois = int(texte[:4]), int(texte[5:7])
        return date(annee, mois, 1)
    except (ValueError, IndexError):
        raise ValidationError({nom: f"Mois invalide : « {texte} » (format AAAA-MM, ex. 2026-09)."})


def lire_mois_liste(valeurs, nom='mois'):
    if valeurs is None:
        return []
    if not isinstance(valeurs, (list, tuple)):
        raise ValidationError({nom: 'Doit être une liste de mois (ex. ["2026-09", "2026-10"]).'})
    return sorted({lire_mois(v, nom) for v in valeurs})


def mois_de_l_annee(annee):
    """Les mois de l'année scolaire, du mois de début au mois de fin (ex. sept. → juin)."""
    mois, d, fin = [], premier_du_mois(annee.date_debut), premier_du_mois(annee.date_fin)
    while d <= fin and len(mois) < 24:
        mois.append(d)
        d = mois_suivant(d)
    return mois


def prochain_numero(prefixe, modele):
    dernier = (modele.objects.filter(numero__startswith=prefixe)
               .order_by('-numero').values_list('numero', flat=True).first())
    suite = int(dernier[len(prefixe):]) + 1 if dernier else 1
    return f"{prefixe}{suite:05d}"


def creer_avec_numero(modele, prefixe, **champs):
    """Crée l'objet avec un numéro de reçu unique (nouvel essai si deux saisies simultanées)."""
    for _essai in range(6):
        try:
            with transaction.atomic():
                return modele.objects.create(numero=prochain_numero(prefixe, modele), **champs)
        except IntegrityError:
            continue
    raise ValidationError("Impossible d'attribuer un numéro de reçu : réessayez.")


# ---------------------------------------------------------------------------
# Tarifs d'un niveau
# ---------------------------------------------------------------------------
def verifier_niveau(classe):
    if not classe.niveau:
        raise ValidationError(
            f"La classe « {classe.nom} » n'a pas de niveau : modifiez-la (écran Classes) "
            f"pour choisir son niveau, afin que les tarifs puissent s'appliquer.")


def tarifs_du_niveau(annee_id, niveau, serie):
    """{'droit': Tarif|None, 'ecolage': Tarif|None, 'autres': [Tarif...]}"""
    resultat = {'droit': None, 'ecolage': None, 'autres': []}
    for t in Tarif.objects.filter(annee_scolaire_id=annee_id, niveau=niveau, serie=serie):
        if t.type == 'autre':
            resultat['autres'].append(t)
        else:
            resultat[t.type] = t
    return resultat


def tarifs_de_l_inscription(ins):
    return tarifs_du_niveau(ins.annee_scolaire_id, ins.classe.niveau, ins.classe.serie)


def _lignes_actives(inscription_ids):
    return (LignePaiement.objects
            .filter(paiement__inscription_id__in=inscription_ids, paiement__annule=False)
            .select_related('paiement'))


# ---------------------------------------------------------------------------
# Situation financière d'un élève
# ---------------------------------------------------------------------------
def calculer_situation(ins, tarifs, lignes, mois_reference=None):
    """Situation d'une inscription : droit, écolage mois par mois, autres frais, totaux.

    `lignes` : lignes de paiement non annulées de cette inscription (avec `paiement`)."""
    mois_reference = mois_reference or premier_du_mois(aujourd_hui())
    tarif_droit, tarif_ecolage = tarifs['droit'], tarifs['ecolage']

    ecolage_paye, droit_ligne, autres_lignes = {}, None, {}
    for l in lignes:
        t = l.paiement.type
        if t == 'ecolage' and l.mois:
            ecolage_paye[l.mois] = l
        elif t == 'droit':
            droit_ligne = l
        elif t == 'autre':
            autres_lignes[l.tarif_id] = l

    def infos_paiement(l):
        return {'paiement': l.paiement_id, 'numero_recu': l.paiement.numero,
                'date_paiement': l.paiement.date.isoformat()}

    # Droit d'inscription
    droit = {'tarif': tarif_droit.id if tarif_droit else None,
             'montant': num(droit_ligne.montant if droit_ligne else (tarif_droit.montant if tarif_droit else None)),
             'paye': droit_ligne is not None, 'paiement': None, 'numero_recu': None, 'date_paiement': None}
    if droit_ligne:
        droit.update(infos_paiement(droit_ligne))

    # Écolage mois par mois
    mois_liste, paye_total, du_total, annee_total = [], ZERO, ZERO, ZERO
    nb_payes = nb_impayes = 0
    for m in mois_de_l_annee(ins.annee_scolaire):
        ligne = ecolage_paye.get(m)
        if ligne is not None:
            statut, montant = 'paye', ligne.montant
            nb_payes += 1
            paye_total += montant
            annee_total += montant
        elif tarif_ecolage is None:
            statut, montant = 'non_defini', None
        else:
            montant = tarif_ecolage.montant
            annee_total += montant
            if m <= mois_reference:
                statut = 'impaye'
                nb_impayes += 1
                du_total += montant
            else:
                statut = 'a_venir'
        entree = {'mois': mois_cle(m), 'libelle': libelle_mois(m), 'montant': num(montant), 'statut': statut,
                  'paiement': None, 'numero_recu': None, 'date_paiement': None}
        if ligne is not None:
            entree.update(infos_paiement(ligne))
        mois_liste.append(entree)

    # Autres frais (facultatifs : non comptés dans « dû à ce jour »)
    autres = []
    for t in tarifs['autres']:
        l = autres_lignes.get(t.id)
        entree = {'tarif': t.id, 'libelle': t.libelle, 'montant': num(l.montant if l else t.montant),
                  'paye': l is not None, 'paiement': None, 'numero_recu': None, 'date_paiement': None}
        if l:
            entree.update(infos_paiement(l))
        autres.append(entree)

    droit_du = ZERO if droit_ligne or tarif_droit is None else tarif_droit.montant
    paye_droit = droit_ligne.montant if droit_ligne else ZERO
    paye_autres = sum((l.montant for l in autres_lignes.values()), ZERO)
    return {
        'inscription': ins.id,
        'annee': ins.annee_scolaire.libelle,
        'tarif_defini': tarif_droit is not None or tarif_ecolage is not None,
        'droit': droit,
        'ecolage': {
            'mensuel': num(tarif_ecolage.montant) if tarif_ecolage else None,
            'mois': mois_liste, 'nb_payes': nb_payes, 'nb_impayes': nb_impayes,
            'montant_paye': num(paye_total), 'montant_du': num(du_total),
        },
        'autres': autres,
        'total_paye': num(paye_total + paye_droit + paye_autres),
        'du_a_ce_jour': num(du_total + droit_du),
        'reste_annee': num((annee_total - paye_total) + droit_du),
    }


def situations_pour(inscriptions, mois_reference=None):
    """Situation de plusieurs inscriptions (peu de requêtes) : [(inscription, situation)].
    Les inscriptions doivent venir avec select_related('classe', 'annee_scolaire', 'eleve')."""
    inscriptions = list(inscriptions)
    par_inscription = {}
    for l in _lignes_actives([i.id for i in inscriptions]):
        par_inscription.setdefault(l.paiement.inscription_id, []).append(l)
    vide = {'droit': None, 'ecolage': None, 'autres': []}
    cache, resultat = {}, []
    for ins in inscriptions:
        cle = (ins.annee_scolaire_id, ins.classe.niveau, ins.classe.serie)
        if cle not in cache:
            cache[cle] = tarifs_du_niveau(*cle) if ins.classe.niveau else vide
        resultat.append((ins, calculer_situation(ins, cache[cle], par_inscription.get(ins.id, []), mois_reference)))
    return resultat


def situation_eleve(ins):
    # La situation s'affiche même si la classe n'a pas de niveau (aucun tarif applicable)
    tarifs = tarifs_de_l_inscription(ins) if ins.classe.niveau else {'droit': None, 'ecolage': None, 'autres': []}
    return calculer_situation(ins, tarifs, list(_lignes_actives([ins.id])))


# ---------------------------------------------------------------------------
# Paiements d'élèves
# ---------------------------------------------------------------------------
def preparer_paiement(ins, type_, mois=None, tarif_id=None):
    """Calcule les lignes d'un paiement SANS rien enregistrer. Le montant vient toujours
    du tarif du niveau de l'élève. Retourne (lignes, total) ; lignes = [dict]."""
    if type_ not in dict(Paiement.TYPES):
        raise ValidationError({'type': "Type de paiement invalide (droit, ecolage ou autre)."})
    classe = ins.classe
    verifier_niveau(classe)
    tarifs = tarifs_de_l_inscription(ins)
    niveau_txt = f"{classe.niveau} {classe.serie}".strip()
    deja = LignePaiement.objects.filter(paiement__inscription=ins, paiement__annule=False)

    if type_ == 'droit':
        tarif = tarifs['droit']
        if tarif is None:
            raise ValidationError(
                f"Le droit d'inscription n'est pas défini pour {niveau_txt} ({ins.annee_scolaire.libelle}) : "
                f"définissez-le dans Finances › Tarifs.")
        if deja.filter(paiement__type='droit').exists():
            raise ValidationError("Le droit d'inscription de cet élève est déjà payé.")
        lignes = [{'libelle': "Droit d'inscription", 'mois': None, 'montant': tarif.montant, 'tarif': tarif}]

    elif type_ == 'ecolage':
        tarif = tarifs['ecolage']
        if tarif is None:
            raise ValidationError(
                f"L'écolage n'est pas défini pour {niveau_txt} ({ins.annee_scolaire.libelle}) : "
                f"définissez-le dans Finances › Tarifs.")
        demandes = lire_mois_liste(mois)
        if not demandes:
            raise ValidationError({'mois': "Choisissez au moins un mois à payer."})
        valides = set(mois_de_l_annee(ins.annee_scolaire))
        hors = [libelle_mois(m) for m in demandes if m not in valides]
        if hors:
            raise ValidationError({'mois': f"Hors de l'année scolaire {ins.annee_scolaire.libelle} : {', '.join(hors)}."})
        payes = set(deja.filter(paiement__type='ecolage', mois__in=demandes).values_list('mois', flat=True))
        if payes:
            raise ValidationError(
                {'mois': "Déjà payé : " + ', '.join(libelle_mois(m) for m in sorted(payes)) + '.'})
        lignes = [{'libelle': f"Écolage {libelle_mois(m)}", 'mois': m, 'montant': tarif.montant, 'tarif': tarif}
                  for m in demandes]

    else:
        if not tarif_id:
            raise ValidationError({'tarif': "Choisissez le frais à encaisser."})
        try:
            tarif = next(t for t in tarifs['autres'] if t.id == int(tarif_id))
        except (StopIteration, TypeError, ValueError):
            raise ValidationError({'tarif': f"Ce frais n'est pas défini pour {niveau_txt}."})
        if deja.filter(paiement__type='autre', tarif=tarif).exists():
            raise ValidationError(f"« {tarif.libelle} » est déjà payé pour cet élève.")
        lignes = [{'libelle': tarif.libelle or 'Autre frais', 'mois': None, 'montant': tarif.montant, 'tarif': tarif}]

    return lignes, sum((l['montant'] for l in lignes), ZERO)


def creer_paiement(ins, type_, mois=None, tarif_id=None, date_paiement=None, mode='especes',
                   reference='', observation='', user=None):
    with transaction.atomic():
        lignes, total = preparer_paiement(ins, type_, mois, tarif_id)
        date_paiement = date_paiement or aujourd_hui()
        eleve = ins.eleve
        paiement = creer_avec_numero(
            Paiement, f"REC-{date_paiement.year}-",
            inscription=ins, annee_scolaire=ins.annee_scolaire,
            eleve_nom=eleve.nom_complet, matricule=eleve.matricule or '',
            classe_nom=ins.classe.nom, annee_libelle=ins.annee_scolaire.libelle,
            type=type_, date=date_paiement, mode=mode, reference=reference[:100],
            observation=observation[:255], montant_total=total,
            saisi_par=user if getattr(user, 'pk', None) else None,
        )
        for l in lignes:
            LignePaiement.objects.create(
                paiement=paiement, libelle=l['libelle'], mois=l['mois'], tarif=l['tarif'], montant=l['montant'])
    return paiement


def annuler_paiement(paiement, motif, user):
    if paiement.annule:
        raise ValidationError("Ce paiement est déjà annulé.")
    if not (motif or '').strip():
        raise ValidationError({'motif': "Indiquez le motif de l'annulation."})
    paiement.annule = True
    paiement.motif_annulation = motif.strip()[:255]
    paiement.annule_par = user if getattr(user, 'pk', None) else None
    paiement.annule_le = timezone.now()
    paiement.save(update_fields=['annule', 'motif_annulation', 'annule_par', 'annule_le'])
    return paiement


# ---------------------------------------------------------------------------
# Salaires
# ---------------------------------------------------------------------------
def avances_en_cours(employe):
    """[(avance, reste à retenir)] des avances non annulées pas encore entièrement retenues."""
    avances = list(AvanceSalaire.objects.filter(employe=employe, annulee=False).order_by('date', 'id'))
    if not avances:
        return []
    retenu = {r['avance']: r['t'] for r in
              RetenueAvance.objects.filter(avance__in=avances, paie__annule=False)
              .values('avance').annotate(t=Sum('montant')).order_by()}
    resultat = []
    for a in avances:
        reste = a.montant - (retenu.get(a.id) or ZERO)
        if reste > 0:
            resultat.append((a, reste))
    return resultat


def total_avances_en_cours(employe):
    return sum((reste for _a, reste in avances_en_cours(employe)), ZERO)


def mois_deja_payes(employe, mois=None):
    qs = LignePaie.objects.filter(paie__employe=employe, paie__annule=False)
    if mois is not None:
        qs = qs.filter(mois__in=mois)
    return set(qs.values_list('mois', flat=True))


def preparer_salaire(employe, mois, exceptionnel=False, montant_exceptionnel=None,
                     motif_exceptionnel='', retenue_avance=None, autres_retenues=0, motif_retenues=''):
    """Calcule une paie SANS rien enregistrer.

    * Normal : brut = salaire mensuel × nombre de mois (montant automatique).
    * Exceptionnel : le brut est le montant saisi, le motif est obligatoire.
    * Retenue d'avance : automatique (tout ce qui est dû, dans la limite de la paie) sauf si une
      valeur est donnée.
    Retourne un dict (brut, retenue_avance, autres_retenues, net, mois, repartition...)."""
    mois = lire_mois_liste(mois)
    motif_exceptionnel = (motif_exceptionnel or '').strip()
    motif_retenues = (motif_retenues or '').strip()

    if exceptionnel:
        if not motif_exceptionnel:
            raise ValidationError({'motif_exceptionnel': "Indiquez le motif de cette situation exceptionnelle."})
        if montant_exceptionnel in (None, ''):
            raise ValidationError({'montant_exceptionnel': "Indiquez le montant à payer."})
        brut = dec(montant_exceptionnel, 'montant_exceptionnel')
        if brut < 0:
            raise ValidationError({'montant_exceptionnel': "Le montant ne peut pas être négatif."})
    else:
        if not mois:
            raise ValidationError({'mois': "Choisissez au moins un mois à payer."})
        if employe.salaire_mensuel is None or employe.salaire_mensuel <= 0:
            raise ValidationError(
                f"Aucun salaire n'est défini pour {employe.nom_complet} : renseignez-le sur sa fiche employé.")
        brut = employe.salaire_mensuel * len(mois)

    deja = mois_deja_payes(employe, mois) if mois else set()
    if deja:
        raise ValidationError({'mois': "Déjà payé : " + ', '.join(libelle_mois(m) for m in sorted(deja)) + '.'})

    autres = dec(autres_retenues or 0, 'autres_retenues')
    if autres < 0:
        raise ValidationError({'autres_retenues': "La retenue ne peut pas être négative."})
    if autres > 0 and not motif_retenues:
        raise ValidationError({'motif_retenues': "Indiquez le motif de la retenue (ex. pénalité)."})
    if autres > brut:
        raise ValidationError({'autres_retenues': "Les retenues dépassent le montant à payer."})

    en_cours = avances_en_cours(employe)
    disponible = sum((reste for _a, reste in en_cours), ZERO)
    maximum = brut - autres
    if retenue_avance in (None, ''):
        retenue = min(disponible, maximum)
    else:
        retenue = dec(retenue_avance, 'retenue_avance')
        if retenue < 0:
            raise ValidationError({'retenue_avance': "La retenue ne peut pas être négative."})
        if retenue > disponible:
            raise ValidationError({'retenue_avance': f"Cet employé n'a que {montant_fr(disponible)} d'avances à rembourser."})
        if retenue > maximum:
            raise ValidationError({'retenue_avance': "La retenue dépasse le montant à payer."})

    repartition, reste_a_retenir = [], retenue
    for avance, reste in en_cours:             # les plus anciennes avances d'abord
        if reste_a_retenir <= 0:
            break
        part = min(reste, reste_a_retenir)
        repartition.append((avance, part))
        reste_a_retenir -= part

    return {
        'mois': mois, 'exceptionnel': bool(exceptionnel), 'motif_exceptionnel': motif_exceptionnel,
        'salaire_mensuel': employe.salaire_mensuel, 'brut': brut,
        'retenue_avance': retenue, 'autres_retenues': autres, 'motif_retenues': motif_retenues,
        'net': brut - retenue - autres, 'repartition': repartition, 'avances_disponibles': disponible,
    }


def creer_salaire(employe, prepare, date_paiement=None, mode='especes', observation='', user=None):
    with transaction.atomic():
        date_paiement = date_paiement or aujourd_hui()
        paie = creer_avec_numero(
            PaieSalaire, f"SAL-{date_paiement.year}-",
            employe=employe, employe_nom=employe.nom_complet, poste=employe.poste,
            date=date_paiement, mode=mode, salaire_mensuel=prepare['salaire_mensuel'],
            montant_brut=prepare['brut'], retenue_avances=prepare['retenue_avance'],
            autres_retenues=prepare['autres_retenues'], motif_retenues=prepare['motif_retenues'][:255],
            net_paye=prepare['net'], exceptionnel=prepare['exceptionnel'],
            motif_exceptionnel=prepare['motif_exceptionnel'][:255], observation=observation[:255],
            saisi_par=user if getattr(user, 'pk', None) else None,
        )
        for m in prepare['mois']:
            LignePaie.objects.create(
                paie=paie, mois=m, montant=ZERO if prepare['exceptionnel'] else prepare['salaire_mensuel'])
        for avance, part in prepare['repartition']:
            RetenueAvance.objects.create(paie=paie, avance=avance, montant=part)
    return paie


def annuler_salaire(paie, motif, user):
    if paie.annule:
        raise ValidationError("Cette paie est déjà annulée.")
    if not (motif or '').strip():
        raise ValidationError({'motif': "Indiquez le motif de l'annulation."})
    paie.annule = True
    paie.motif_annulation = motif.strip()[:255]
    paie.annule_par = user if getattr(user, 'pk', None) else None
    paie.annule_le = timezone.now()
    paie.save(update_fields=['annule', 'motif_annulation', 'annule_par', 'annule_le'])
    return paie          # les avances retenues redeviennent dues automatiquement


def payer_groupe(employes, mois, date_paiement, mode, retenues=None, appliquer=False, user=None):
    """Paie plusieurs employés en une fois, pour les mêmes mois.

    Pour chaque employé : montant automatique, mois déjà payés ignorés, avances retenues
    automatiquement ; `retenues` = {id employé: {'montant': .., 'motif': ..}} pour une retenue
    supplémentaire (pénalité...). Une erreur sur un employé n'empêche pas les autres.
    appliquer=False : simple aperçu."""
    retenues = retenues or {}
    mois = lire_mois_liste(mois)
    if not mois:
        raise ValidationError({'mois': "Choisissez au moins un mois à payer."})
    resultats, total_net, total_brut = [], ZERO, ZERO
    for emp in employes:
        item = {'employe': emp.id, 'nom': emp.nom_complet, 'poste': emp.poste, 'statut': '',
                'mois': [], 'brut': 0.0, 'retenue_avance': 0.0, 'autres_retenues': 0.0, 'net': 0.0,
                'message': '', 'paie': None, 'numero': None}
        try:
            payes = mois_deja_payes(emp, mois)
            a_payer = [m for m in mois if m not in payes]
            if not a_payer:
                item.update(statut='deja_paye', message='Tous ces mois sont déjà payés.')
            else:
                extra = retenues.get(emp.id) or retenues.get(str(emp.id)) or {}
                prepare = preparer_salaire(
                    emp, a_payer, autres_retenues=extra.get('montant') or 0, motif_retenues=extra.get('motif') or '')
                item.update(mois=[mois_cle(m) for m in a_payer], brut=num(prepare['brut']),
                            retenue_avance=num(prepare['retenue_avance']),
                            autres_retenues=num(prepare['autres_retenues']), net=num(prepare['net']))
                if len(a_payer) < len(mois):
                    item['message'] = 'Certains mois étaient déjà payés : ils sont ignorés.'
                if appliquer:
                    paie = creer_salaire(emp, prepare, date_paiement, mode, user=user)
                    item.update(statut='paye', paie=paie.id, numero=paie.numero)
                else:
                    item['statut'] = 'a_payer'
                total_brut += prepare['brut']
                total_net += prepare['net']
        except ValidationError as exc:
            item.update(statut='erreur', message=_texte_erreur(exc))
        resultats.append(item)
    return resultats, total_brut, total_net


def _texte_erreur(exc):
    detail = exc.detail
    morceaux = []

    def aplatir(d):
        if isinstance(d, dict):
            for v in d.values():
                aplatir(v)
        elif isinstance(d, (list, tuple)):
            for v in d:
                aplatir(v)
        else:
            morceaux.append(str(d))
    aplatir(detail)
    return ' '.join(morceaux)

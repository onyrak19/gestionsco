"""Données financières dans l'écran « Import / Export » (Excel).

Ces jeux s'ajoutent à ceux de `school/export_import.py` au démarrage (voir `apps.py`).
Chaque ligne importée passe par les MÊMES règles que la saisie à l'écran : les montants
des paiements viennent toujours des tarifs, les doublons sont ignorés.
"""
from django.db.models import Count

from school import excel_outils as xo
from school import export_import as ei
from school.models import Inscription

from . import services
from .models import (
    AvanceSalaire, CategorieFinance, Employe, LignePaiement, MODES_PAIEMENT, Mouvement, PaieSalaire, Paiement, Tarif,
)
from .outils import libelle_mois
from .serializers import EmployeSerializer, MouvementSerializer

ErreurLigne = ei.ErreurLigne
TYPES_TARIF = dict(Tarif.TYPES)
SENS = dict(CategorieFinance.SENS)


def _oui(valeur):
    return 'Oui' if valeur else 'Non'


def _num(valeur):
    return None if valeur is None else float(valeur)


def _par_libelle(choix, valeur, nom):
    """'Écolage' / 'ecolage' -> 'ecolage' (clé ou libellé, sans accents ni majuscules)."""
    t = xo.normaliser(valeur)
    for cle, libelle in choix.items() if isinstance(choix, dict) else choix:
        if t in (xo.normaliser(cle), xo.normaliser(libelle)):
            return cle
    raise ErreurLigne(f"{nom} : « {xo.texte(valeur)} » non reconnu.")


def _sens(valeur):
    t = xo.normaliser(valeur)
    if t.startswith('depense') or t in ('sortie', 'd'):
        return 'depense'
    if t.startswith('entree') or t in ('recette', 'e'):
        return 'entree'
    raise ErreurLigne(f"Sens : « {xo.texte(valeur)} » non reconnu (écrivez Dépense ou Entrée).")


def _booleen(valeur, defaut=False):
    t = xo.normaliser(valeur)
    if t == '':
        return defaut
    return t in ('oui', 'o', 'true', '1', 'x', 'yes')


# ===========================================================================
# EXPORT
# ===========================================================================
class JeuTarifs(ei.Jeu):
    cle, libelle, importable = 'tarifs', 'Tarifs', True
    description = "Droits d'inscription, écolages mensuels et autres frais, par niveau et par année."
    colonnes = ('Année scolaire', 'Niveau', 'Série', 'Type', 'Libellé', 'Montant')

    def queryset(self, f):
        qs = Tarif.objects.select_related('annee_scolaire')
        if f.annee:
            qs = qs.filter(annee_scolaire_id=f.annee)
        return qs.order_by('annee_scolaire__date_debut', 'niveau', 'serie', 'type', 'libelle')

    def lignes(self, f):
        for t in self.queryset(f):
            yield [t.annee_scolaire.libelle, t.niveau, t.serie, t.get_type_display(), t.libelle, _num(t.montant)]


class JeuCategories(ei.Jeu):
    cle, libelle, importable = 'categories_finance', 'Catégories (finances)', True
    description = "Catégories de dépenses et d'entrées d'argent."
    colonnes = ('Nom', 'Sens', 'Active', 'Utilisations')

    def queryset(self, f):
        return CategorieFinance.objects.annotate(nb=Count('mouvements')).order_by('sens', 'nom')

    def lignes(self, f):
        for c in self.queryset(f):
            yield [c.nom, c.get_sens_display(), _oui(c.actif), c.nb]


class JeuMouvements(ei.Jeu):
    cle, libelle, importable = 'mouvements', 'Dépenses et entrées', True
    description = "Dépenses, imprévus et entrées d'argent (hors scolarité des élèves)."
    colonnes = ('Date', 'Sens', 'Catégorie', 'Libellé', 'Montant', 'Imprévu', 'Référence', 'Notes')

    def queryset(self, f):
        qs = Mouvement.objects.select_related('categorie')
        if f.annee:
            a = ei.AnneeScolaire.objects.filter(pk=f.annee).first()
            if a:
                qs = qs.filter(date__range=(a.date_debut, a.date_fin))
        return qs.order_by('date', 'id')

    def lignes(self, f):
        for m in self.queryset(f):
            yield [m.date, m.categorie.get_sens_display(), m.categorie.nom, m.libelle, _num(m.montant),
                   _oui(m.imprevu), m.reference, m.notes]


class JeuPaiements(ei.Jeu):
    cle, libelle, importable = 'paiements', 'Paiements élèves', True
    description = "Tous les encaissements d'élèves (une ligne par mois d'écolage, droit ou frais), reçus annulés inclus."
    colonnes = ('N° reçu', 'Date', 'Année scolaire', 'Classe', 'N°', 'Matricule', 'Nom', 'Prénom', 'Type',
                'Désignation', 'Mois', 'Montant', 'Mode', 'Référence', 'Statut')

    def queryset(self, f):
        qs = LignePaiement.objects.select_related(
            'paiement', 'paiement__inscription__eleve', 'paiement__annee_scolaire')
        if f.annee:
            qs = qs.filter(paiement__annee_scolaire_id=f.annee)
        if f.classes:
            qs = qs.filter(paiement__inscription__classe_id__in=f.classes)
        return qs.order_by('paiement__date', 'paiement_id', 'mois', 'id')

    def lignes(self, f):
        for l in self.queryset(f):
            p, ins = l.paiement, l.paiement.inscription
            nom, prenom, numero = (ins.eleve.nom, ins.eleve.prenom, ins.numero) if ins else (p.eleve_nom, '', None)
            yield [p.numero, p.date, p.annee_libelle, p.classe_nom, numero, p.matricule, nom, prenom,
                   p.get_type_display(), l.libelle, services.mois_cle(l.mois) if l.mois else '',
                   _num(l.montant), p.get_mode_display(), p.reference, 'Annulé' if p.annule else 'Valide']


class JeuEmployes(ei.Jeu):
    cle, libelle, importable = 'employes', 'Employés', True
    description = "Les employés (enseignants et personnel) avec leur salaire mensuel."
    colonnes = ('Nom', 'Prénom', 'Poste', 'Téléphone', 'Salaire mensuel', "Date d'embauche", 'Actif')

    def queryset(self, f):
        return Employe.objects.order_by('nom', 'prenom')

    def lignes(self, f):
        for e in self.queryset(f):
            yield [e.nom, e.prenom, e.poste, e.telephone, _num(e.salaire_mensuel), e.date_embauche, _oui(e.actif)]


class JeuSalaires(ei.Jeu):
    cle, libelle = 'salaires', 'Salaires payés'
    description = "Toutes les paies : mois payés, brut, retenues (avances, pénalités), net, situations exceptionnelles."
    colonnes = ('N°', 'Date', 'Employé', 'Poste', 'Mois payés', 'Brut', 'Retenue avances', 'Autres retenues',
                'Motif retenues', 'Net payé', 'Exceptionnel', 'Motif exceptionnel', 'Mode', 'Statut')

    def queryset(self, f):
        qs = PaieSalaire.objects.prefetch_related('lignes')
        if f.annee:
            a = ei.AnneeScolaire.objects.filter(pk=f.annee).first()
            if a:
                qs = qs.filter(date__range=(a.date_debut, a.date_fin))
        return qs.order_by('date', 'id')

    def lignes(self, f):
        for p in self.queryset(f):
            yield [p.numero, p.date, p.employe_nom, p.poste, ', '.join(libelle_mois(l.mois) for l in p.lignes.all()),
                   _num(p.montant_brut), _num(p.retenue_avances), _num(p.autres_retenues), p.motif_retenues,
                   _num(p.net_paye), _oui(p.exceptionnel), p.motif_exceptionnel, p.get_mode_display(),
                   'Annulée' if p.annule else 'Valide']


class JeuAvances(ei.Jeu):
    cle, libelle = 'avances', 'Avances sur salaire'
    description = "Les avances données aux employés et ce qu'il reste à retenir."
    colonnes = ('Date', 'Employé', 'Montant', 'Motif', 'Reste à retenir', 'Statut')

    def queryset(self, f):
        return AvanceSalaire.objects.select_related('employe').order_by('date', 'id')

    def lignes(self, f):
        dues = {}
        for emp_id in set(self.queryset(f).values_list('employe_id', flat=True)):
            emp = Employe.objects.get(pk=emp_id)
            for avance, reste in services.avances_en_cours(emp):
                dues[avance.id] = reste
        for a in self.queryset(f):
            yield [a.date, a.employe.nom_complet, _num(a.montant), a.motif,
                   _num(dues.get(a.id, 0)), 'Annulée' if a.annulee else 'Valide']


# ===========================================================================
# IMPORT
# ===========================================================================
def _importer_tarifs(ctx, row):
    annee = ctx.annee(ei._txt(row, 'annee'))
    if annee.cloturee:
        raise ErreurLigne(f"L'année {annee.libelle} est clôturée : tarifs figés.")
    niveau, serie = ei._txt(row, 'niveau'), ei._txt(row, 'serie').upper()
    if not niveau:
        raise ErreurLigne("Niveau : valeur manquante.")
    type_ = _par_libelle(TYPES_TARIF, ei._champ(row, 'type'), 'Type')
    libelle = ei._txt(row, 'libelle') if type_ == 'autre' else ''
    if type_ == 'autre' and not libelle:
        raise ErreurLigne("Libellé : obligatoire pour un « Autre frais ».")
    montant = xo.nombre_decimal(ei._champ(row, 'montant'), 'Montant')
    if montant is None or montant < 0:
        raise ErreurLigne("Montant : un nombre positif est obligatoire.")
    montant = services.dec(montant)
    existant = Tarif.objects.filter(annee_scolaire=annee, niveau=niveau, serie=serie, type=type_, libelle=libelle).first()
    if existant:
        if existant.montant == montant:
            return 'ignore'
        existant.montant = montant
        existant.save(update_fields=['montant'])
        return 'maj'
    Tarif.objects.create(annee_scolaire=annee, niveau=niveau, serie=serie, type=type_, libelle=libelle, montant=montant)
    return 'cree'


def _categorie(sens, nom, creer=True):
    existante = CategorieFinance.objects.filter(sens=sens, nom__iexact=nom).first()
    if existante or not creer:
        return existante
    return CategorieFinance.objects.create(sens=sens, nom=nom)


def _importer_categories(ctx, row):
    nom = ei._txt(row, 'nom')
    if not nom:
        raise ErreurLigne("Nom : obligatoire.")
    sens = _sens(ei._champ(row, 'sens'))
    actif = _booleen(ei._champ(row, 'active'), True)
    existante = _categorie(sens, nom, creer=False)
    if existante:
        if existante.actif == actif:
            return 'ignore'
        existante.actif = actif
        existante.save(update_fields=['actif'])
        return 'maj'
    CategorieFinance.objects.create(sens=sens, nom=nom, actif=actif)
    return 'cree'


def _importer_mouvements(ctx, row):
    jour = xo.analyser_date(ei._champ(row, 'date'), 'Date')
    if jour is None:
        raise ErreurLigne("Date : obligatoire.")
    sens = _sens(ei._champ(row, 'sens'))
    nom_cat = ei._txt(row, 'categorie')
    if not nom_cat:
        raise ErreurLigne("Catégorie : obligatoire.")
    categorie = _categorie(sens, nom_cat)
    montant = xo.nombre_decimal(ei._champ(row, 'montant'), 'Montant')
    if montant is None:
        raise ErreurLigne("Montant : obligatoire.")
    montant = services.dec(montant)
    libelle = ei._txt(row, 'libelle')
    if Mouvement.objects.filter(date=jour, categorie=categorie, libelle=libelle, montant=montant).exists():
        return 'ignore'
    donnees = {'date': jour.isoformat(), 'categorie': categorie.id, 'libelle': libelle, 'montant': str(montant),
               'imprevu': _booleen(ei._champ(row, 'imprevu')), 'reference': ei._txt(row, 'reference'),
               'notes': ei._txt(row, 'notes')}
    ei._valider(MouvementSerializer(data=donnees, context={})).save()
    return 'cree'


def _importer_paiements(ctx, row):
    statut = xo.normaliser(ei._champ(row, 'statut'))
    if statut.startswith('annul'):
        return 'ignore'
    annee = ctx.annee(ei._txt(row, 'annee'))
    classe = ctx.classe(annee, ei._txt(row, 'classe'))
    inscription = ei._trouver_inscription(ctx, classe, row)
    ins = Inscription.objects.select_related('eleve', 'classe', 'annee_scolaire').get(pk=inscription.pk)
    type_ = _par_libelle(dict(Paiement.TYPES), ei._champ(row, 'type'), 'Type')
    jour = xo.analyser_date(ei._champ(row, 'date'), 'Date')
    if jour and jour > services.aujourd_hui():
        raise ErreurLigne("Date : elle ne peut pas être dans le futur.")
    mode_brut = ei._champ(row, 'mode')
    mode = _par_libelle(dict(MODES_PAIEMENT), mode_brut, 'Mode') if mode_brut else 'especes'

    actives = LignePaiement.objects.filter(paiement__inscription=ins, paiement__annule=False)
    mois, tarif_id = None, None
    if type_ == 'droit':
        if actives.filter(paiement__type='droit').exists():
            return 'ignore'
    elif type_ == 'ecolage':
        brut = ei._champ(row, 'mois')
        if brut is None:
            raise ErreurLigne("Mois : obligatoire pour un écolage (ex. 2026-09).")
        mois = [services.mois_cle(services.lire_mois(brut, 'Mois'))]
        if actives.filter(paiement__type='ecolage', mois=services.lire_mois(mois[0])).exists():
            return 'ignore'
    else:
        libelle = ei._txt(row, 'libelle')
        services.verifier_niveau(ins.classe)
        tarif = next((t for t in services.tarifs_de_l_inscription(ins)['autres']
                      if xo.normaliser(t.libelle) == xo.normaliser(libelle)), None)
        if tarif is None:
            raise ErreurLigne(f"Frais « {libelle} » non défini pour {ins.classe.nom}.")
        if actives.filter(paiement__type='autre', tarif=tarif).exists():
            return 'ignore'
        tarif_id = tarif.id
    services.creer_paiement(ins, type_, mois=mois, tarif_id=tarif_id, date_paiement=jour, mode=mode,
                            reference=ei._txt(row, 'reference'), user=ctx.utilisateur)
    return 'cree'


def _importer_employes(ctx, row):
    nom, prenom = ei._txt(row, 'nom'), ei._txt(row, 'prenom')
    if not nom:
        raise ErreurLigne("Nom : obligatoire.")
    salaire = xo.nombre_decimal(ei._champ(row, 'salaire'), 'Salaire mensuel')
    donnees = {'nom': nom, 'prenom': prenom, 'poste': ei._txt(row, 'poste'), 'telephone': ei._txt(row, 'telephone')}
    if salaire is not None:
        donnees['salaire_mensuel'] = str(services.dec(salaire))
    embauche = xo.analyser_date(ei._champ(row, 'embauche'), "Date d'embauche")
    if embauche:
        donnees['date_embauche'] = embauche.isoformat()
    if ei._champ(row, 'actif') is not None:
        donnees['actif'] = _booleen(ei._champ(row, 'actif'), True)
    existant = next((e for e in Employe.objects.all()
                     if xo.normaliser(e.nom) == xo.normaliser(nom) and xo.normaliser(e.prenom) == xo.normaliser(prenom)),
                    None)
    if existant:
        changes = {c: v for c, v in donnees.items() if c not in ('nom', 'prenom') and v != '' and
                   str(getattr(existant, c)) != str(v) and
                   not (c == 'salaire_mensuel' and services.dec(getattr(existant, c)) == services.dec(v))}
        if not changes:
            return 'ignore'
        ei._valider(EmployeSerializer(existant, data=changes, partial=True)).save()
        return 'maj'
    ei._valider(EmployeSerializer(data=donnees)).save()
    return 'cree'


# ===========================================================================
# MODÈLES À TÉLÉCHARGER
# ===========================================================================
MODELES = {
    'tarifs': {
        'resume': "Définit les droits d'inscription, écolages mensuels et autres frais d'un niveau pour une année.",
        'colonnes': [
            ('Année scolaire', True, "Comme dans l'application", '2026-2027'),
            ('Niveau', True, "6ème, 5ème, Terminale…", '6ème'),
            ('Série', False, "Pour les niveaux à série (Première, Terminale)", ''),
            ('Type', True, "Droit d'inscription, Écolage mensuel ou Autre frais", 'Écolage mensuel'),
            ('Libellé', False, "Seulement pour « Autre frais » (ex. Uniforme)", ''),
            ('Montant', True, "Montant, sans la devise", 45000),
        ],
        'notes': ["Un tarif déjà défini avec un montant différent est mis à jour (les paiements déjà faits ne changent pas)."],
    },
    'categories_finance': {
        'resume': "Crée des catégories de dépenses ou d'entrées d'argent.",
        'colonnes': [
            ('Nom', True, "Nom de la catégorie", 'Fournitures'),
            ('Sens', True, "Dépense ou Entrée", 'Dépense'),
            ('Active', False, "Oui ou Non (Oui si vide)", 'Oui'),
        ],
        'notes': ["Une catégorie qui existe déjà est ignorée."],
    },
    'mouvements': {
        'resume': "Importe des dépenses, imprévus et entrées d'argent. Une catégorie inconnue est créée automatiquement.",
        'colonnes': [
            ('Date', True, "JJ/MM/AAAA", '14/10/2026'),
            ('Sens', True, "Dépense ou Entrée", 'Dépense'),
            ('Catégorie', True, "Nom de la catégorie", 'Entretien et réparations'),
            ('Libellé', True, "Description", 'Réparation du portail'),
            ('Montant', True, "Montant, sans la devise", 80000),
            ('Imprévu', False, "Oui si c'est une dépense imprévue", 'Oui'),
            ('Référence', False, "N° de facture ou de pièce", ''),
            ('Notes', False, "Remarque libre", ''),
        ],
        'notes': ["Une opération identique (même date, catégorie, libellé et montant) est ignorée."],
    },
    'paiements': {
        'resume': "Importe des paiements d'élèves (ex. reprise d'un ancien fichier). Les montants viennent des tarifs.",
        'colonnes': [
            ('Année scolaire', True, "Comme dans l'application", '2026-2027'),
            ('Classe', True, "Nom exact de la classe", '6ème 1'),
            ('N°', False, "Numéro de l'élève dans la classe (ou Matricule, ou Nom + Prénom)", 1),
            ('Matricule', False, "Autre façon d'identifier l'élève", ''),
            ('Nom', False, "Avec Prénom, si ni N° ni Matricule", ''),
            ('Prénom', False, "Avec Nom, si ni N° ni Matricule", ''),
            ('Type', True, "Droit d'inscription, Écolage ou Autre frais", 'Écolage'),
            ('Mois', False, "Obligatoire pour un écolage : AAAA-MM", '2026-09'),
            ('Désignation', False, "Nom du frais, pour « Autre frais »", ''),
            ('Date', False, "JJ/MM/AAAA (aujourd'hui si vide)", '05/09/2026'),
            ('Mode', False, "Espèces, Mobile money, Virement ou Chèque", 'Espèces'),
            ('Référence', False, "N° de transaction ou de chèque", ''),
        ],
        'notes': ["Les tarifs du niveau doivent être définis. Un mois ou un droit déjà payé est ignoré.",
                  "Les lignes « Annulé » d'un fichier exporté sont ignorées ; la colonne Montant est ignorée (le tarif s'applique)."],
    },
    'employes': {
        'resume': "Crée des employés ou met à jour leur salaire.",
        'colonnes': [
            ('Nom', True, "Nom de famille", 'RANDRIA'),
            ('Prénom', False, "Prénom", 'Mamy'),
            ('Poste', False, "Fonction", 'Enseignant'),
            ('Téléphone', False, "Mobile", '034 00 000 00'),
            ('Salaire mensuel', False, "Montant, sans la devise", 300000),
            ("Date d'embauche", False, "JJ/MM/AAAA", ''),
            ('Actif', False, "Oui ou Non", 'Oui'),
        ],
        'notes': ["Un employé est reconnu par son nom et son prénom."],
    },
}

OBLIGATOIRES = {
    'tarifs': ('annee', 'niveau', 'type', 'montant'),
    'categories_finance': ('nom', 'sens'),
    'mouvements': ('date', 'sens', 'categorie', 'libelle', 'montant'),
    'paiements': ('annee', 'classe', 'type'),
    'employes': ('nom',),
}
ALIAS = {
    'type': ('type',), 'mois': ('mois', 'moispaye'), 'montant': ('montant',),
    'libelle': ('libelle', 'designation'), 'date': ('date', 'datedepaiement'),
    'mode': ('mode', 'modedepaiement'), 'reference': ('reference', 'ref'),
    'sens': ('sens',), 'categorie': ('categorie',), 'imprevu': ('imprevu',), 'notes': ('notes', 'remarque'),
    'active': ('active', 'actif'), 'poste': ('poste', 'fonction'), 'telephone': ('telephone', 'mobile'),
    'salaire': ('salairemensuel', 'salaire'), 'embauche': ('datedembauche', 'embauche'),
    'actif': ('actif', 'active'), 'statut': ('statut',),
}
TITRES = {'type': 'Type', 'montant': 'Montant', 'sens': 'Sens', 'categorie': 'Catégorie', 'libelle': 'Libellé',
          'date': 'Date'}


def enregistrer():
    """Ajoute les jeux financiers à l'export / import Excel (peut être appelée plusieurs fois)."""
    jeux = (JeuTarifs(), JeuCategories(), JeuMouvements(), JeuPaiements(), JeuEmployes(), JeuSalaires(), JeuAvances())
    for j in jeux:
        ei.JEUX[j.cle] = j
        if j.importable:
            ei.JEUX_IMPORTABLES[j.cle] = j
    ei.FONCTIONS.update({
        'tarifs': _importer_tarifs, 'categories_finance': _importer_categories,
        'mouvements': _importer_mouvements, 'paiements': _importer_paiements, 'employes': _importer_employes,
    })
    ei.OBLIGATOIRES.update(OBLIGATOIRES)
    for cle, valeur in ALIAS.items():
        ei.ALIAS.setdefault(cle, valeur)
    ei.TITRES.update({k: v for k, v in TITRES.items() if k not in ei.TITRES})
    ei.CALCULEES.update({'nrecu', 'statut', 'utilisations', 'restearetenir', 'netpaye', 'brut', 'moispayes'})
    ei.MODELES.update(MODELES)

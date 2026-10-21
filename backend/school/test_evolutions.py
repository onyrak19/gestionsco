"""Tests des évolutions : niveaux/séries, configuration des matières, matricules,
clôture avec mot de passe, décisions, règles de passage, relevés, impressions PDF."""
import re
from datetime import date

from django.contrib.auth.models import User
from django.core.cache import cache
from rest_framework.test import APIClient, APITestCase

from accounts.models import UserProfile

from .calculs import cloturer_annee
from .models import (
    AnneeScolaire, Classe, ConfigMatiere, Matiere, Eleve, Inscription, Affectation, Note,
)

MDP = 'Passw0rd!secret'


def creer_user(username, role='enseignant', statut='valide'):
    user = User.objects.create_user(username, f'{username}@ecole.test', MDP)
    UserProfile.objects.create(user=user, role=role, statut=statut)
    return user


class Base(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = creer_user('admin', role='admin')
        cls.prof = creer_user('prof')
        cls.a1 = AnneeScolaire.objects.create(
            libelle='2025-2026', date_debut=date(2025, 9, 1), date_fin=date(2026, 6, 30), active=True)
        cls.a2 = AnneeScolaire.objects.create(
            libelle='2026-2027', date_debut=date(2026, 9, 1), date_fin=date(2027, 6, 30))
        cls.maths = Matiere.objects.create(nom='Mathématiques')
        cls.francais = Matiere.objects.create(nom='Français')
        cls.histoire = Matiere.objects.create(nom='Histoire')

    def setUp(self):
        cache.clear()

    def client_de(self, user):
        c = APIClient()
        c.force_authenticate(user)
        return c

    @property
    def adm(self):
        return self.client_de(self.admin)

    def classe(self, niveau, serie='', numero=1, annee=None):
        return Classe.objects.create(niveau=niveau, serie=serie, numero=numero,
                                     annee_scolaire=annee or self.a1)

    def eleve(self, nom='Rakoto', prenom='Jean'):
        return Eleve.objects.create(nom=nom, prenom=prenom)

    def inscrire(self, eleve, classe):
        return Inscription.objects.create(eleve=eleve, classe=classe)

    def noter(self, ins, matiere, valeur, trimestre=1):
        return Note.objects.create(inscription=ins, matiere=matiere, trimestre=trimestre,
                                   j1=valeur, examen=valeur)


# ---------------------------------------------------------------------------
class ClassesTests(Base):
    def creer(self, **donnees):
        base = {'annee_scolaire': self.a1.id}
        return self.adm.post('/api/school/classes/', {**base, **donnees}, format='json')

    def test_nom_construit_automatiquement(self):
        r = self.creer(niveau='5ème', numero=2)
        self.assertEqual((r.status_code, r.data['nom']), (201, '5ème 2'))
        r = self.creer(niveau='Petite section')
        self.assertEqual(r.data['nom'], 'Petite section 1')

    def test_serie_obligatoire_en_premiere_et_terminale(self):
        for niveau in ('Première', 'Terminale'):
            r = self.creer(niveau=niveau, numero=1)
            self.assertEqual(r.status_code, 400)
            self.assertIn('serie', r.data)
        r = self.creer(niveau='Terminale', serie='l', numero=1)
        self.assertEqual((r.status_code, r.data['nom'], r.data['serie']), (201, 'Terminale L 1', 'L'))

    def test_serie_ignoree_pour_les_autres_niveaux(self):
        r = self.creer(niveau='6ème', serie='S', numero=1)
        self.assertEqual((r.data['nom'], r.data['serie']), ('6ème 1', ''))

    def test_niveau_libre_saisi_a_la_main(self):
        r = self.creer(niveau='Maternelle bilingue', numero=3)
        self.assertEqual((r.status_code, r.data['nom']), (201, 'Maternelle bilingue 3'))

    def test_serie_libre_ose(self):
        r = self.creer(niveau='Première', serie='OSE', numero=2)
        self.assertEqual(r.data['nom'], 'Première OSE 2')

    def test_doublon_refuse_et_numero_suivant_accepte(self):
        self.creer(niveau='5ème', numero=1)
        self.assertEqual(self.creer(niveau='5ème', numero=1).status_code, 400)
        self.assertEqual(self.creer(niveau='5ème', numero=2).status_code, 201)
        # même classe dans une autre année : accepté
        self.assertEqual(self.adm.post('/api/school/classes/', {
            'niveau': '5ème', 'numero': 1, 'annee_scolaire': self.a2.id}, format='json').status_code, 201)

    def test_niveau_ou_nom_obligatoire(self):
        self.assertEqual(self.creer().status_code, 400)

    def test_classe_ancienne_avec_juste_un_nom(self):
        r = self.creer(nom='Ancienne classe')
        self.assertEqual((r.status_code, r.data['nom'], r.data['niveau']), (201, 'Ancienne classe', ''))

    def test_effectif_et_etat_de_configuration(self):
        c = self.classe('6ème')
        self.inscrire(self.eleve(), c)
        r = self.adm.get(f'/api/school/classes/?annee={self.a1.id}')
        self.assertEqual((r.data[0]['effectif'], r.data[0]['configuree']), (1, False))

    def test_niveaux_pour_les_formulaires(self):
        r = self.client_de(self.prof).get('/api/school/niveaux/')
        self.assertEqual(r.data['niveaux'][0], 'Petite section')
        self.assertEqual(r.data['niveaux'][-1], 'Terminale')
        self.assertEqual(r.data['series'], ['L', 'S', 'OSE'])
        self.assertEqual(r.data['niveaux_avec_serie'], ['Première', 'Terminale'])


# ---------------------------------------------------------------------------
class ConfigMatieresTests(Base):
    def put(self, classe, matieres):
        return self.adm.put('/api/school/config-matieres/', {
            'classe': classe.id,
            'matieres': [{'matiere': m.id, 'coefficient': c} for m, c in matieres]}, format='json')

    def get(self, classe):
        return self.adm.get(f'/api/school/config-matieres/?classe={classe.id}')

    def test_la_config_s_applique_a_toutes_les_classes_du_meme_niveau(self):
        c1, c2 = self.classe('5ème', numero=1), self.classe('5ème', numero=2)
        autre = self.classe('4ème')
        r = self.put(c1, [(self.maths, 4), (self.francais, 3)])
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(sorted(c['nom'] for c in r.data['classes']), ['5ème 1', '5ème 2'])

        r2 = self.get(c2)
        coefs = {m['nom']: (m['enseignee'], m['coefficient']) for m in r2.data['matieres']}
        self.assertEqual(coefs['Mathématiques'], (True, 4))
        self.assertEqual(coefs['Français'], (True, 3))
        self.assertFalse(coefs['Histoire'][0])
        self.assertTrue(r2.data['configuree'])
        self.assertFalse(self.get(autre).data['configuree'])

    def test_une_config_par_serie(self):
        p_s, p_l = self.classe('Première', 'S'), self.classe('Première', 'L')
        self.put(p_s, [(self.maths, 5)])
        self.put(p_l, [(self.maths, 2)])
        coef = lambda c: next(m['coefficient'] for m in self.get(c).data['matieres'] if m['nom'] == 'Mathématiques')
        self.assertEqual((coef(p_s), coef(p_l)), (5, 2))
        # une 2e classe Première S partage la config de la série S
        self.assertEqual(coef(self.classe('Première', 'S', numero=2)), 5)

    def test_modification_remplace_la_liste(self):
        c = self.classe('5ème')
        self.put(c, [(self.maths, 4), (self.francais, 3)])
        self.put(c, [(self.maths, 6)])
        self.assertEqual(ConfigMatiere.objects.filter(niveau='5ème').count(), 1)
        self.assertEqual(ConfigMatiere.objects.get(niveau='5ème').coefficient, 6)

    def test_propose_la_config_de_l_annee_precedente(self):
        self.put(self.classe('5ème'), [(self.maths, 4)])
        nouvelle = self.classe('5ème', annee=self.a2)
        r = self.get(nouvelle)
        self.assertEqual((r.data['configuree'], r.data['propose']), (False, True))
        self.assertEqual(next(m for m in r.data['matieres'] if m['nom'] == 'Mathématiques')['coefficient'], 4)
        # rien n'est enregistré tant que l'admin ne valide pas
        self.assertFalse(ConfigMatiere.objects.filter(annee_scolaire=self.a2).exists())
        self.put(nouvelle, [(self.maths, 4)])
        self.assertTrue(self.get(nouvelle).data['configuree'])

    def test_annee_cloturee_figee(self):
        c = self.classe('5ème')
        AnneeScolaire.objects.filter(pk=self.a1.pk).update(cloturee=True)
        self.assertEqual(self.put(c, [(self.maths, 4)]).status_code, 400)

    def test_classe_sans_niveau_refusee(self):
        ancienne = Classe.objects.create(nom='Vieille classe', annee_scolaire=self.a1)
        self.assertEqual(self.get(ancienne).status_code, 400)

    def test_validation(self):
        c = self.classe('5ème')
        self.assertEqual(self.put(c, [(self.maths, 0)]).status_code, 400)
        self.assertEqual(self.put(c, [(self.maths, 21)]).status_code, 400)
        self.assertEqual(self.put(c, [(self.maths, 2), (self.maths, 3)]).status_code, 400)

    def test_reserve_a_l_admin(self):
        c = self.classe('5ème')
        self.assertEqual(self.client_de(self.prof).get(f'/api/school/config-matieres/?classe={c.id}').status_code, 403)

    def test_seules_les_matieres_configurees_comptent_avec_leur_coefficient(self):
        c = self.classe('5ème')
        self.put(c, [(self.maths, 4), (self.francais, 1)])
        ins = self.inscrire(self.eleve(), c)
        self.noter(ins, self.maths, 10)
        self.noter(ins, self.francais, 20)
        self.noter(ins, self.histoire, 0)     # non enseignée en 5ème : ignorée
        r = self.adm.get(f'/api/school/classes/{c.id}/releve/?trimestre=1')
        self.assertEqual(r.data['eleves'][0]['generale'], 12.0)   # (10*4 + 20*1) / 5
        self.assertEqual([m['nom'] for m in r.data['matieres']], ['Français', 'Mathématiques'])

    def test_sans_config_on_garde_le_coefficient_par_defaut(self):
        c = self.classe('6ème')
        ins = self.inscrire(self.eleve(), c)
        Matiere.objects.filter(pk=self.maths.pk).update(coefficient=3)
        self.noter(ins, self.maths, 10)
        self.noter(ins, self.francais, 18)
        r = self.adm.get(f'/api/school/classes/{c.id}/releve/?trimestre=1')
        self.assertEqual(r.data['eleves'][0]['generale'], 12.0)   # (10*3 + 18*1) / 4

    def test_matiere_non_enseignee_refusee_pour_les_notes_et_les_affectations(self):
        c = self.classe('5ème')
        self.put(c, [(self.maths, 4)])
        ins = self.inscrire(self.eleve(), c)
        r = self.adm.post('/api/school/notes/upsert/', {
            'inscription': ins.id, 'matiere': self.histoire.id, 'trimestre': 1, 'j1': 10}, format='json')
        self.assertEqual(r.status_code, 400)
        r = self.adm.post('/api/school/affectations/', {
            'enseignant': self.prof.id, 'matiere': self.histoire.id, 'classe': c.id}, format='json')
        self.assertEqual(r.status_code, 400)
        r = self.adm.post('/api/school/affectations/', {
            'enseignant': self.prof.id, 'matiere': self.maths.id, 'classe': c.id}, format='json')
        self.assertEqual(r.status_code, 201, r.data)


# ---------------------------------------------------------------------------
class MatriculeEtNumeroTests(Base):
    def test_numero_par_classe_dans_l_ordre_d_inscription(self):
        c1, c2 = self.classe('Terminale', 'S'), self.classe('Terminale', 'L')
        i1 = self.inscrire(self.eleve('A', 'a'), c1)
        i2 = self.inscrire(self.eleve('B', 'b'), c1)
        i3 = self.inscrire(self.eleve('C', 'c'), c2)
        self.assertEqual((i1.numero, i2.numero, i3.numero), (1, 2, 1))

    def test_matricule_automatique(self):
        c = self.classe('Terminale', 'L')
        e = self.eleve()
        self.assertIsNone(e.matricule)
        self.inscrire(e, c)
        e.refresh_from_db()
        self.assertEqual(e.matricule, 'TLE-L1-25-001')

    def test_matricule_conserve_apres_une_autre_inscription(self):
        e = self.eleve()
        self.inscrire(e, self.classe('6ème'))
        e.refresh_from_db()
        premier = e.matricule
        self.inscrire(e, self.classe('5ème', annee=self.a2))
        e.refresh_from_db()
        self.assertEqual(e.matricule, premier)

    def test_matricules_distincts(self):
        c = self.classe('6ème')
        eleves = [self.eleve(f'N{i}', 'p') for i in range(3)]
        for e in eleves:
            self.inscrire(e, c)
        mats = [Eleve.objects.get(pk=e.pk).matricule for e in eleves]
        self.assertEqual(mats, ['6E-1-25-001', '6E-1-25-002', '6E-1-25-003'])

    def test_eleve_cree_sans_matricule_via_l_api(self):
        r = self.adm.post('/api/school/eleves/', {'nom': 'X', 'prenom': 'Y', 'matricule': 'FORCE'}, format='json')
        self.assertEqual((r.status_code, r.data['matricule']), (201, None))

    def test_un_eleve_ne_peut_etre_que_dans_une_classe_par_annee(self):
        e = self.eleve()
        c1, c2 = self.classe('6ème', numero=1), self.classe('6ème', numero=2)
        r = self.adm.post('/api/school/inscriptions/', {'eleve': e.id, 'classe': c1.id}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        r = self.adm.post('/api/school/inscriptions/', {'eleve': e.id, 'classe': c2.id}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('une seule classe', str(r.data))

    def test_l_api_attribue_numero_et_annee(self):
        c = self.classe('6ème')
        r = self.adm.post('/api/school/inscriptions/', {'eleve': self.eleve().id, 'classe': c.id}, format='json')
        self.assertEqual((r.data['numero'], r.data['annee_scolaire'], r.data['decision']),
                         (1, self.a1.id, 'en_cours'))
        self.assertTrue(r.data['eleve_details']['matricule'].startswith('6E-1-25-'))

    def test_tri_alphabetique_ou_par_numero(self):
        c = self.classe('6ème')
        for nom in ('Zafy', 'Abel', 'Miora'):
            self.inscrire(self.eleve(nom, 'p'), c)
        noms = lambda ordre: [i['eleve_details']['nom'] for i in
                              self.adm.get(f'/api/school/inscriptions/?classe={c.id}&ordre={ordre}').data]
        self.assertEqual(noms('alpha'), ['Abel', 'Miora', 'Zafy'])
        self.assertEqual(noms('numero'), ['Zafy', 'Abel', 'Miora'])

    def test_liste_des_eleves_par_nom_ou_matricule(self):
        c = self.classe('6ème')
        self.inscrire(self.eleve('Zafy', 'p'), c)
        self.inscrire(self.eleve('Abel', 'p'), c)
        noms = lambda ordre: [e['nom'] for e in self.adm.get(f'/api/school/eleves/?ordre={ordre}').data]
        self.assertEqual(noms('alpha'), ['Abel', 'Zafy'])
        self.assertEqual(noms('matricule'), ['Zafy', 'Abel'])
        e = self.adm.get('/api/school/eleves/').data[0]
        self.assertEqual((e['derniere_classe'], e['derniere_annee'], e['derniere_decision']),
                         ('6ème 1', '2025-2026', 'en_cours'))


# ---------------------------------------------------------------------------
class ClotureTests(Base):
    def setUp(self):
        super().setUp()
        self.c = self.classe('6ème')
        self.bon, self.faible, self.sans = (
            self.inscrire(self.eleve(nom, 'p'), self.c) for nom in ('Bon', 'Faible', 'Sans'))
        self.noter(self.bon, self.maths, 14)
        self.noter(self.faible, self.maths, 6)

    def cloturer(self, mdp=MDP, user=None):
        return self.client_de(user or self.admin).post(
            f'/api/school/annees/{self.a1.id}/cloturer/', {'password': mdp}, format='json')

    def test_mot_de_passe_obligatoire_et_verifie(self):
        self.assertEqual(self.cloturer('mauvais').status_code, 403)
        r = self.client_de(self.admin).post(f'/api/school/annees/{self.a1.id}/cloturer/', {}, format='json')
        self.assertEqual(r.status_code, 400)
        self.a1.refresh_from_db()
        self.assertFalse(self.a1.cloturee)

    def test_seul_un_admin_peut_cloturer(self):
        self.assertEqual(self.cloturer(user=self.prof).status_code, 403)

    def test_decisions_calculees(self):
        r = self.cloturer()
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['resume'], {'passant': 1, 'redoublant': 1, 'non_decide': 1})
        for ins, attendu, moy in ((self.bon, 'passant', 14.0), (self.faible, 'redoublant', 6.0),
                                  (self.sans, 'non_decide', None)):
            ins.refresh_from_db()
            self.assertEqual(ins.decision, attendu)
            self.assertEqual(ins.moyenne_annuelle and float(ins.moyenne_annuelle), moy)
        self.a1.refresh_from_db()
        self.assertTrue(self.a1.cloturee)
        self.assertFalse(self.a1.active)

    def test_seuil_exactement_10_est_passant(self):
        Note.objects.filter(inscription=self.faible).update(j1=10, examen=10)
        self.cloturer()
        self.faible.refresh_from_db()
        self.assertEqual(self.faible.decision, 'passant')

    def test_moyenne_annuelle_est_la_moyenne_des_trimestres(self):
        self.noter(self.bon, self.maths, 10, trimestre=2)     # T1 = 14, T2 = 10  -> 12
        self.cloturer()
        self.bon.refresh_from_db()
        self.assertEqual(float(self.bon.moyenne_annuelle), 12.0)

    def test_double_cloture_refusee(self):
        self.cloturer()
        self.assertEqual(self.cloturer().status_code, 400)

    def test_apres_cloture_plus_de_notes_ni_inscriptions(self):
        self.cloturer()
        r = self.adm.post('/api/school/notes/upsert/', {
            'inscription': self.bon.id, 'matiere': self.maths.id, 'trimestre': 1, 'j1': 20}, format='json')
        self.assertEqual(r.status_code, 403)
        r = self.adm.post('/api/school/inscriptions/', {'eleve': self.eleve('N', 'n').id, 'classe': self.c.id}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_correction_manuelle_de_la_decision(self):
        url = f'/api/school/inscriptions/{self.sans.id}/decision/'
        # impossible tant que l'année n'est pas clôturée
        self.assertEqual(self.adm.patch(url, {'decision': 'passant'}, format='json').status_code, 400)
        self.cloturer()
        self.assertEqual(self.adm.patch(url, {'decision': 'passant'}, format='json').data['decision'], 'passant')
        self.assertEqual(self.adm.patch(url, {'decision': 'en_cours'}, format='json').status_code, 400)
        self.assertEqual(self.client_de(self.prof).patch(url, {'decision': 'passant'}, format='json').status_code, 403)

    def test_dossier_de_l_eleve(self):
        self.cloturer()
        r = self.adm.get(f'/api/school/eleves/{self.bon.eleve_id}/dossier/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['statut'], 'passant')
        p = r.data['parcours'][0]
        self.assertEqual((p['annee'], p['classe'], p['decision'], p['moyenne_annuelle'], p['rang_annuel'], p['effectif']),
                         ('2025-2026', '6ème 1', 'passant', 14.0, 1, 3))
        self.assertEqual(p['moyennes']['T1'], 14.0)
        self.assertIsNone(p['moyennes']['T2'])
        self.assertEqual(self.client_de(self.prof).get(f'/api/school/eleves/{self.bon.eleve_id}/dossier/').status_code, 403)


# ---------------------------------------------------------------------------
class PassageEnClasseSuperieureTests(Base):
    def cycle(self, niveau, moyenne, serie=''):
        """Un élève fait son année a1 en `niveau` avec `moyenne`, puis a1 est clôturée."""
        c = self.classe(niveau, serie)
        e = self.eleve()
        ins = self.inscrire(e, c)
        if moyenne is not None:
            self.noter(ins, self.maths, moyenne)
        cloturer_annee(self.a1)
        return e

    def inscrire_api(self, eleve, niveau, serie=''):
        c, _ = Classe.objects.get_or_create(niveau=niveau, serie=serie, numero=1, annee_scolaire=self.a2)
        return self.adm.post('/api/school/inscriptions/', {'eleve': eleve.id, 'classe': c.id}, format='json')

    def test_passant_va_au_niveau_superieur(self):
        e = self.cycle('Seconde', 12)
        self.assertEqual(self.inscrire_api(e, 'Première', 'S').status_code, 201)

    def test_passant_ne_peut_pas_redoubler_ni_sauter_un_niveau(self):
        e = self.cycle('Seconde', 12)
        r = self.inscrire_api(e, 'Seconde')
        self.assertEqual(r.status_code, 400)
        self.assertIn('Première', str(r.data))
        self.assertEqual(self.inscrire_api(e, 'Terminale', 'S').status_code, 400)

    def test_redoublant_doit_refaire_le_meme_niveau(self):
        e = self.cycle('Seconde', 6)
        r = self.inscrire_api(e, 'Première', 'L')
        self.assertEqual(r.status_code, 400)
        self.assertIn('redoublant', str(r.data))
        self.assertEqual(self.inscrire_api(e, 'Seconde').status_code, 201)

    def test_exemple_du_cahier_des_charges_seconde_puis_premiere(self):
        reussi, rate = self.cycle('Seconde', 15), None
        self.assertEqual(self.inscrire_api(reussi, 'Première', 'S').status_code, 201)

    def test_meme_serie_de_premiere_a_terminale(self):
        e = self.cycle('Première', 13, 'S')
        r = self.inscrire_api(e, 'Terminale', 'L')
        self.assertEqual(r.status_code, 400)
        self.assertIn('même série', str(r.data))
        self.assertEqual(self.inscrire_api(e, 'Terminale', 'S').status_code, 201)

    def test_terminale_passant_a_termine_le_cycle(self):
        e = self.cycle('Terminale', 14, 'L')
        r = self.inscrire_api(e, 'Terminale', 'L')
        self.assertEqual(r.status_code, 400)
        self.assertIn('terminé le cycle', str(r.data))

    def test_sans_note_la_decision_doit_etre_prise_a_la_main(self):
        e = self.cycle('6ème', None)
        r = self.inscrire_api(e, '5ème')
        self.assertEqual(r.status_code, 400)
        self.assertIn('dossier', str(r.data))
        ins = Inscription.objects.get(eleve=e)
        self.adm.patch(f'/api/school/inscriptions/{ins.id}/decision/', {'decision': 'passant'}, format='json')
        self.assertEqual(self.inscrire_api(e, '5ème').status_code, 201)

    def test_annee_precedente_non_cloturee_bloque(self):
        e = self.eleve()
        self.inscrire(e, self.classe('6ème'))             # a1 pas clôturée
        r = self.inscrire_api(e, '5ème')
        self.assertEqual(r.status_code, 400)
        self.assertIn('clôturée', str(r.data))

    def test_nouvel_eleve_libre_de_choisir_son_niveau(self):
        self.assertEqual(self.inscrire_api(self.eleve('Neuf', 'x'), 'Terminale', 'S').status_code, 201)

    def test_niveaux_libres_sans_regle_automatique(self):
        c = Classe.objects.create(niveau='Atelier', annee_scolaire=self.a1)
        e = self.eleve()
        self.inscrire(e, c)
        cloturer_annee(self.a1)
        self.assertEqual(self.inscrire_api(e, '5ème').status_code, 201)


# ---------------------------------------------------------------------------
class NotesAdminTests(Base):
    """L'administrateur saisit et consulte les notes de toutes les classes."""

    def test_admin_saisit_dans_n_importe_quelle_classe_sans_affectation(self):
        for niveau in ('6ème', '3ème'):
            c = self.classe(niveau)
            ins = self.inscrire(self.eleve(niveau, 'x'), c)
            r = self.adm.post('/api/school/notes/upsert/', {
                'inscription': ins.id, 'matiere': self.maths.id, 'trimestre': 2, 'j1': 12, 'examen': 14}, format='json')
            self.assertEqual((r.status_code, r.data['moyenne_matiere']), (200, 13.0))
            self.assertEqual(Note.objects.get(inscription=ins).saisi_par, self.admin)

    def test_admin_lit_les_notes_de_toutes_les_classes(self):
        for niveau in ('6ème', '3ème'):
            self.noter(self.inscrire(self.eleve(niveau, 'x'), self.classe(niveau)), self.maths, 10)
        self.assertEqual(len(self.adm.get('/api/school/notes/').data), 2)
        self.assertEqual(len(self.adm.get('/api/school/inscriptions/').data), 2)

    def test_releve_de_classe(self):
        c = self.classe('6ème')
        self.noter(self.inscrire(self.eleve('Bon', 'a'), c), self.maths, 16)
        self.noter(self.inscrire(self.eleve('Moyen', 'b'), c), self.maths, 10)
        self.noter(self.inscrire(self.eleve('Faible', 'c'), c), self.maths, 4)
        r = self.adm.get(f'/api/school/classes/{c.id}/releve/?trimestre=1&ordre=rang')
        self.assertEqual([(e['nom'], e['generale'], e['rang']) for e in r.data['eleves']],
                         [('Bon', 16.0, 1), ('Moyen', 10.0, 2), ('Faible', 4.0, 3)])
        self.assertEqual(r.data['stats'], {'moyenne': 10.0, 'max': 16.0, 'min': 4.0, 'nb': 3})
        alpha = self.adm.get(f'/api/school/classes/{c.id}/releve/?trimestre=1').data['eleves']
        self.assertEqual([e['nom'] for e in alpha], ['Bon', 'Faible', 'Moyen'])
        self.assertEqual(self.adm.get(f'/api/school/classes/{c.id}/releve/?trimestre=9').status_code, 400)
        self.assertEqual(self.client_de(self.prof).get(f'/api/school/classes/{c.id}/releve/').status_code, 403)

    def test_releve_annuel_et_ex_aequo(self):
        c = self.classe('6ème')
        i1, i2 = self.inscrire(self.eleve('A', 'a'), c), self.inscrire(self.eleve('B', 'b'), c)
        for ins in (i1, i2):
            self.noter(ins, self.maths, 12, 1)
            self.noter(ins, self.maths, 14, 2)
        r = self.adm.get(f'/api/school/classes/{c.id}/releve/?trimestre=annuel')
        self.assertEqual([(e['generale'], e['rang']) for e in r.data['eleves']], [(13.0, 1), (13.0, 1)])


# ---------------------------------------------------------------------------
class EtablissementTests(Base):
    def test_lecture_et_modification(self):
        self.assertEqual(self.client_de(self.prof).get('/api/school/etablissement/').status_code, 200)
        r = self.adm.put('/api/school/etablissement/', {
            'nom': 'Lycée Test', 'ville': 'Antananarivo', 'directeur': 'M. X'}, format='json')
        self.assertEqual((r.status_code, r.data['nom']), (200, 'Lycée Test'))
        self.assertEqual(self.client_de(self.prof).put('/api/school/etablissement/', {'nom': 'Z'}, format='json').status_code, 403)


# ---------------------------------------------------------------------------
class PdfTests(Base):
    def setUp(self):
        super().setUp()
        self.c1, self.c2 = self.classe('6ème', numero=1), self.classe('6ème', numero=2)
        self.i1 = self.inscrire(self.eleve('Rakoto', 'Jean'), self.c1)
        self.i2 = self.inscrire(self.eleve('Rabe', 'Zo'), self.c1)
        self.i3 = self.inscrire(self.eleve('Andry', 'Mino'), self.c2)
        self.noter(self.i1, self.maths, 14)
        self.noter(self.i2, self.maths, 9)

    def pdf(self, nom, donnees, user=None):
        return self.client_de(user or self.admin).post(f'/api/school/pdf/{nom}/', donnees, format='json')

    def verifier(self, r):
        self.assertEqual(r.status_code, 200, getattr(r, 'data', ''))
        self.assertEqual(r['Content-Type'], 'application/pdf')
        self.assertTrue(r.content.startswith(b'%PDF'))
        return r.content

    def test_chaque_document_pour_une_selection(self):
        for nom in ('cartes', 'certificats'):
            self.verifier(self.pdf(nom, {'inscriptions': [self.i1.id, self.i3.id]}))
        self.verifier(self.pdf('bulletins', {'inscriptions': [self.i1.id], 'trimestre': 1}))

    def test_tout_selectionner_par_classe_ou_par_annee(self):
        self.verifier(self.pdf('cartes', {'classe': self.c1.id}))
        self.verifier(self.pdf('bulletins', {'annee': self.a1.id, 'trimestre': 2}))
        self.verifier(self.pdf('certificats', {'annee': self.a1.id, 'ordre': 'numero'}))

    def test_nombre_de_pages_des_cartes(self):
        pages = lambda octets: int(re.search(rb'/Count (\d+)', octets).group(1))
        for i in range(9):
            self.inscrire(self.eleve(f'N{i}', 'p'), self.c2)    # c2 : 10 élèves au total
        self.assertEqual(pages(self.verifier(self.pdf('cartes', {'inscriptions': [self.i1.id]}))), 1)
        self.assertEqual(pages(self.verifier(self.pdf('cartes', {'classe': self.c2.id}))), 2)   # 8 cartes par page
        self.assertEqual(pages(self.verifier(self.pdf('certificats', {'classe': self.c2.id}))), 10)  # 1 par élève

    def test_fiches_d_appel(self):
        self.verifier(self.pdf('fiches-appel', {'classes': [self.c1.id, self.c2.id], 'semaine': '2026-10-07'}))
        self.verifier(self.pdf('fiches-appel', {'annee': self.a1.id}))

    def test_donnees_invalides(self):
        self.assertEqual(self.pdf('cartes', {}).status_code, 400)
        self.assertEqual(self.pdf('cartes', {'inscriptions': []}).status_code, 400)
        self.assertEqual(self.pdf('cartes', {'inscriptions': 'abc'}).status_code, 400)
        self.assertEqual(self.pdf('cartes', {'inscriptions': ['x']}).status_code, 400)
        self.assertEqual(self.pdf('bulletins', {'classe': self.c1.id}).status_code, 400)
        self.assertEqual(self.pdf('bulletins', {'classe': self.c1.id, 'trimestre': 7}).status_code, 400)
        self.assertEqual(self.pdf('fiches-appel', {}).status_code, 400)
        self.assertEqual(self.pdf('fiches-appel', {'classes': [self.c1.id], 'semaine': 'demain'}).status_code, 400)

    def test_reserve_a_l_administrateur(self):
        for nom, corps in (('cartes', {'classe': self.c1.id}), ('certificats', {'classe': self.c1.id}),
                           ('bulletins', {'classe': self.c1.id, 'trimestre': 1}),
                           ('fiches-appel', {'classes': [self.c1.id]})):
            self.assertEqual(self.pdf(nom, corps, user=self.prof).status_code, 403, nom)
            self.assertEqual(APIClient().post(f'/api/school/pdf/{nom}/', corps, format='json').status_code, 401)

    def test_bulletin_d_une_annee_cloturee_contient_la_decision(self):
        AnneeScolaire.objects.filter(pk=self.a1.pk).update(cloturee=True)
        Inscription.objects.filter(pk=self.i1.pk).update(decision='passant')
        self.verifier(self.pdf('bulletins', {'inscriptions': [self.i1.id], 'trimestre': 3}))

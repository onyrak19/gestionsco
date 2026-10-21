from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework.test import APIClient, APITestCase

from accounts.models import UserProfile

from .models import (
    AnneeScolaire, Classe, Matiere, Eleve, Inscription, Affectation, Note, arrondi,
)
from .calculs import moyenne_ponderee


def creer_user(username, role='enseignant', statut='valide'):
    user = User.objects.create_user(username, f'{username}@ecole.test', 'Passw0rd!secret')
    UserProfile.objects.create(user=user, role=role, statut=statut)
    return user


class BaseTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = creer_user('admin', role='admin')
        cls.prof1 = creer_user('prof1')      # affecté : 6eA / Maths
        cls.prof2 = creer_user('prof2')      # aucune affectation
        cls.annee = AnneeScolaire.objects.create(
            libelle='2026-2027', date_debut=date(2026, 9, 1),
            date_fin=date(2027, 6, 30), active=True)
        cls.classe_a = Classe.objects.create(nom='6eA', annee_scolaire=cls.annee)
        cls.classe_b = Classe.objects.create(nom='6eB', annee_scolaire=cls.annee)
        cls.maths = Matiere.objects.create(nom='Maths', coefficient=3)
        cls.francais = Matiere.objects.create(nom='Français', coefficient=1)
        cls.eleve_a = Eleve.objects.create(matricule='A1', nom='Rakoto', prenom='Jean')
        cls.eleve_b = Eleve.objects.create(matricule='B1', nom='Rabe', prenom='Zo')
        cls.ins_a = Inscription.objects.create(
            eleve=cls.eleve_a, classe=cls.classe_a, annee_scolaire=cls.annee)
        cls.ins_b = Inscription.objects.create(
            eleve=cls.eleve_b, classe=cls.classe_b, annee_scolaire=cls.annee)
        Affectation.objects.create(
            enseignant=cls.prof1, matiere=cls.maths, classe=cls.classe_a,
            annee_scolaire=cls.annee)

    def client_de(self, user):
        c = APIClient()
        c.force_authenticate(user)
        return c

    def upsert(self, user, **donnees):
        base = {'inscription': self.ins_a.id, 'matiere': self.maths.id, 'trimestre': 1}
        return self.client_de(user).post('/api/school/notes/upsert/',
                                         {**base, **donnees}, format='json')


class CalculsTests(APITestCase):
    def test_arrondi_a_la_demi_superieure(self):
        self.assertEqual(arrondi('12.125'), 12.13)
        self.assertEqual(arrondi(Decimal('10.005')), 10.01)
        self.assertEqual(arrondi(Decimal('7')), 7.0)

    def test_moyennes_d_une_note(self):
        n = Note(j1=Decimal('10'), j2=Decimal('12'), j3=None, examen=Decimal('15'))
        self.assertEqual(n.moyenne_journaliere, 11.0)
        self.assertEqual(n.moyenne_matiere, 13.0)

    def test_zero_est_une_vraie_note(self):
        n = Note(j1=Decimal('0'), j2=Decimal('10'), examen=Decimal('0'))
        self.assertEqual(n.moyenne_journaliere, 5.0)
        self.assertEqual(n.moyenne_matiere, 2.5)

    def test_moyenne_avec_une_seule_composante(self):
        self.assertEqual(Note(examen=Decimal('14')).moyenne_matiere, 14.0)
        self.assertEqual(Note(j1=Decimal('9'), j2=Decimal('10')).moyenne_matiere, 9.5)
        self.assertIsNone(Note().moyenne_matiere)
        self.assertIsNone(Note().moyenne_journaliere)

    def test_moyenne_ponderee(self):
        self.assertEqual(moyenne_ponderee([(10.0, 3), (16.0, 1)]), 11.5)
        self.assertEqual(moyenne_ponderee([(None, 2), (12.0, 2)]), 12.0)
        self.assertIsNone(moyenne_ponderee([]))


class InscriptionsEnseignantTests(BaseTest):
    def test_enseignant_voit_les_eleves_de_sa_classe_seulement(self):
        c = self.client_de(self.prof1)
        r = c.get(f'/api/school/inscriptions/?classe={self.classe_a.id}')
        self.assertEqual(r.status_code, 200)
        self.assertEqual([i['id'] for i in r.data], [self.ins_a.id])
        # même en demandant l'autre classe, ou toutes
        self.assertEqual(c.get(f'/api/school/inscriptions/?classe={self.classe_b.id}').data, [])
        self.assertEqual([i['id'] for i in c.get('/api/school/inscriptions/').data], [self.ins_a.id])

    def test_enseignant_sans_affectation_ne_voit_rien(self):
        self.assertEqual(self.client_de(self.prof2).get('/api/school/inscriptions/').data, [])

    def test_l_admin_voit_tout(self):
        r = self.client_de(self.admin).get('/api/school/inscriptions/')
        self.assertEqual(len(r.data), 2)

    def test_enseignant_ne_peut_pas_inscrire(self):
        r = self.client_de(self.prof1).post('/api/school/inscriptions/', {
            'eleve': self.eleve_b.id, 'classe': self.classe_a.id,
            'annee_scolaire': self.annee.id}, format='json')
        self.assertEqual(r.status_code, 403)

    def test_enseignant_en_attente_refuse(self):
        attente = creer_user('attente', statut='en_attente')
        self.assertEqual(self.client_de(attente).get('/api/school/inscriptions/').status_code, 403)

    def test_anonyme_refuse(self):
        self.assertEqual(APIClient().get('/api/school/inscriptions/').status_code, 401)


class ListeNotesTests(BaseTest):
    def setUp(self):
        Note.objects.create(inscription=self.ins_a, matiere=self.maths, trimestre=1, j1=10)
        Note.objects.create(inscription=self.ins_a, matiere=self.francais, trimestre=1, j1=11)
        Note.objects.create(inscription=self.ins_b, matiere=self.maths, trimestre=1, j1=12)

    def test_enseignant_sans_affectation_ne_voit_aucune_note(self):
        r = self.client_de(self.prof2).get('/api/school/notes/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data, [])

    def test_enseignant_ne_voit_que_sa_classe_et_sa_matiere(self):
        r = self.client_de(self.prof1).get('/api/school/notes/')
        self.assertEqual([(n['inscription'], n['matiere']) for n in r.data],
                         [(self.ins_a.id, self.maths.id)])

    def test_l_admin_voit_tout(self):
        self.assertEqual(len(self.client_de(self.admin).get('/api/school/notes/').data), 3)

    def test_filtres(self):
        r = self.client_de(self.admin).get(
            f'/api/school/notes/?classe={self.classe_b.id}&trimestre=1')
        self.assertEqual(len(r.data), 1)

    def test_creation_directe_impossible(self):
        r = self.client_de(self.prof1).post('/api/school/notes/', {
            'inscription': self.ins_b.id, 'matiere': self.maths.id,
            'trimestre': 2, 'j1': 20}, format='json')
        self.assertEqual(r.status_code, 405)
        self.assertEqual(Note.objects.count(), 3)

    def test_parametre_non_numerique_donne_400(self):
        r = self.client_de(self.admin).get('/api/school/notes/?classe=abc')
        self.assertEqual(r.status_code, 400)


class SaisieNotesTests(BaseTest):
    def test_saisie_avec_des_textes_comme_le_fait_le_formulaire(self):
        r = self.upsert(self.prof1, j1='12.5', j2='', j3='', examen='14')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['j1'], 12.5)
        self.assertIsNone(r.data['j2'])
        self.assertEqual(r.data['moyenne_journaliere'], 12.5)
        self.assertEqual(r.data['moyenne_matiere'], 13.25)

    def test_zero_est_conserve(self):
        r = self.upsert(self.prof1, j1=0, j2=10, examen=0)
        self.assertEqual(r.status_code, 200)
        n = Note.objects.get(inscription=self.ins_a)
        self.assertEqual((n.j1, n.j2, n.examen), (Decimal('0'), Decimal('10'), Decimal('0')))
        self.assertEqual(r.data['moyenne_matiere'], 2.5)

    def test_mise_a_jour_remplace_les_valeurs(self):
        self.upsert(self.prof1, j1=10, j2=11, examen=12)
        r = self.upsert(self.prof1, j1=15, j2='', examen=16)
        self.assertEqual(Note.objects.count(), 1)
        self.assertEqual(r.data['j1'], 15.0)
        self.assertIsNone(r.data['j2'])
        n = Note.objects.get()
        self.assertEqual(n.saisi_par, self.prof1)

    def test_bareme_0_a_20(self):
        for mauvaise in (-1, 20.01, 250, 'abc'):
            r = self.upsert(self.prof1, j1=mauvaise)
            self.assertEqual(r.status_code, 400, mauvaise)
        self.assertEqual(self.upsert(self.prof1, j1=20).status_code, 200)

    def test_trop_de_decimales_refuse(self):
        self.assertEqual(self.upsert(self.prof1, j1='12.345').status_code, 400)

    def test_trimestre_invalide(self):
        for t in (0, 4, 'x'):
            self.assertEqual(self.upsert(self.prof1, trimestre=t).status_code, 400, t)

    def test_matiere_ou_inscription_inconnue_donne_400_pas_500(self):
        self.assertEqual(self.upsert(self.prof1, matiere=99999).status_code, 400)
        self.assertEqual(self.upsert(self.prof1, inscription=99999).status_code, 400)

    def test_champs_obligatoires(self):
        r = self.client_de(self.prof1).post('/api/school/notes/upsert/', {}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_enseignant_non_affecte_a_la_classe(self):
        r = self.upsert(self.prof1, inscription=self.ins_b.id, j1=10)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(Note.objects.count(), 0)

    def test_enseignant_non_affecte_a_la_matiere(self):
        r = self.upsert(self.prof1, matiere=self.francais.id, j1=10)
        self.assertEqual(r.status_code, 403)

    def test_enseignant_sans_affectation(self):
        self.assertEqual(self.upsert(self.prof2, j1=10).status_code, 403)

    def test_l_admin_peut_tout_saisir(self):
        r = self.upsert(self.admin, inscription=self.ins_b.id, matiere=self.francais.id, j1=9)
        self.assertEqual(r.status_code, 200)

    def test_annee_cloturee_bloque_la_saisie(self):
        self.annee.cloturee = True
        self.annee.active = False
        self.annee.save()
        r = self.upsert(self.prof1, j1=10)
        self.assertEqual(r.status_code, 403)
        self.assertIn('clôturée', r.data['detail'])
        self.assertEqual(self.upsert(self.admin, j1=10).status_code, 403)


class MoyennesEleveTests(BaseTest):
    def setUp(self):
        Affectation.objects.create(enseignant=self.prof1, matiere=self.francais,
                                   classe=self.classe_a, annee_scolaire=self.annee)
        Note.objects.create(inscription=self.ins_a, matiere=self.maths, trimestre=1,
                            j1=10, examen=10)          # moyenne 10, coef 3
        Note.objects.create(inscription=self.ins_a, matiere=self.francais, trimestre=1,
                            j1=18, examen=18)          # moyenne 18, coef 1

    def test_moyenne_generale_ponderee_par_les_coefficients(self):
        r = self.client_de(self.admin).get(f'/api/school/notes/moyennes/{self.eleve_a.id}/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['par_matiere'], {'Maths': {'T1': 10.0}, 'Français': {'T1': 18.0}})
        # (10*3 + 18*1) / 4 = 12  (et non 14 comme avec une moyenne simple)
        self.assertEqual(r.data['moyenne_generale'], {'T1': 12.0})

    def test_enseignant_de_la_classe_autorise(self):
        r = self.client_de(self.prof1).get(f'/api/school/notes/moyennes/{self.eleve_a.id}/')
        self.assertEqual(r.status_code, 200)

    def test_enseignant_d_une_autre_classe_refuse(self):
        r = self.client_de(self.prof1).get(f'/api/school/notes/moyennes/{self.eleve_b.id}/')
        self.assertEqual(r.status_code, 403)
        self.assertEqual(
            self.client_de(self.prof2).get(f'/api/school/notes/moyennes/{self.eleve_a.id}/').status_code, 403)

    def test_eleve_inconnu(self):
        self.assertEqual(self.client_de(self.admin).get('/api/school/notes/moyennes/9999/').status_code, 404)

    def test_les_annees_ne_se_melangent_pas(self):
        ancienne = AnneeScolaire.objects.create(
            libelle='2025-2026', date_debut=date(2025, 9, 1), date_fin=date(2026, 6, 30))
        classe_old = Classe.objects.create(nom='6eA', annee_scolaire=ancienne)
        ins_old = Inscription.objects.create(eleve=self.eleve_a, classe=classe_old,
                                             annee_scolaire=ancienne)
        Note.objects.create(inscription=ins_old, matiere=self.maths, trimestre=1, j1=2, examen=2)
        # par défaut : année active uniquement
        r = self.client_de(self.admin).get(f'/api/school/notes/moyennes/{self.eleve_a.id}/')
        self.assertEqual(r.data['par_matiere']['Maths'], {'T1': 10.0})
        r = self.client_de(self.admin).get(
            f'/api/school/notes/moyennes/{self.eleve_a.id}/?annee={ancienne.id}')
        self.assertEqual(r.data['par_matiere'], {'Maths': {'T1': 2.0}})


class ReferentielTests(BaseTest):
    def test_le_code_des_matieres_est_automatique(self):
        c = self.client_de(self.admin)
        codes = {}
        for nom in ('Histoire', 'Géographie', 'Sport', 'Histoire de l\'art'):
            r = c.post('/api/school/matieres/', {'nom': nom, 'coefficient': 1}, format='json')
            self.assertEqual(r.status_code, 201, r.data)
            codes[nom] = r.data['code']
        self.assertEqual(codes, {'Histoire': 'HIS', 'Géographie': 'GEO', 'Sport': 'SPO',
                                 "Histoire de l'art": 'HIS2'})

    def test_le_code_ne_se_saisit_pas(self):
        r = self.client_de(self.admin).post(
            '/api/school/matieres/', {'nom': 'Histoire', 'code': 'ZZZ', 'coefficient': 1}, format='json')
        self.assertEqual(r.data['code'], 'HIS')   # le code envoyé est ignoré

    def test_coefficient_minimum_1(self):
        r = self.client_de(self.admin).post(
            '/api/school/matieres/', {'nom': 'X', 'coefficient': 0}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_eleve_sans_date_de_naissance(self):
        r = self.client_de(self.admin).post('/api/school/eleves/', {
            'matricule': 'Z9', 'nom': 'A', 'prenom': 'B',
            'date_naissance': '', 'sexe': 'M'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertIsNone(r.data['date_naissance'])

    def test_recherche_eleve(self):
        r = self.client_de(self.admin).get('/api/school/eleves/?search=rakoto')
        self.assertEqual([e['matricule'] for e in r.data], ['A1'])

    def test_ecriture_reservee_a_l_admin(self):
        c = self.client_de(self.prof1)
        self.assertEqual(c.post('/api/school/matieres/', {'nom': 'X'}, format='json').status_code, 403)
        self.assertEqual(c.get('/api/school/matieres/').status_code, 200)
        self.assertEqual(c.get('/api/school/eleves/').status_code, 403)


class AnneesTests(BaseTest):
    def creer(self, **modifs):
        donnees = {'libelle': '2030-2031', 'date_debut': '2030-09-01', 'date_fin': '2031-06-30'}
        return self.client_de(self.admin).post('/api/school/annees/', {**donnees, **modifs}, format='json')

    def test_dates_incoherentes_refusees(self):
        self.assertEqual(self.creer(date_fin='2030-01-01').status_code, 400)
        self.assertEqual(self.creer(date_fin='2030-09-01').status_code, 400)

    def test_une_seule_annee_active(self):
        r = self.creer(active=True)
        self.assertEqual(r.status_code, 201)
        self.annee.refresh_from_db()
        self.assertFalse(self.annee.active)
        self.assertEqual(AnneeScolaire.objects.filter(active=True).count(), 1)

    def test_une_annee_cloturee_ne_peut_pas_etre_reactivee(self):
        AnneeScolaire.objects.filter(pk=self.annee.pk).update(cloturee=True, active=False)
        r = self.client_de(self.admin).patch(
            f'/api/school/annees/{self.annee.id}/', {'active': True}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_la_cloture_ne_passe_pas_par_la_modification_simple(self):
        r = self.client_de(self.admin).patch(
            f'/api/school/annees/{self.annee.id}/', {'cloturee': True}, format='json')
        self.assertEqual(r.status_code, 200)
        self.annee.refresh_from_db()
        self.assertFalse(self.annee.cloturee)   # ignoré : il faut le mot de passe

    def test_pas_de_nouvelle_classe_dans_une_annee_cloturee(self):
        AnneeScolaire.objects.filter(pk=self.annee.pk).update(cloturee=True, active=False)
        r = self.client_de(self.admin).post(
            '/api/school/classes/', {'niveau': '5ème', 'numero': 1, 'annee_scolaire': self.annee.id}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_annee_active(self):
        r = self.client_de(self.prof1).get('/api/school/annees/active/')
        self.assertEqual(r.data['libelle'], '2026-2027')

    def test_parametre_annee_invalide(self):
        self.assertEqual(self.client_de(self.admin).get('/api/school/classes/?annee=abc').status_code, 400)


class InscriptionAffectationValidationTests(BaseTest):
    def setUp(self):
        self.ancienne = AnneeScolaire.objects.create(
            libelle='2025-2026', date_debut=date(2025, 9, 1), date_fin=date(2026, 6, 30))
        self.eleve_c = Eleve.objects.create(matricule='C1', nom='Andry', prenom='Mino')

    def test_l_annee_de_l_inscription_est_celle_de_la_classe(self):
        r = self.client_de(self.admin).post('/api/school/inscriptions/', {
            'eleve': self.eleve_c.id, 'classe': self.classe_a.id,
            'annee_scolaire': self.ancienne.id}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['annee_scolaire'], self.annee.id)

    def test_inscription_valide_et_doublon_refuse(self):
        c = self.client_de(self.admin)
        donnees = {'eleve': self.eleve_c.id, 'classe': self.classe_a.id, 'annee_scolaire': self.annee.id}
        self.assertEqual(c.post('/api/school/inscriptions/', donnees, format='json').status_code, 201)
        self.assertEqual(c.post('/api/school/inscriptions/', donnees, format='json').status_code, 400)

    def test_affectation_seulement_pour_un_enseignant_valide(self):
        c = self.client_de(self.admin)
        base = {'matiere': self.francais.id, 'classe': self.classe_b.id, 'annee_scolaire': self.annee.id}
        for refuse in (self.admin, creer_user('attente', statut='en_attente')):
            r = c.post('/api/school/affectations/', {**base, 'enseignant': refuse.id}, format='json')
            self.assertEqual(r.status_code, 400)
        r = c.post('/api/school/affectations/', {**base, 'enseignant': self.prof2.id}, format='json')
        self.assertEqual(r.status_code, 201, r.data)

    def test_l_annee_de_l_affectation_est_celle_de_la_classe(self):
        r = self.client_de(self.admin).post('/api/school/affectations/', {
            'enseignant': self.prof2.id, 'matiere': self.francais.id,
            'classe': self.classe_a.id, 'annee_scolaire': self.ancienne.id}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['annee_scolaire'], self.annee.id)   # pas l'année envoyée


class MesAffectationsTests(BaseTest):
    def test_par_defaut_annee_active_seulement(self):
        ancienne = AnneeScolaire.objects.create(
            libelle='2025-2026', date_debut=date(2025, 9, 1), date_fin=date(2026, 6, 30))
        classe_old = Classe.objects.create(nom='6eA', annee_scolaire=ancienne)
        Affectation.objects.create(enseignant=self.prof1, matiere=self.maths,
                                   classe=classe_old, annee_scolaire=ancienne)
        c = self.client_de(self.prof1)
        self.assertEqual(len(c.get('/api/school/affectations/mes/').data), 1)
        self.assertEqual(len(c.get('/api/school/affectations/mes/?annee=all').data), 2)
        self.assertEqual(len(c.get(f'/api/school/affectations/mes/?annee={ancienne.id}').data), 1)
        # les affectations des autres ne sont jamais visibles
        self.assertEqual(self.client_de(self.prof2).get('/api/school/affectations/mes/').data, [])

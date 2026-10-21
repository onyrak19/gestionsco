from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework.test import APIClient, APITestCase

from accounts.models import UserProfile
from school.models import AnneeScolaire, Classe, Eleve, Inscription

from .models import AvanceSalaire, CategorieFinance, Employe, Paiement, Tarif


def creer_user(username, role='admin'):
    u = User.objects.create_user(username, f'{username}@ecole.test', 'Passw0rd!secret')
    UserProfile.objects.create(user=u, role=role, statut='valide')
    return u


class BaseFinance(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = creer_user('admin')
        cls.prof = creer_user('prof', role='enseignant')
        cls.annee = AnneeScolaire.objects.create(
            libelle='2026-2027', date_debut=date(2026, 9, 1), date_fin=date(2027, 6, 30), active=True)
        cls.classe = Classe.objects.create(niveau='6ème', numero=1, annee_scolaire=cls.annee)
        cls.eleve = Eleve.objects.create(nom='Rakoto', prenom='Jean', parent_nom='Mme Rasoa',
                                         parent_mobile='034 12 345 67')
        cls.ins = Inscription.objects.create(eleve=cls.eleve, classe=cls.classe, annee_scolaire=cls.annee)
        Tarif.objects.create(annee_scolaire=cls.annee, niveau='6ème', type='droit', montant=50000)
        Tarif.objects.create(annee_scolaire=cls.annee, niveau='6ème', type='ecolage', montant=45000)
        cls.uniforme = Tarif.objects.create(annee_scolaire=cls.annee, niveau='6ème', type='autre',
                                            libelle='Uniforme', montant=30000)

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.admin)

    def encaisser(self, **donnees):
        base = {'inscription': self.ins.id, 'type': 'ecolage', 'mois': ['2026-09']}
        return self.api.post('/api/finance/paiements/', {**base, **donnees}, format='json')


class PaiementsTests(BaseFinance):
    def test_montant_automatique_et_recu(self):
        r = self.encaisser(mois=['2026-09', '2026-10'])
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['montant_total'], 90000)
        self.assertEqual(len(r.data['lignes']), 2)
        self.assertTrue(r.data['numero'].startswith('REC-'))

    def test_le_montant_envoye_est_ignore(self):
        r = self.encaisser(montant=1)
        self.assertEqual(r.data['montant_total'], 45000)

    def test_droit_une_seule_fois(self):
        self.assertEqual(self.encaisser(type='droit', mois=None).status_code, 201)
        self.assertEqual(self.encaisser(type='droit').status_code, 400)

    def test_mois_deja_paye_refuse(self):
        self.encaisser()
        self.assertEqual(self.encaisser().status_code, 400)

    def test_mois_hors_annee_refuse(self):
        self.assertEqual(self.encaisser(mois=['2026-07']).status_code, 400)

    def test_autre_frais(self):
        r = self.encaisser(type='autre', tarif=self.uniforme.id)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['montant_total'], 30000)

    def test_tarif_manquant(self):
        Tarif.objects.filter(type='ecolage').delete()
        r = self.encaisser()
        self.assertEqual(r.status_code, 400)

    def test_apercu_n_enregistre_rien(self):
        r = self.encaisser(apercu=True)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['total'], 45000)
        self.assertEqual(Paiement.objects.count(), 0)

    def test_situation_et_annulation(self):
        p = self.encaisser(mois=['2026-09']).data
        s = self.api.get(f'/api/finance/inscriptions/{self.ins.id}/situation/?au=2026-10').data
        statuts = {m['mois']: m['statut'] for m in s['ecolage']['mois']}
        self.assertEqual(statuts['2026-09'], 'paye')
        self.assertEqual(statuts['2026-10'], 'impaye')
        r = self.api.post(f"/api/finance/paiements/{p['id']}/annuler/", {'motif': 'Erreur'}, format='json')
        self.assertEqual(r.status_code, 200)
        s = self.api.get(f'/api/finance/inscriptions/{self.ins.id}/situation/?au=2026-10').data
        self.assertEqual({m['mois']: m['statut'] for m in s['ecolage']['mois']}['2026-09'], 'impaye')
        self.assertEqual(self.api.post(f"/api/finance/paiements/{p['id']}/annuler/", {}, format='json').status_code, 400)

    def test_pdf_recu_et_carte(self):
        p = self.encaisser().data
        r = self.api.get(f"/api/finance/paiements/{p['id']}/recu/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b'%PDF'))
        r = self.api.post('/api/finance/pdf/cartes-ecolage/', {'classe': self.classe.id}, format='json')
        self.assertTrue(r.content.startswith(b'%PDF'))
        r = self.api.post('/api/finance/pdf/impayes/', {'annee': self.annee.id}, format='json')
        self.assertTrue(r.content.startswith(b'%PDF'))

    def test_droits_admin_seulement(self):
        prof = APIClient()
        prof.force_authenticate(self.prof)
        self.assertEqual(prof.get('/api/finance/situations/').status_code, 403)
        self.assertEqual(APIClient().get('/api/finance/situations/').status_code, 401)


class TarifsTests(BaseFinance):
    def test_lecture_et_ecriture(self):
        r = self.api.get(f'/api/finance/tarifs/?annee={self.annee.id}')
        bloc = r.data['niveaux'][0]
        self.assertEqual((bloc['niveau'], bloc['droit_inscription'], bloc['ecolage_mensuel']), ('6ème', 50000, 45000))
        r = self.api.put('/api/finance/tarifs/', {
            'annee': self.annee.id, 'niveau': '6ème', 'droit_inscription': 60000, 'ecolage_mensuel': 45000,
            'autres': [{'libelle': 'Uniforme', 'montant': 30000}]}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(Tarif.objects.get(type='droit').montant, Decimal('60000'))

    def test_frais_deja_encaisse_non_supprimable(self):
        self.encaisser(type='autre', tarif=self.uniforme.id)
        r = self.api.put('/api/finance/tarifs/', {
            'annee': self.annee.id, 'niveau': '6ème', 'droit_inscription': 50000, 'ecolage_mensuel': 45000,
            'autres': []}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_copie_vers_nouvelle_annee(self):
        nouvelle = AnneeScolaire.objects.create(
            libelle='2027-2028', date_debut=date(2027, 9, 1), date_fin=date(2028, 6, 30))
        r = self.api.post('/api/finance/tarifs/copier/', {'de': self.annee.id, 'vers': nouvelle.id}, format='json')
        self.assertEqual(r.data['copies'], 3)


class DepensesTests(BaseFinance):
    def test_categories_par_defaut_et_ajout(self):
        self.assertTrue(CategorieFinance.objects.filter(sens='depense', nom='Imprévus').exists())
        r = self.api.post('/api/finance/categories/', {'nom': 'Jardinage', 'sens': 'depense'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        r = self.api.post('/api/finance/categories/', {'nom': 'jardinage', 'sens': 'depense'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_mouvements_et_bilan(self):
        self.encaisser()
        dep = CategorieFinance.objects.get(sens='depense', nom='Imprévus')
        ent = CategorieFinance.objects.get(sens='entree', nom='Subvention')
        self.api.post('/api/finance/mouvements/', {
            'date': '2026-10-01', 'categorie': dep.id, 'libelle': 'Vitre cassée', 'montant': 20000,
            'imprevu': True}, format='json')
        self.api.post('/api/finance/mouvements/', {
            'date': '2026-10-02', 'categorie': ent.id, 'libelle': 'Subvention', 'montant': 100000}, format='json')
        b = self.api.get('/api/finance/bilan/?date_debut=2026-09-01&date_fin=2026-12-31').data
        self.assertEqual(b['entrees']['total'], 145000)
        self.assertEqual(b['depenses']['imprevus'], 20000)
        self.assertEqual(b['solde'], 125000)

    def test_categorie_utilisee_non_supprimable(self):
        dep = CategorieFinance.objects.get(sens='depense', nom='Loyer')
        self.api.post('/api/finance/mouvements/', {
            'date': '2026-10-01', 'categorie': dep.id, 'libelle': 'Loyer', 'montant': 1000}, format='json')
        self.assertEqual(self.api.delete(f'/api/finance/categories/{dep.id}/').status_code, 400)


class SalairesTests(BaseFinance):
    def setUp(self):
        super().setUp()
        self.emp = Employe.objects.create(nom='Randria', prenom='Mamy', salaire_mensuel=300000)

    def payer(self, **donnees):
        base = {'employe': self.emp.id, 'mois': ['2025-12', '2026-01', '2026-02']}
        return self.api.post('/api/finance/salaires/', {**base, **donnees}, format='json')

    def test_plusieurs_mois_montant_automatique(self):
        r = self.payer()
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['montant_brut'], 900000)
        self.assertEqual(r.data['net_paye'], 900000)

    def test_mois_deja_paye(self):
        self.payer(mois=['2025-12'])
        self.assertEqual(self.payer(mois=['2025-12']).status_code, 400)

    def test_avance_retenue_automatiquement(self):
        self.api.post('/api/finance/avances/', {'employe': self.emp.id, 'date': '2026-01-05', 'montant': 100000},
                      format='json')
        r = self.payer(mois=['2026-01'])
        self.assertEqual(r.data['retenue_avances'], 100000)
        self.assertEqual(r.data['net_paye'], 200000)
        self.assertEqual(self.api.get(f'/api/finance/employes/{self.emp.id}/situation/').data['total_avances'], 0)
        # annuler la paie : l'avance redevient due
        self.api.post(f"/api/finance/salaires/{r.data['id']}/annuler/", {'motif': 'Erreur'}, format='json')
        self.assertEqual(self.api.get(f'/api/finance/employes/{self.emp.id}/situation/').data['total_avances'], 100000)

    def test_avance_partielle_sur_plusieurs_paies(self):
        self.api.post('/api/finance/avances/', {'employe': self.emp.id, 'date': '2026-01-05', 'montant': 500000},
                      format='json')
        r1 = self.payer(mois=['2026-01'])
        self.assertEqual(r1.data['retenue_avances'], 300000)
        r2 = self.payer(mois=['2026-02'])
        self.assertEqual(r2.data['retenue_avances'], 200000)
        self.assertEqual(r2.data['net_paye'], 100000)

    def test_situation_exceptionnelle_avec_penalite(self):
        r = self.payer(mois=['2026-01'], autres_retenues=50000, motif_retenues='Pénalité retards')
        self.assertEqual(r.data['net_paye'], 250000)
        self.assertEqual(self.payer(mois=['2026-02'], autres_retenues=1000).status_code, 400)   # motif manquant
        r = self.payer(mois=['2026-03'], exceptionnel=True, montant_exceptionnel=120000,
                       motif_exceptionnel='Mi-temps ce mois')
        self.assertEqual(r.data['montant_brut'], 120000)
        self.assertEqual(self.payer(mois=['2026-04'], exceptionnel=True, montant_exceptionnel=1).status_code, 400)

    def test_paiement_groupe(self):
        autre = Employe.objects.create(nom='Rabe', salaire_mensuel=200000)
        Employe.objects.create(nom='Sans salaire')
        r = self.api.post('/api/finance/salaires/groupe/',
                          {'employes': 'tous', 'mois': ['2026-01'], 'apercu': True}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['total_net'], 500000)
        self.assertEqual(r.data['nb_erreurs'], 1)
        self.assertEqual(Paiement.objects.count() + self.emp.paies.count(), 0)
        r = self.api.post('/api/finance/salaires/groupe/',
                          {'employes': [self.emp.id, autre.id], 'mois': ['2026-01']}, format='json')
        self.assertEqual(r.data['nb_payes'], 2)
        r = self.api.post('/api/finance/salaires/groupe/',
                          {'employes': [self.emp.id], 'mois': ['2026-01']}, format='json')
        self.assertEqual(r.data['resultats'][0]['statut'], 'deja_paye')

    def test_fiche_de_paie_pdf(self):
        r = self.payer(mois=['2026-01'])
        pdf = self.api.get(f"/api/finance/salaires/{r.data['id']}/fiche/")
        self.assertTrue(pdf.content.startswith(b'%PDF'))

    def test_employe_avec_historique_non_supprimable(self):
        self.payer(mois=['2026-01'])
        self.assertEqual(self.api.delete(f'/api/finance/employes/{self.emp.id}/').status_code, 400)


class ImportExportTests(BaseFinance):
    def test_export_finances_dans_le_catalogue(self):
        r = self.api.get('/api/school/export/catalogue/')
        cles = {j['cle'] for j in r.data['jeux']}
        for cle in ('tarifs', 'paiements', 'mouvements', 'employes', 'salaires', 'avances', 'config_matieres'):
            self.assertIn(cle, cles)
        r = self.api.post('/api/school/export/', {'jeux': 'tous'}, format='json')
        self.assertEqual(r.status_code, 200)

    def test_eleve_parents_via_api(self):
        r = self.api.post('/api/school/eleves/', {
            'nom': 'Rabe', 'prenom': 'Zo', 'sexe': 'F', 'parent_nom': 'M. Rabe', 'parent_mobile': '034 11 111 11'},
            format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['parent_mobile'], '034 11 111 11')
        r = self.api.post('/api/school/eleves/', {
            'nom': 'X', 'prenom': 'Y', 'sexe': 'M', 'parent_mobile': 'abc'}, format='json')
        self.assertEqual(r.status_code, 400)

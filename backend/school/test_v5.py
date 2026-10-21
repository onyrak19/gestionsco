"""Tests de la version 5 : un seul enseignant par matière, photo d'élève,
pièces jointes, impression par classes, coefficient par défaut, journal d'activité."""
import shutil
import tempfile
from io import BytesIO

from django.core.cache import cache
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework.test import APIClient

from journal.models import Activite

from .models import Affectation, AnneeScolaire, Eleve, Inscription, Matiere, PieceJointe
from .tests import BaseTest

MEDIA_TEST = tempfile.mkdtemp(prefix='gestion-scolaire-test-')
PDF = b'%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n'


def image_octets(format_image='JPEG', taille=(900, 700)):
    sortie = BytesIO()
    Image.new('RGB', taille, (30, 90, 200)).save(sortie, format_image)
    return sortie.getvalue()


def fichier_photo(nom='photo.jpg', **kw):
    return SimpleUploadedFile(nom, image_octets(**kw), content_type='image/jpeg')


def fichier_pdf(nom='acte.pdf', contenu=PDF):
    return SimpleUploadedFile(nom, contenu, content_type='application/pdf')


@override_settings(MEDIA_ROOT=MEDIA_TEST)
class BaseV5(BaseTest):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_TEST, ignore_errors=True)

    def setUp(self):
        cache.clear()
        self.admin_client = self.client_de(self.admin)

    def creer_eleve_avec_photo(self, nom='Nouveau'):
        r = self.admin_client.post('/api/school/eleves/', {
            'nom': nom, 'prenom': 'Test', 'sexe': 'F', 'date_naissance': '',
            'photo': fichier_photo(),
        }, format='multipart')
        self.assertEqual(r.status_code, 201, r.data)
        return r.data


# ---------------------------------------------------------------------------
class UnSeulEnseignantParMatiereTests(BaseV5):
    """Une matière n'a qu'un seul enseignant dans une classe donnée."""

    def affecter(self, enseignant, matiere, classe):
        return self.admin_client.post('/api/school/affectations/', {
            'enseignant': enseignant.id, 'matiere': matiere.id, 'classe': classe.id}, format='json')

    def test_un_second_enseignant_pour_la_meme_matiere_est_refuse(self):
        r = self.affecter(self.prof2, self.maths, self.classe_a)    # prof1 a déjà Maths en 6eA
        self.assertEqual(r.status_code, 400)
        self.assertIn('déjà confiée', str(r.data))
        self.assertEqual(Affectation.objects.filter(classe=self.classe_a, matiere=self.maths).count(), 1)

    def test_le_meme_enseignant_deux_fois_est_refuse(self):
        r = self.affecter(self.prof1, self.maths, self.classe_a)
        self.assertEqual(r.status_code, 400)
        self.assertIn('déjà affecté', str(r.data))

    def test_autre_matiere_ou_autre_classe_reste_possible(self):
        self.assertEqual(self.affecter(self.prof2, self.francais, self.classe_a).status_code, 201)
        self.assertEqual(self.affecter(self.prof2, self.maths, self.classe_b).status_code, 201)

    def test_changer_d_enseignant_remplace_l_ancien(self):
        affectation = Affectation.objects.get(classe=self.classe_a, matiere=self.maths)
        r = self.admin_client.patch(f'/api/school/affectations/{affectation.id}/',
                                    {'enseignant': self.prof2.id}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(self.upsert(self.prof2, j1=12).status_code, 200)
        self.assertEqual(self.upsert(self.prof1, j1=10).status_code, 403)
        self.assertEqual(Affectation.objects.filter(classe=self.classe_a, matiere=self.maths).count(), 1)

    def test_la_base_de_donnees_garantit_aussi_la_regle(self):
        from django.db import IntegrityError, transaction
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Affectation.objects.create(enseignant=self.prof2, matiere=self.maths,
                                           classe=self.classe_a, annee_scolaire=self.annee)


# ---------------------------------------------------------------------------
class PhotoEleveTests(BaseV5):
    def test_photo_facultative_a_la_creation(self):
        r = self.admin_client.post('/api/school/eleves/', {
            'nom': 'Sans', 'prenom': 'Photo', 'sexe': 'M', 'date_naissance': ''}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertFalse(r.data['a_photo'])
        self.assertEqual(r.data['photo_token'], '')

    def test_photo_envoyee_reduite_et_convertie_en_jpeg(self):
        data = self.creer_eleve_avec_photo()
        self.assertTrue(data['a_photo'])
        self.assertTrue(data['photo_token'])
        eleve = Eleve.objects.get(pk=data['id'])
        self.assertTrue(eleve.photo.name.startswith('eleves/photos/'))
        with eleve.photo.open('rb') as f:
            image = Image.open(f)
            self.assertEqual(image.format, 'JPEG')
            self.assertLessEqual(max(image.size), 480)
        self.assertNotIn('photo', data)   # le champ d'envoi n'est pas renvoyé

    def test_fichier_qui_n_est_pas_une_image_refuse(self):
        r = self.admin_client.post('/api/school/eleves/', {
            'nom': 'X', 'prenom': 'Y', 'sexe': 'M',
            'photo': SimpleUploadedFile('faux.jpg', b'ceci n est pas une image'),
        }, format='multipart')
        self.assertEqual(r.status_code, 400)
        self.assertIn('photo', r.data)
        self.assertFalse(Eleve.objects.filter(nom='X').exists())

    def test_remplacer_puis_retirer_la_photo_supprime_les_anciens_fichiers(self):
        data = self.creer_eleve_avec_photo()
        eleve = Eleve.objects.get(pk=data['id'])
        premier = eleve.photo.name
        r = self.admin_client.patch(f"/api/school/eleves/{data['id']}/",
                                    {'photo': fichier_photo()}, format='multipart')
        self.assertEqual(r.status_code, 200, r.data)
        eleve.refresh_from_db()
        self.assertNotEqual(eleve.photo.name, premier)
        self.assertFalse(default_storage.exists(premier))
        second = eleve.photo.name
        r = self.admin_client.patch(f"/api/school/eleves/{data['id']}/",
                                    {'retirer_photo': 'true'}, format='multipart')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(r.data['a_photo'])
        self.assertFalse(default_storage.exists(second))

    def test_suppression_de_l_eleve_supprime_sa_photo(self):
        data = self.creer_eleve_avec_photo()
        nom = Eleve.objects.get(pk=data['id']).photo.name
        self.assertTrue(default_storage.exists(nom))
        self.assertEqual(self.admin_client.delete(f"/api/school/eleves/{data['id']}/").status_code, 204)
        self.assertFalse(default_storage.exists(nom))

    def test_acces_a_la_photo(self):
        data = self.creer_eleve_avec_photo()
        eleve = Eleve.objects.get(pk=data['id'])
        # inscrit dans la classe de prof1 : prof1 la voit, prof2 non
        Inscription.objects.create(eleve=eleve, classe=self.classe_a, annee_scolaire=self.annee)
        url = f"/api/school/eleves/{eleve.id}/photo/"
        r = self.admin_client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'image/jpeg')
        self.assertTrue(b''.join(r.streaming_content).startswith(b'\xff\xd8\xff'))
        self.assertEqual(self.client_de(self.prof1).get(url).status_code, 200)
        self.assertEqual(self.client_de(self.prof2).get(url).status_code, 403)
        self.assertEqual(APIClient().get(url).status_code, 401)

    def test_eleve_sans_photo_donne_404(self):
        r = self.admin_client.get(f"/api/school/eleves/{self.eleve_a.id}/photo/")
        self.assertEqual(r.status_code, 404)


# ---------------------------------------------------------------------------
class PiecesJointesTests(BaseV5):
    def setUp(self):
        super().setUp()
        self.eleve_c = Eleve.objects.create(nom='Randria', prenom='Mamy')

    def inscrire(self, **extra):
        donnees = {'eleve': self.eleve_c.id, 'classe': self.classe_a.id, **extra}
        return self.admin_client.post('/api/school/inscriptions/', donnees, format='multipart')

    def test_inscription_sans_piece_jointe(self):
        r = self.admin_client.post('/api/school/inscriptions/', {
            'eleve': self.eleve_c.id, 'classe': self.classe_a.id}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['pieces_jointes'], [])

    def test_inscription_avec_plusieurs_pieces_jointes(self):
        r = self.inscrire(fichiers=[fichier_pdf('acte.pdf'), fichier_photo('scan.jpg')],
                          libelles=['Acte de naissance', 'Carnet'])
        self.assertEqual(r.status_code, 201, r.data)
        pieces = r.data['pieces_jointes']
        self.assertEqual([p['libelle'] for p in pieces], ['Acte de naissance', 'Carnet'])
        self.assertEqual([p['nom_original'] for p in pieces], ['acte.pdf', 'scan.jpg'])
        self.assertEqual(PieceJointe.objects.filter(inscription_id=r.data['id']).count(), 2)

    def test_un_fichier_refuse_annule_toute_l_inscription(self):
        r = self.inscrire(fichiers=[fichier_pdf(), SimpleUploadedFile('virus.exe', b'MZ\x90\x00')])
        self.assertEqual(r.status_code, 400)
        self.assertIn('fichiers', r.data)
        self.assertFalse(Inscription.objects.filter(eleve=self.eleve_c).exists())
        self.assertEqual(PieceJointe.objects.count(), 0)

    def test_faux_pdf_refuse(self):
        r = self.inscrire(fichiers=[fichier_pdf('faux.pdf', b'MZ pas un pdf')])
        self.assertEqual(r.status_code, 400)

    def test_telechargement_et_suppression(self):
        ins = self.inscrire(fichiers=[fichier_pdf()]).data
        piece = ins['pieces_jointes'][0]
        url = f"/api/school/pieces-jointes/{piece['id']}/"
        r = self.admin_client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')
        self.assertEqual(b''.join(r.streaming_content), PDF)
        # un enseignant n'a aucun accès aux documents
        self.assertEqual(self.client_de(self.prof1).get(url).status_code, 403)
        nom = PieceJointe.objects.get(pk=piece['id']).fichier.name
        self.assertEqual(self.admin_client.delete(url).status_code, 204)
        self.assertFalse(default_storage.exists(nom))

    def test_ajout_ulterieur_de_pieces(self):
        ins = self.inscrire().data
        url = f"/api/school/inscriptions/{ins['id']}/pieces/"
        r = self.admin_client.post(url, {'fichiers': [fichier_pdf()], 'libelles': ['Certificat']},
                                   format='multipart')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data[0]['libelle'], 'Certificat')
        self.assertEqual(self.admin_client.post(url, {}, format='multipart').status_code, 400)

    def test_annee_cloturee_dossier_fige(self):
        ins = self.inscrire(fichiers=[fichier_pdf()]).data
        AnneeScolaire.objects.filter(pk=self.annee.pk).update(cloturee=True)
        r = self.admin_client.post(f"/api/school/inscriptions/{ins['id']}/pieces/",
                                   {'fichiers': [fichier_pdf()]}, format='multipart')
        self.assertEqual(r.status_code, 400)
        r = self.admin_client.delete(f"/api/school/pieces-jointes/{ins['pieces_jointes'][0]['id']}/")
        self.assertEqual(r.status_code, 400)

    def test_les_enseignants_ne_voient_pas_les_pieces_jointes(self):
        self.inscrire(fichiers=[fichier_pdf()])
        r = self.client_de(self.prof1).get(f'/api/school/inscriptions/?classe={self.classe_a.id}')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data)
        self.assertTrue(all(i['pieces_jointes'] == [] for i in r.data))
        r = self.admin_client.get(f'/api/school/inscriptions/?classe={self.classe_a.id}')
        self.assertTrue(any(i['pieces_jointes'] for i in r.data))

    def test_le_dossier_de_l_eleve_liste_les_pieces(self):
        self.inscrire(fichiers=[fichier_pdf()])
        r = self.admin_client.get(f'/api/school/eleves/{self.eleve_c.id}/dossier/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data['parcours'][0]['pieces']), 1)


# ---------------------------------------------------------------------------
class ImpressionParClassesTests(BaseV5):
    def bulletins(self, **corps):
        return self.admin_client.post('/api/school/pdf/bulletins/', {'trimestre': 1, **corps}, format='json')

    def test_bulletins_de_plusieurs_classes_dans_un_seul_pdf(self):
        r = self.bulletins(classes=[self.classe_a.id, self.classe_b.id])
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')
        self.assertTrue(r.content.startswith(b'%PDF'))
        ligne = Activite.objects.filter(categorie='impression').first()
        self.assertIn('2 classe(s)', ligne.description)
        self.assertIn('1er trimestre', ligne.description)

    def test_bulletins_de_toute_l_annee(self):
        self.assertEqual(self.bulletins(annee=self.annee.id).status_code, 200)

    def test_classes_doit_etre_une_liste_non_vide_de_classes_avec_eleves(self):
        self.assertEqual(self.bulletins(classes='6eA').status_code, 400)
        self.assertEqual(self.bulletins(classes=['abc']).status_code, 400)
        self.assertEqual(self.bulletins(classes=[]).status_code, 400)

    def test_reserve_a_l_administrateur(self):
        r = self.client_de(self.prof1).post('/api/school/pdf/bulletins/',
                                            {'classes': [self.classe_a.id], 'trimestre': 1}, format='json')
        self.assertEqual(r.status_code, 403)


# ---------------------------------------------------------------------------
class CoefficientParDefautTests(BaseV5):
    def test_le_coefficient_par_defaut_se_modifie_sans_toucher_au_code(self):
        code = self.maths.code
        r = self.admin_client.patch(f'/api/school/matieres/{self.maths.id}/', {'coefficient': 5}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['coefficient'], 5)
        self.assertEqual(r.data['code'], code)
        ligne = Activite.objects.filter(categorie='matiere', action='modification').first()
        self.assertIn('coefficient par défaut : 3 → 5', ligne.description)

    def test_coefficient_invalide_refuse(self):
        r = self.admin_client.patch(f'/api/school/matieres/{self.maths.id}/', {'coefficient': 0}, format='json')
        self.assertEqual(r.status_code, 400)


# ---------------------------------------------------------------------------
class JournalActiviteTests(BaseV5):
    def test_saisie_de_note_tracee_avec_qui_quoi_quand(self):
        self.assertEqual(self.upsert(self.prof1, j1=12, examen=14).status_code, 200)
        ligne = Activite.objects.get(categorie='note')
        self.assertEqual(ligne.action, 'creation')
        self.assertEqual(ligne.utilisateur, self.prof1)
        self.assertEqual(ligne.utilisateur_role, 'enseignant')
        self.assertEqual(ligne.matiere, 'Maths')
        self.assertEqual(ligne.annee, '2026-2027')
        self.assertEqual(ligne.classe, '6eA')
        self.assertEqual(ligne.eleve, 'Rakoto Jean')
        self.assertIsNotNone(ligne.date)
        for morceau in ('Enseignant', 'a saisi la note de Rakoto Jean', 'Maths', 'J1 = 12', 'Examen = 14'):
            self.assertIn(morceau, ligne.description)

    def test_modification_tracee_et_resaisie_identique_ignoree(self):
        self.upsert(self.prof1, j1=12)
        self.upsert(self.prof1, j1=12)                      # rien n'a changé : pas de nouvelle ligne
        self.assertEqual(Activite.objects.filter(categorie='note').count(), 1)
        self.upsert(self.prof1, j1=15)
        derniere = Activite.objects.filter(categorie='note').first()
        self.assertEqual(derniere.action, 'modification')
        self.assertIn('J1 : 12 → 15', derniere.description)
        self.upsert(self.prof1, j1=None)                    # effacement
        self.assertIn('J1 : 15 → (vide)', Activite.objects.filter(categorie='note').first().description)

    def test_note_refusee_n_est_pas_tracee(self):
        self.assertEqual(self.upsert(self.prof1, j1=25).status_code, 400)
        self.assertEqual(self.upsert(self.prof2, j1=10).status_code, 403)
        self.assertFalse(Activite.objects.filter(categorie='note').exists())

    def test_inscription_creation_et_suppression_tracees(self):
        eleve = Eleve.objects.create(nom='Randria', prenom='Mamy')
        r = self.admin_client.post('/api/school/inscriptions/',
                                   {'eleve': eleve.id, 'classe': self.classe_a.id}, format='json')
        ligne = Activite.objects.get(categorie='inscription', action='creation')
        self.assertIn('a inscrit Randria Mamy en 6eA', ligne.description)
        self.assertEqual(ligne.utilisateur_role, 'admin')
        self.admin_client.delete(f"/api/school/inscriptions/{r.data['id']}/")
        self.assertTrue(Activite.objects.filter(categorie='inscription', action='suppression').exists())

    def test_creation_modification_suppression_d_une_classe(self):
        r = self.admin_client.post('/api/school/classes/', {
            'niveau': '5ème', 'numero': 1, 'annee_scolaire': self.annee.id}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.admin_client.patch(f"/api/school/classes/{r.data['id']}/", {'numero': 2}, format='json')
        self.admin_client.delete(f"/api/school/classes/{r.data['id']}/")
        actions = list(Activite.objects.filter(categorie='classe').order_by('id').values_list('action', flat=True))
        self.assertEqual(actions, ['creation', 'modification', 'suppression'])

    def test_affectation_tracee(self):
        self.admin_client.post('/api/school/affectations/', {
            'enseignant': self.prof2.id, 'matiere': self.francais.id, 'classe': self.classe_a.id}, format='json')
        ligne = Activite.objects.get(categorie='affectation')
        self.assertIn('Français', ligne.description)
        self.assertEqual(ligne.classe, '6eA')

    def test_connexions_tracees_sans_recopier_l_identifiant_saisi(self):
        c = APIClient()
        c.post('/api/auth/login/', {'username': 'prof1', 'password': MDP}, format='json')
        self.assertTrue(Activite.objects.filter(categorie='connexion', action='connexion',
                                                utilisateur=self.prof1).exists())
        c.post('/api/auth/login/', {'username': 'prof1', 'password': 'faux'}, format='json')
        self.assertTrue(Activite.objects.filter(action='echec', utilisateur=self.prof1).exists())
        c.post('/api/auth/login/', {'username': 'MotDePasseTapeIci', 'password': 'x'}, format='json')
        inconnu = Activite.objects.filter(action='echec', utilisateur__isnull=True).get()
        self.assertNotIn('MotDePasseTapeIci', inconnu.description)

    def test_validation_d_un_enseignant_tracee(self):
        en_attente = creer_user_attente()
        self.admin_client.patch(f'/api/auth/enseignants/{en_attente.id}/', {'statut': 'valide'}, format='json')
        ligne = Activite.objects.get(categorie='enseignant', action='validation')
        self.assertIn('a validé le compte', ligne.description)

    def test_le_journal_est_reserve_a_l_administrateur(self):
        self.upsert(self.prof1, j1=10)
        self.assertEqual(self.client_de(self.prof1).get('/api/journal/').status_code, 403)
        self.assertEqual(APIClient().get('/api/journal/').status_code, 401)
        r = self.admin_client.get('/api/journal/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['count'], len(r.data['results']))
        self.assertIn('description', r.data['results'][0])

    def test_aucune_modification_possible_via_l_api(self):
        self.upsert(self.prof1, j1=10)
        ligne = Activite.objects.first()
        for methode in ('put', 'patch', 'delete'):
            r = getattr(self.admin_client, methode)(f'/api/journal/{ligne.id}/')
            self.assertIn(r.status_code, (404, 405))


def creer_user_attente():
    from django.contrib.auth.models import User
    from accounts.models import UserProfile
    user = User.objects.create_user('attente', 'attente@ecole.test', 'Passw0rd!secret',
                                    first_name='Nina', last_name='Rabe')
    UserProfile.objects.create(user=user, role='enseignant', statut='en_attente')
    return user


MDP = 'Passw0rd!secret'

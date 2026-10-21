import io
from contextlib import redirect_stdout

from django.contrib.auth.models import User
from django.core.cache import cache
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from .models import UserProfile

MDP = 'Passw0rd!secret'


def creer_user(username, role='enseignant', statut='valide', mdp=MDP):
    user = User.objects.create_user(username, f'{username}@ecole.test', mdp)
    UserProfile.objects.create(user=user, role=role, statut=statut)
    return user


class BaseTest(APITestCase):
    def setUp(self):
        cache.clear()  # remet à zéro les compteurs anti force brute
        self.admin = creer_user('admin', role='admin')
        self.prof = creer_user('prof')

    def client_de(self, user):
        c = APIClient()
        c.force_authenticate(user)
        return c


class LoginTests(BaseTest):
    def login(self, username, password=MDP, **extra):
        return APIClient().post('/api/auth/login/',
                                {'username': username, 'password': password},
                                format='json', **extra)

    def test_connexion_reussie(self):
        for username, role in (('admin', 'admin'), ('prof', 'enseignant')):
            r = self.login(username)
            self.assertEqual(r.status_code, 200)
            self.assertIn('access', r.data)
            self.assertIn('refresh', r.data)
            self.assertEqual(r.data['user']['profile']['role'], role)

    def test_identifiants_invalides(self):
        self.assertEqual(self.login('prof', 'mauvais').status_code, 401)
        self.assertEqual(self.login('inconnu').status_code, 401)

    def test_champs_manquants(self):
        r = APIClient().post('/api/auth/login/', {}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_statuts_bloques_avec_message(self):
        attendus = {
            'en_attente': 'en attente de validation',
            'refuse': 'refusée',
            'desactive': 'désactivé',
        }
        for statut, extrait in attendus.items():
            creer_user(f'p_{statut}', statut=statut)
            r = self.login(f'p_{statut}')
            self.assertEqual(r.status_code, 403, statut)
            self.assertIn(extrait, r.data['error'])

    def test_compte_sans_profil_refuse(self):
        User.objects.create_user('sansprofil', 'x@x.fr', MDP)
        r = self.login('sansprofil')
        self.assertEqual(r.status_code, 403)
        self.assertIn("pas de profil", r.data['error'])

    def test_superuser_recoit_un_profil_admin_et_peut_se_connecter(self):
        # Reproduit `manage.py createsuperuser`
        User.objects.create_superuser('root', 'root@ecole.test', MDP)
        profil = UserProfile.objects.get(user__username='root')
        self.assertEqual((profil.role, profil.statut), ('admin', 'valide'))
        self.assertEqual(self.login('root').status_code, 200)

    def test_le_mot_de_passe_n_est_jamais_affiche(self):
        sortie = io.StringIO()
        with redirect_stdout(sortie):
            self.login('prof', 'MotDePasseSecret42')
            self.login('prof')
        self.assertNotIn('MotDePasseSecret42', sortie.getvalue())
        self.assertNotIn(MDP, sortie.getvalue())

    def test_un_ancien_token_invalide_ne_bloque_pas_la_connexion(self):
        r = self.login('prof', HTTP_AUTHORIZATION='Bearer token.expire.ou.faux')
        self.assertEqual(r.status_code, 200)

    def test_limitation_des_tentatives(self):
        codes = [self.login('prof', 'mauvais').status_code for _ in range(11)]
        self.assertEqual(codes[:10], [401] * 10)
        self.assertEqual(codes[10], 429)


class InscriptionEnseignantTests(BaseTest):
    donnees = {
        'username': 'nouveau', 'email': 'nouveau@ecole.test',
        'password': 'Un-Bon-Mdp-2026', 'nom': 'Rakoto', 'prenom': 'Jean',
        'telephone': '0340000000',
    }

    def inscrire(self, **modifs):
        return APIClient().post('/api/auth/inscription-enseignant/',
                                {**self.donnees, **modifs}, format='json')

    def test_inscription_cree_un_compte_en_attente(self):
        r = self.inscrire()
        self.assertEqual(r.status_code, 201)
        user = User.objects.get(username='nouveau')
        self.assertEqual(user.profile.role, 'enseignant')
        self.assertEqual(user.profile.statut, 'en_attente')
        self.assertEqual(user.profile.telephone, '0340000000')
        self.assertEqual((user.last_name, user.first_name), ('Rakoto', 'Jean'))
        self.assertTrue(user.check_password('Un-Bon-Mdp-2026'))

    def test_email_deja_utilise_refuse_sans_tenir_compte_de_la_casse(self):
        r = self.inscrire(email='PROF@ecole.test')
        self.assertEqual(r.status_code, 400)
        self.assertIn('email', r.data)

    def test_email_obligatoire(self):
        self.assertEqual(self.inscrire(email='').status_code, 400)

    def test_mots_de_passe_faibles_refuses(self):
        for faible in ('123456', 'password', 'abc', '12345678'):
            r = self.inscrire(password=faible)
            self.assertEqual(r.status_code, 400, faible)
            self.assertIn('password', r.data)
        self.assertFalse(User.objects.filter(username='nouveau').exists())

    def test_nom_trop_long_refuse_proprement(self):
        self.assertEqual(self.inscrire(nom='x' * 151).status_code, 400)


class GestionEnseignantsTests(BaseTest):
    def test_liste_reservee_a_l_admin_et_filtrable(self):
        creer_user('attente', statut='en_attente')
        r = self.client_de(self.admin).get('/api/auth/enseignants/')
        self.assertEqual([u['username'] for u in r.data], ['attente'])
        r = self.client_de(self.admin).get('/api/auth/enseignants/?statut=valide')
        self.assertEqual([u['username'] for u in r.data], ['prof'])
        self.assertEqual(self.client_de(self.prof).get('/api/auth/enseignants/').status_code, 403)
        self.assertEqual(APIClient().get('/api/auth/enseignants/').status_code, 401)

    def test_l_admin_change_le_statut(self):
        attente = creer_user('attente', statut='en_attente')
        r = self.client_de(self.admin).patch(
            f'/api/auth/enseignants/{attente.id}/', {'statut': 'valide'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['profile']['statut'], 'valide')
        attente.profile.refresh_from_db()
        self.assertEqual(attente.profile.statut, 'valide')

    def test_un_compte_admin_n_est_pas_modifiable_par_ce_endpoint(self):
        r = self.client_de(self.admin).patch(
            f'/api/auth/enseignants/{self.admin.id}/', {'statut': 'desactive'}, format='json')
        self.assertEqual(r.status_code, 404)
        self.admin.profile.refresh_from_db()
        self.assertEqual(self.admin.profile.statut, 'valide')

    def test_un_enseignant_ne_peut_pas_changer_les_statuts(self):
        r = self.client_de(self.prof).patch(
            f'/api/auth/enseignants/{self.prof.id}/', {'statut': 'valide'}, format='json')
        self.assertEqual(r.status_code, 403)

    def test_email_deja_pris_refuse(self):
        r = self.client_de(self.admin).patch(
            f'/api/auth/enseignants/{self.prof.id}/', {'email': 'admin@ecole.test'}, format='json')
        self.assertEqual(r.status_code, 400)


class StatutEnTempsReelTests(BaseTest):
    """Un compte désactivé perd l'accès immédiatement, même avec un token valide."""

    def test_token_existant_refuse_apres_desactivation(self):
        token = str(RefreshToken.for_user(self.prof).access_token)
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(c.get('/api/auth/profile/').status_code, 200)

        self.prof.profile.statut = 'desactive'
        self.prof.profile.save()
        r = c.get('/api/auth/profile/')
        self.assertEqual(r.status_code, 401)
        self.assertIn('désactivé', r.data['detail'])

    def test_renouvellement_du_token(self):
        refresh = str(RefreshToken.for_user(self.prof))
        r = APIClient().post('/api/token/refresh/', {'refresh': refresh}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertIn('access', r.data)

        self.prof.profile.statut = 'refuse'
        self.prof.profile.save()
        r = APIClient().post('/api/token/refresh/', {'refresh': refresh}, format='json')
        self.assertEqual(r.status_code, 401)

    def test_refresh_invalide(self):
        r = APIClient().post('/api/token/refresh/', {'refresh': 'nimportequoi'}, format='json')
        self.assertEqual(r.status_code, 401)

    def test_reactivation_redonne_l_acces(self):
        self.prof.profile.statut = 'desactive'
        self.prof.profile.save()
        self.prof.profile.statut = 'valide'
        self.prof.profile.save()
        token = str(RefreshToken.for_user(self.prof).access_token)
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(c.get('/api/auth/profile/').status_code, 200)

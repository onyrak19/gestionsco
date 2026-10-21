import os
from io import StringIO
from unittest import mock

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from accounts.models import UserProfile


def lancer(**variables):
    sortie = StringIO()
    base = {'ADMIN_USERNAME': '', 'ADMIN_PASSWORD': '', 'ADMIN_EMAIL': '', 'ADMIN_RESET_PASSWORD': ''}
    base.update(variables)
    with mock.patch.dict(os.environ, base):
        call_command('creer_admin', stdout=sortie)
    return sortie.getvalue()


class CreerAdminTests(TestCase):
    def test_cree_un_administrateur_avec_profil(self):
        lancer(ADMIN_USERNAME='directeur', ADMIN_PASSWORD='MotDePasse123')
        user = User.objects.get(username='directeur')
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.check_password('MotDePasse123'))
        profil = UserProfile.objects.get(user=user)
        self.assertEqual((profil.role, profil.statut), ('admin', 'valide'))

    def test_nom_par_defaut_admin(self):
        lancer(ADMIN_PASSWORD='MotDePasse123')
        self.assertTrue(User.objects.filter(username='admin', is_superuser=True).exists())

    def test_sans_mot_de_passe_rien_n_est_cree(self):
        lancer()
        self.assertEqual(User.objects.count(), 0)

    def test_mot_de_passe_trop_court(self):
        lancer(ADMIN_PASSWORD='abc')
        self.assertEqual(User.objects.count(), 0)

    def test_relance_ne_change_pas_le_mot_de_passe(self):
        lancer(ADMIN_PASSWORD='MotDePasse123')
        lancer(ADMIN_PASSWORD='AutreMotDePasse456')
        self.assertTrue(User.objects.get(username='admin').check_password('MotDePasse123'))
        self.assertEqual(User.objects.count(), 1)

    def test_reinitialisation_explicite(self):
        lancer(ADMIN_PASSWORD='MotDePasse123')
        lancer(ADMIN_PASSWORD='AutreMotDePasse456', ADMIN_RESET_PASSWORD='True')
        self.assertTrue(User.objects.get(username='admin').check_password('AutreMotDePasse456'))

    def test_ne_promeut_pas_un_enseignant(self):
        User.objects.create_user('admin', password='x-Enseignant-1')
        lancer(ADMIN_PASSWORD='MotDePasse123')
        self.assertFalse(User.objects.get(username='admin').is_superuser)

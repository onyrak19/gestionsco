from datetime import date, datetime, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from accounts.models import UserProfile

from . import services
from .models import Activite


def creer(username, role='enseignant'):
    user = User.objects.create_user(username, f'{username}@ecole.test', 'Passw0rd!secret',
                                    first_name='Jean', last_name=username.capitalize())
    UserProfile.objects.create(user=user, role=role, statut='valide')
    return user


class ServicesTests(APITestCase):
    def test_valeurs_lisibles(self):
        self.assertEqual(services.valeur_lisible(None), '(vide)')
        self.assertEqual(services.valeur_lisible(''), '(vide)')
        self.assertEqual(services.valeur_lisible(True), 'oui')
        self.assertEqual(services.valeur_lisible(Decimal('12.50')), '12,5')
        self.assertEqual(services.valeur_lisible(Decimal('10.00')), '10')
        self.assertEqual(services.valeur_lisible(date(2026, 9, 1)), '01/09/2026')
        self.assertEqual(services.valeur_lisible(3), '3')

    def test_difference_ne_garde_que_ce_qui_change(self):
        libelles = {'nom': 'nom', 'coefficient': 'coefficient'}
        self.assertEqual(
            services.difference({'nom': 'A', 'coefficient': 1}, {'nom': 'A', 'coefficient': 2}, libelles),
            'coefficient : 1 → 2')
        self.assertEqual(services.difference({'nom': 'A'}, {'nom': 'A'}, libelles), '')

    def test_acteur(self):
        admin = creer('admin', 'admin')
        self.assertEqual(services.acteur(admin), 'Administrateur Jean Admin')
        self.assertEqual(services.acteur(creer('prof')), 'Enseignant Jean Prof')
        self.assertEqual(services.acteur(None), 'Un visiteur')

    def test_enregistrer_ne_leve_jamais_d_exception(self):
        # utilisateur invalide + champs trop longs : la ligne est tronquée, rien ne plante
        services.enregistrer(None, 'note', 'creation', 'x', annee='2' * 50, classe='c' * 200)
        ligne = Activite.objects.get()
        self.assertEqual(len(ligne.annee), 20)
        self.assertEqual(len(ligne.classe), 60)
        # catégorie absente du modèle : la base accepte la valeur, le service ne plante pas non plus
        services.enregistrer(None, 'inconnue', 'creation', 'y')


class JournalApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = creer('admin', 'admin')
        cls.prof = creer('prof')

    def setUp(self):
        self.c = APIClient()
        self.c.force_authenticate(self.admin)
        services.enregistrer(None, 'note', 'creation', 'Note de Marie en SVT', utilisateur=self.prof,
                             annee='2025-2026', classe='3ème 1', matiere='SVT', eleve='Marie Dupont')
        services.enregistrer(None, 'inscription', 'creation', 'Inscription de Paul', utilisateur=self.admin,
                             annee='2026-2027', classe='6ème 1', eleve='Paul Martin')
        services.enregistrer(None, 'connexion', 'connexion', 'Connexion', utilisateur=self.prof)

    def lire(self, **params):
        r = self.c.get('/api/journal/', params)
        self.assertEqual(r.status_code, 200, r.data)
        return r.data

    def test_du_plus_recent_au_plus_ancien_et_pagine(self):
        data = self.lire(page_size=2)
        self.assertEqual(data['count'], 3)
        self.assertEqual(len(data['results']), 2)
        self.assertEqual(data['results'][0]['categorie'], 'connexion')
        self.assertIsNotNone(data['next'])

    def test_filtres(self):
        self.assertEqual(self.lire(categorie='note')['count'], 1)
        self.assertEqual(self.lire(utilisateur=self.prof.id)['count'], 2)
        self.assertEqual(self.lire(annee='2026-2027')['count'], 1)
        self.assertEqual(self.lire(action='connexion')['count'], 1)
        self.assertEqual(self.lire(q='svt')['count'], 1)           # insensible à la casse
        self.assertEqual(self.lire(q='Paul')['count'], 1)
        self.assertEqual(self.lire(q='introuvable')['count'], 0)

    def test_filtre_par_dates_bornes_incluses(self):
        ancienne = Activite.objects.get(categorie='note')
        hier = timezone.now() - timedelta(days=1)
        Activite.objects.filter(pk=ancienne.pk).update(date=hier)
        jour = timezone.localtime(hier).date().isoformat()
        self.assertEqual(self.lire(date_debut=jour, date_fin=jour)['count'], 1)
        aujourdhui = timezone.localdate().isoformat()
        self.assertEqual(self.lire(date_debut=aujourdhui)['count'], 2)

    def test_parametres_invalides(self):
        self.assertEqual(self.c.get('/api/journal/', {'utilisateur': 'abc'}).status_code, 400)
        self.assertEqual(self.c.get('/api/journal/', {'date_debut': '31/12/2026'}).status_code, 400)

    def test_filtres_proposes(self):
        r = self.c.get('/api/journal/filtres/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual({u['nom'] for u in r.data['utilisateurs']}, {'Jean Admin', 'Jean Prof'})
        self.assertEqual(r.data['annees'], ['2026-2027', '2025-2026'])
        self.assertTrue(any(c['value'] == 'note' for c in r.data['categories']))

    def test_acces_reserve_a_l_administrateur(self):
        prof = APIClient()
        prof.force_authenticate(self.prof)
        self.assertEqual(prof.get('/api/journal/').status_code, 403)
        self.assertEqual(prof.get('/api/journal/filtres/').status_code, 403)

    def test_le_nom_reste_lisible_apres_suppression_de_l_utilisateur(self):
        self.prof.delete()
        ligne = Activite.objects.get(categorie='note')
        self.assertIsNone(ligne.utilisateur)
        self.assertEqual(ligne.utilisateur_nom, 'Jean Prof')

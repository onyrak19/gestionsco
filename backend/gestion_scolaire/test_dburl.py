import unittest

from gestion_scolaire.dburl import config_depuis_url


class ConfigDepuisUrlTests(unittest.TestCase):
    def test_adresse_render_complete(self):
        c = config_depuis_url('postgresql://ecole_user:s3cret@dpg-abc123-a:5432/ecole_db')
        self.assertEqual(c['ENGINE'], 'django.db.backends.postgresql')
        self.assertEqual(c['NAME'], 'ecole_db')
        self.assertEqual(c['USER'], 'ecole_user')
        self.assertEqual(c['PASSWORD'], 's3cret')
        self.assertEqual(c['HOST'], 'dpg-abc123-a')
        self.assertEqual(c['PORT'], '5432')
        self.assertTrue(c['CONN_HEALTH_CHECKS'])

    def test_schema_postgres_et_sans_port(self):
        c = config_depuis_url('postgres://u:p@hote/base')
        self.assertEqual(c['HOST'], 'hote')
        self.assertEqual(c['PORT'], '')

    def test_mot_de_passe_avec_caracteres_speciaux(self):
        c = config_depuis_url('postgresql://u:p%40ss%2Fw%3Ard@hote:5432/base')
        self.assertEqual(c['PASSWORD'], 'p@ss/w:rd')

    def test_sslmode_conserve(self):
        c = config_depuis_url('postgresql://u:p@hote:5432/base?sslmode=require')
        self.assertEqual(c['OPTIONS'], {'sslmode': 'require'})

    def test_refuse_autre_schema(self):
        with self.assertRaises(ValueError):
            config_depuis_url('mysql://u:p@hote/base')

    def test_refuse_base_absente(self):
        with self.assertRaises(ValueError):
            config_depuis_url('postgresql://u:p@hote:5432/')

    def test_refuse_port_invalide(self):
        with self.assertRaises(ValueError):
            config_depuis_url('postgresql://u:p@hote:abc/base')

    def test_erreur_sans_fuite_du_mot_de_passe(self):
        try:
            config_depuis_url('mysql://u:MOTDEPASSE@hote/base')
        except ValueError as e:
            self.assertNotIn('MOTDEPASSE', str(e))


if __name__ == '__main__':
    unittest.main()

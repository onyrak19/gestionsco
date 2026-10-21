import { formatApiError } from './errors';

const erreur = (status, data) => ({ response: { status, data } });

test('erreurs de champs DRF', () => {
  expect(formatApiError(erreur(400, { password: ['Trop court.', 'Trop commun.'] })))
    .toBe('password : Trop court. Trop commun.');
});

test('erreur globale, detail et error sans préfixe', () => {
  expect(formatApiError(erreur(400, { non_field_errors: ['Année clôturée.'] }))).toBe('Année clôturée.');
  expect(formatApiError(erreur(403, { detail: 'Interdit.' }))).toBe('Interdit.');
  expect(formatApiError(erreur(401, { error: 'Identifiants invalides' }))).toBe('Identifiants invalides');
});

test('serveur injoignable et erreur 500', () => {
  expect(formatApiError({})).toMatch(/joindre le serveur/);
  expect(formatApiError(erreur(500, '<html>'))).toMatch(/Erreur du serveur/);
});

import { calculerMoyennes, formatNote } from './notes';

test('une note à 0 compte dans la moyenne', () => {
  const r = calculerMoyennes({ j1: '0', j2: '10', j3: '', examen: '0' });
  expect(r.moyenneJournaliere).toBe(5);
  expect(r.moyenneMatiere).toBe(2.5);
});

test('cases vides : aucune moyenne', () => {
  expect(calculerMoyennes({})).toEqual({ moyenneJournaliere: null, moyenneMatiere: null });
  expect(calculerMoyennes({ j1: '', examen: '' }).moyenneMatiere).toBeNull();
});

test("une seule composante : on prend celle qui existe", () => {
  expect(calculerMoyennes({ examen: '14' }).moyenneMatiere).toBe(14);
  expect(calculerMoyennes({ j1: 9, j2: 10 }).moyenneMatiere).toBe(9.5);
});

test('même résultat que le backend : (moy. journalière + examen) / 2', () => {
  expect(calculerMoyennes({ j1: '12.5', examen: '14' }).moyenneMatiere).toBe(13.25);
});

test('formatNote', () => {
  expect(formatNote(null)).toBe('-');
  expect(formatNote(12.5)).toBe('12.50');
});

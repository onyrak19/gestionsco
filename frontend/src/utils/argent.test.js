import { formaterMontant, lireMontant, libelleMois, dateFr, moisEntre } from './argent';

describe('formaterMontant', () => {
  test('sépare les milliers et ajoute la devise', () => {
    expect(formaterMontant(25000)).toBe('25\u00a0000\u00a0Ar');
    expect(formaterMontant(1250000, 'Ar')).toBe('1\u00a0250\u00a0000\u00a0Ar');
  });
  test('affiche les centimes seulement s’il y en a', () => {
    expect(formaterMontant(1250.5)).toBe('1\u00a0250,50\u00a0Ar');
    expect(formaterMontant('300.00')).toBe('300\u00a0Ar');
  });
  test('valeur absente : tiret', () => {
    expect(formaterMontant(null)).toBe('—');
    expect(formaterMontant('')).toBe('—');
  });
  test('sans devise et montant négatif', () => {
    expect(formaterMontant(-4500, '')).toBe('-4\u00a0500');
  });
});

describe('lireMontant', () => {
  test('accepte espaces et virgule', () => {
    expect(lireMontant('25 000')).toBe(25000);
    expect(lireMontant('1250,5')).toBe(1250.5);
  });
  test('vide ou invalide : null', () => {
    expect(lireMontant('')).toBeNull();
    expect(lireMontant('abc')).toBeNull();
  });
});

describe('mois et dates', () => {
  test('libellé d’un mois', () => {
    expect(libelleMois('2026-09')).toBe('Septembre 2026');
    expect(libelleMois('2027-02')).toBe('Février 2027');
  });
  test('date française', () => {
    expect(dateFr('2026-10-14')).toBe('14/10/2026');
    expect(dateFr(null)).toBe('');
  });
  test('mois d’une année scolaire', () => {
    const mois = moisEntre('2026-09-01', '2027-06-30');
    expect(mois[0]).toBe('2026-09');
    expect(mois).toHaveLength(10);
    expect(mois[mois.length - 1]).toBe('2027-06');
  });
});

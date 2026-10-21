import { formatTaille, verifierPiece } from './fichiers';

jest.mock('../api/axios', () => ({ __esModule: true, default: { get: jest.fn() } }));

const fichier = (nom, taille = 1000) => ({ name: nom, size: taille });

test('tailles lisibles', () => {
  expect(formatTaille(512)).toBe('512 o');
  expect(formatTaille(2048)).toBe('2 Ko');
  expect(formatTaille(1.5 * 1024 * 1024)).toBe('1,5 Mo');
});

test('pièces jointes : formats, taille et fichiers vides', () => {
  expect(verifierPiece(fichier('acte.PDF'))).toBe('');
  expect(verifierPiece(fichier('scan.jpeg'))).toBe('');
  expect(verifierPiece(fichier('virus.exe'))).toMatch(/non accepté/);
  expect(verifierPiece(fichier('sans_extension'))).toMatch(/non accepté/);
  expect(verifierPiece(fichier('vide.pdf', 0))).toMatch(/vide/);
  expect(verifierPiece(fichier('gros.pdf', 11 * 1024 * 1024))).toMatch(/10 Mo/);
});

export const DECISIONS = {
  en_cours: 'En cours',
  passant: 'Passant',
  redoublant: 'Redoublant',
  non_decide: 'À décider',
};

export const TRIMESTRES = [
  { value: 1, label: '1er trimestre' },
  { value: 2, label: '2e trimestre' },
  { value: 3, label: '3e trimestre' },
];

// Notes en dessous de 10 : mises en évidence
export const classeNote = (v) => (v === null || v === undefined ? '' : v < 10 ? 'note-basse' : 'note-ok');

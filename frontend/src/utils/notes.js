// Calcul des moyennes : même règle que le backend (school/models.py).
// Une case vide = pas de note ; 0 est une vraie note.
const estRenseignee = (v) => v !== '' && v !== null && v !== undefined && !isNaN(Number(v));

// Arrondi à 2 décimales, 0,005 arrondi vers le haut
const arrondi = (x) => Math.round((x + Number.EPSILON) * 100) / 100;

export const calculerMoyennes = (note = {}) => {
  const js = [note.j1, note.j2, note.j3].filter(estRenseignee).map(Number);
  const mj = js.length ? js.reduce((a, b) => a + b, 0) / js.length : null;
  const ex = estRenseignee(note.examen) ? Number(note.examen) : null;

  let mm = null;
  if (mj !== null && ex !== null) mm = (mj + ex) / 2;
  else if (mj !== null) mm = mj;
  else if (ex !== null) mm = ex;

  return {
    moyenneJournaliere: mj === null ? null : arrondi(mj),
    moyenneMatiere: mm === null ? null : arrondi(mm),
  };
};

export const formatNote = (v) => (v === null || v === undefined ? '-' : Number(v).toFixed(2));

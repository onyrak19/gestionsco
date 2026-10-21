// Montants et mois : mêmes règles d'affichage que le serveur (finance/outils.py).
const MOIS_FR = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août',
  'septembre', 'octobre', 'novembre', 'décembre'];

const NBSP = '\u00a0';

// 25000 -> « 25 000 Ar » ; 1250.5 -> « 1 250,50 Ar » ; vide -> « — »
export const formaterMontant = (valeur, devise = 'Ar') => {
  if (valeur === null || valeur === undefined || valeur === '' || isNaN(Number(valeur))) return '—';
  const n = Math.round((Number(valeur) + Number.EPSILON) * 100) / 100;
  const entier = Number.isInteger(n);
  const [partieEntiere, decimales] = Math.abs(n).toFixed(entier ? 0 : 2).split('.');
  const groupes = partieEntiere.replace(/\B(?=(\d{3})+(?!\d))/g, NBSP);
  const texte = `${n < 0 ? '-' : ''}${groupes}${decimales ? `,${decimales}` : ''}`;
  return devise ? `${texte}${NBSP}${devise}` : texte;
};

// Champ de saisie -> nombre (accepte « 25 000 » ou « 1250,5 ») ; null si vide ou invalide
export const lireMontant = (texte) => {
  if (texte === null || texte === undefined) return null;
  const propre = String(texte).replace(/[\s\u00a0]/g, '').replace(',', '.');
  if (propre === '' || isNaN(Number(propre))) return null;
  return Number(propre);
};

const deux = (n) => String(n).padStart(2, '0');

// Date du jour au format AAAA-MM-JJ (heure locale)
export const dateDuJour = (d = new Date()) => `${d.getFullYear()}-${deux(d.getMonth() + 1)}-${deux(d.getDate())}`;

// Mois courant au format AAAA-MM
export const moisCourant = (d = new Date()) => `${d.getFullYear()}-${deux(d.getMonth() + 1)}`;

// '2026-09' -> 'Septembre 2026'
export const libelleMois = (cle) => {
  const m = /^(\d{4})-(\d{2})/.exec(cle || '');
  if (!m) return cle || '';
  const nom = MOIS_FR[Number(m[2]) - 1] || '';
  return `${nom.charAt(0).toUpperCase()}${nom.slice(1)} ${m[1]}`;
};

// '2026-10-14' -> '14/10/2026'
export const dateFr = (iso) => {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || '');
  return m ? `${m[3]}/${m[2]}/${m[1]}` : '';
};

// Les 12 mois d'une année scolaire à partir de deux dates ISO : ['2026-09', ...]
export const moisEntre = (debutIso, finIso) => {
  const d = /^(\d{4})-(\d{2})/.exec(debutIso || '');
  const f = /^(\d{4})-(\d{2})/.exec(finIso || '');
  if (!d || !f) return [];
  let a = Number(d[1]); let m = Number(d[2]);
  const af = Number(f[1]); const mf = Number(f[2]);
  const mois = [];
  while ((a < af || (a === af && m <= mf)) && mois.length < 24) {
    mois.push(`${a}-${deux(m)}`);
    m += 1;
    if (m > 12) { m = 1; a += 1; }
  }
  return mois;
};

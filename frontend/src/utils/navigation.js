// Plan de navigation de l'application : trois espaces pour l'administration
// (Scolarité, Finances, Outils) et un menu simple pour les enseignants.
// Layout, palette de recherche, fil d'Ariane et page d'accueil lisent tous ce fichier.

const lien = (to, label, icone, extra = {}) => ({ to, label, icone, ...extra });

export const ESPACES = [
  { cle: 'scolarite', label: 'Scolarité', icone: 'eleve', to: '/admin/scolarite', aide: 'Élèves, classes, notes et bulletins' },
  { cle: 'finances', label: 'Finances', icone: 'argent', to: '/admin/finances', aide: 'Encaissements, dépenses et salaires' },
  { cle: 'outils', label: 'Outils', icone: 'reglages', to: '/admin/donnees', aide: 'Import / export, journal, établissement' },
];

export const MENUS = {
  accueil: [
    { titre: 'Raccourcis' },
    lien('/admin/inscriptions', 'Inscrire un élève', 'plus'),
    lien('/admin/notes', 'Saisir des notes', 'crayon'),
    lien('/admin/finances/encaissements', 'Encaisser un élève', 'argent'),
    lien('/admin/finances/depenses', 'Saisir une dépense', 'montee'),
  ],
  scolarite: [
    lien('/admin/scolarite', 'Tableau de bord', 'accueil', { end: true }),
    { titre: 'Élèves' },
    lien('/admin/eleves', 'Élèves', 'eleve', { mots: 'fiche matricule parent photo' }),
    lien('/admin/inscriptions', 'Inscriptions', 'inscription', { mots: 'inscrire nouveau' }),
    { titre: 'Organisation' },
    lien('/admin/classes', 'Classes', 'classe', { mots: 'niveau effectif' }),
    lien('/admin/annees', 'Années scolaires', 'calendrier', { mots: 'annee activer cloturer' }),
    lien('/admin/matieres', 'Matières', 'livre', { mots: 'coefficient' }),
    lien('/admin/enseignants', 'Enseignants', 'enseignant', { mots: 'professeur valider demande' }),
    lien('/admin/affectations', 'Affectations', 'lien', { mots: 'enseignant matiere classe' }),
    { titre: 'Notes et bulletins' },
    lien('/admin/notes', 'Saisie des notes', 'crayon', { mots: 'trimestre evaluation' }),
    lien('/admin/releves', 'Relevés de classe', 'tableau', { mots: 'moyenne resultat' }),
    lien('/admin/impressions', 'Impressions', 'imprimante', { mots: 'bulletin certificat carte pdf' }),
  ],
  finances: [
    lien('/admin/finances', 'Bilan', 'graphique', { end: true, mots: 'solde rapport' }),
    { titre: 'Élèves' },
    lien('/admin/finances/encaissements', 'Encaissements', 'argent', { mots: 'payer ecolage droit paiement caisse' }),
    lien('/admin/finances/paiements', 'Paiements et reçus', 'recu', { mots: 'recu annuler historique' }),
    lien('/admin/finances/tarifs', 'Tarifs', 'etiquette', { mots: 'prix ecolage droit' }),
    { titre: 'Mouvements' },
    lien('/admin/finances/depenses', 'Dépenses', 'montee', { mots: 'sortie achat imprevu' }),
    lien('/admin/finances/entrees', "Entrées d'argent", 'descente', { mots: 'recette don' }),
    { titre: 'Personnel' },
    lien('/admin/finances/employes', 'Employés', 'enseignant', { mots: 'personnel salarie' }),
    lien('/admin/finances/salaires', 'Salaires', 'portefeuille', { mots: 'paie avance' }),
  ],
  outils: [
    { titre: 'Données' },
    lien('/admin/donnees', 'Import / Export Excel', 'tableur', { mots: 'excel xlsx importer exporter' }),
    { titre: 'Administration' },
    lien('/admin/journal', "Journal d'activité", 'journal', { mots: 'historique audit' }),
    lien('/admin/parametres', 'Établissement', 'reglages', { mots: 'ecole nom logo adresse parametres' }),
  ],
  enseignant: [
    lien('/enseignant', 'Accueil', 'accueil', { end: true }),
    lien('/enseignant/classes', 'Mes classes', 'classe'),
    lien('/enseignant/notes', 'Saisie des notes', 'crayon'),
    lien('/enseignant/resultats', 'Résultats', 'graphique'),
  ],
};

const CHEMINS_OUTILS = ['/admin/donnees', '/admin/journal', '/admin/parametres'];

// Dans quel espace se trouve-t-on ? (détermine le menu et la couleur de l'interface)
export const espaceDeChemin = (chemin, admin) => {
  if (!admin) return 'enseignant';
  if (chemin === '/admin' || chemin === '/admin/') return 'accueil';
  if (chemin.startsWith('/admin/finances')) return 'finances';
  if (CHEMINS_OUTILS.some((c) => chemin.startsWith(c))) return 'outils';
  return 'scolarite';
};

export const libelleEspace = (cle) => {
  if (cle === 'accueil') return 'Accueil';
  if (cle === 'enseignant') return 'Espace enseignant';
  return (ESPACES.find((e) => e.cle === cle) || {}).label || '';
};

// Toutes les pages atteignables (palette de recherche)
export const pagesRecherchables = (admin) => {
  const cles = admin ? ['scolarite', 'finances', 'outils'] : ['enseignant'];
  const pages = [];
  if (admin) pages.push({ to: '/admin', label: 'Accueil', icone: 'accueil', espace: 'Accueil', mots: 'espaces' });
  cles.forEach((cle) => {
    MENUS[cle].filter((i) => i.to).forEach((i) => pages.push({ ...i, espace: libelleEspace(cle) }));
  });
  return pages;
};

// Pages sans entrée de menu : on indique leur parent pour le fil d'Ariane
const SPECIAUX = [
  { prefixe: '/admin/finances/eleves/', parent: '/admin/finances/encaissements', label: "Situation de l'élève" },
  { prefixe: '/admin/finances/categories', parent: '/admin/finances/depenses', label: 'Catégories' },
  { prefixe: '/admin/bulletins', parent: '/admin/impressions', label: 'Bulletins' },
];

export const filAriane = (chemin, cle) => {
  if (cle === 'accueil') return [{ label: 'Accueil' }];
  const items = (MENUS[cle] || []).filter((i) => i.to);
  const fil = [];
  const racine = cle === 'enseignant'
    ? { label: 'Espace enseignant', to: '/enseignant' }
    : (() => { const e = ESPACES.find((x) => x.cle === cle); return e ? { label: e.label, to: e.to } : null; })();
  if (racine && cle !== 'enseignant') fil.push(racine);

  const special = SPECIAUX.find((s) => chemin.startsWith(s.prefixe));
  if (special) {
    const parent = items.find((i) => i.to === special.parent);
    if (parent) fil.push({ label: parent.label, to: parent.to });
    fil.push({ label: special.label });
    return fil;
  }
  const meilleur = items
    .filter((i) => chemin === i.to || chemin.startsWith(`${i.to}/`))
    .sort((a, b) => b.to.length - a.to.length)[0];
  if (meilleur) {
    const reste = chemin.slice(meilleur.to.length);
    if (reste) {
      fil.push({ label: meilleur.label, to: meilleur.to });
      fil.push({ label: reste.endsWith('/config') ? 'Configuration' : 'Détail' });
    } else {
      fil.push({ label: meilleur.label });
    }
  }
  return fil;
};

// Dernières pages visitées (affichées sur l'accueil)
const CLE_RECENTES = 'pages_recentes';
export const lirePagesRecentes = () => {
  try {
    const v = JSON.parse(localStorage.getItem(CLE_RECENTES) || '[]');
    return Array.isArray(v) ? v.filter((p) => p && p.to && p.label).slice(0, 4) : [];
  } catch (e) { return []; }
};
export const noterPageRecente = (page) => {
  try {
    const autres = lirePagesRecentes().filter((p) => p.to !== page.to);
    localStorage.setItem(CLE_RECENTES, JSON.stringify([page, ...autres].slice(0, 4)));
  } catch (e) { /* stockage indisponible : on ne mémorise pas */ }
};

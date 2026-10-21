import React from 'react';

// Petites icônes à traits (24×24), toutes dessinées pour cette application.
const FORMES = {
  accueil: <><path d="M3 11l9-8 9 8" /><path d="M5 10v10h14V10" /><path d="M10 20v-6h4v6" /></>,
  calendrier: <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M3 10h18M8 3v4M16 3v4" /></>,
  classe: <><path d="M3 21h18" /><path d="M5 21V9l7-5 7 5v12" /><path d="M9 21v-5h6v5" /><path d="M12 10v.01" /></>,
  livre: <><path d="M4 5a2 2 0 0 1 2-2h13v15H6a2 2 0 0 0-2 2V5z" /><path d="M4 20a2 2 0 0 1 2-2h13" /></>,
  eleve: <><path d="M2 9l10-5 10 5-10 5-10-5z" /><path d="M6 11.5V16c0 1.5 3 3 6 3s6-1.5 6-3v-4.5" /></>,
  enseignant: <><circle cx="12" cy="8" r="4" /><path d="M4 21c0-4 4-6 8-6s8 2 8 6" /></>,
  inscription: <><rect x="5" y="4" width="14" height="17" rx="2" /><path d="M9 4h6v3H9zM9 12h6M9 16h4" /></>,
  lien: <><path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1" /><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1" /></>,
  crayon: <><path d="M4 20l4-1 11-11-3-3L5 16l-1 4z" /><path d="M14 6l3 3" /></>,
  graphique: <><path d="M4 20V10M10 20V4M16 20v-8M22 20H2" /></>,
  reglages: <><path d="M4 6h9M19 6h1M4 12h3M13 12h7M4 18h11M21 18h-1" /><circle cx="16" cy="6" r="2" /><circle cx="10" cy="12" r="2" /><circle cx="18" cy="18" r="2" /></>,
  sortie: <><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><path d="M16 17l5-5-5-5M21 12H9" /></>,
  recherche: <><circle cx="11" cy="11" r="7" /><path d="M21 21l-4.3-4.3" /></>,
  plus: <><path d="M12 5v14M5 12h14" /></>,
  corbeille: <><path d="M4 7h16M10 11v6M14 11v6" /><path d="M6 7l1 13h10l1-13" /><path d="M9 7V4h6v3" /></>,
  imprimante: <><path d="M6 9V3h12v6" /><path d="M6 18H4a1 1 0 0 1-1-1v-6a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v6a1 1 0 0 1-1 1h-2" /><path d="M6 14h12v7H6z" /></>,
  valider: <><path d="M5 12l5 5L20 7" /></>,
  gauche: <><path d="M19 12H5M11 6l-6 6 6 6" /></>,
  droite: <><path d="M5 12h14M13 6l6 6-6 6" /></>,
  televerser: <><path d="M12 16V4M7 9l5-5 5 5M4 20h16" /></>,
  telecharger: <><path d="M12 4v12M7 11l5 5 5-5M4 20h16" /></>,
  trombone: <><path d="M21 11l-9 9a5 5 0 0 1-7-7l9-9a3.5 3.5 0 0 1 5 5l-9 9a2 2 0 0 1-3-3l8-8" /></>,
  journal: <><path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6l8-3z" /><path d="M9 12l2 2 4-4" /></>,
  appareil: <><path d="M4 8h3l2-3h6l2 3h3a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1z" /><circle cx="12" cy="13" r="4" /></>,
  wifi: <><path d="M2 9a15 15 0 0 1 20 0M5 12.5a10 10 0 0 1 14 0M8.5 16a5 5 0 0 1 7 0M12 20h.01" /></>,
  menu: <><path d="M4 6h16M4 12h16M4 18h16" /></>,
  fermer: <><path d="M6 6l12 12M18 6L6 18" /></>,
  fichier: <><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5z" /><path d="M14 3v5h5" /></>,
  oeil: <><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z" /><circle cx="12" cy="12" r="3" /></>,
  cadenas: <><rect x="5" y="11" width="14" height="10" rx="2" /><path d="M8 11V8a4 4 0 0 1 8 0v3" /></>,
  actualiser: <><path d="M20 11a8 8 0 0 0-14-4M4 5v4h4M4 13a8 8 0 0 0 14 4M20 19v-4h-4" /></>,
  lecture: <><path d="M7 4l13 8-13 8V4z" /></>,
  alerte: <><path d="M12 3l10 18H2L12 3z" /><path d="M12 10v5M12 18v.01" /></>,
  tableau: <><rect x="3" y="4" width="18" height="16" rx="2" /><path d="M3 10h18M3 15h18M9 4v16" /></>,
  crayonEdit: <><path d="M4 20h4L19 9l-4-4L4 16v4z" /></>,
  soleil: <><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></>,
  lune: <><path d="M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5z" /></>,
  chevron: <><path d="M9 6l6 6-6 6" /></>,
  carte: <><rect x="3" y="5" width="18" height="14" rx="2" /><circle cx="9" cy="11" r="2" /><path d="M6 16c.6-1.6 1.8-2.4 3-2.4s2.4.8 3 2.4M15 10h3M15 14h3" /></>,
  certificat: <><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5z" /><path d="M14 3v5h5M9 13h6M9 17h4" /></>,
  appel: <><rect x="4" y="4" width="16" height="17" rx="2" /><path d="M8 9l1.5 1.5L12 8M14 9.5h3M8 15l1.5 1.5L12 14M14 15.5h3" /></>,
  tableur: <><rect x="3" y="3" width="18" height="18" rx="2" /><path d="M3 9h18M3 15h18M9 3v18M15 3v18" /></>,
  argent: <><circle cx="12" cy="12" r="9" /><path d="M14.8 9.2c-.5-.9-1.5-1.4-2.8-1.4-1.6 0-2.7.8-2.7 2 0 3 5.6 1.4 5.6 4.2 0 1.2-1.2 2-2.9 2-1.4 0-2.5-.6-3-1.6M12 6v1.8M12 16.2V18" /></>,
  recu: <><path d="M6 3h12v18l-3-2-3 2-3-2-3 2V3z" /><path d="M9 8h6M9 12h6" /></>,
  etiquette: <><path d="M3 12V4h8l10 10-8 8L3 12z" /><circle cx="7.5" cy="8.5" r="1.3" /></>,
  montee: <><path d="M7 17L17 7M9 7h8v8" /></>,
  descente: <><path d="M17 7L7 17M15 17H7V9" /></>,
  portefeuille: <><path d="M3 7a2 2 0 0 1 2-2h13v4" /><rect x="3" y="7" width="18" height="13" rx="2" /><path d="M16 13.5h2.5" /></>,
  agrandir: <><path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" /></>,
  reduire: <><path d="M9 4v5H4M15 4v5h5M9 20v-5H4M15 20v-5h5" /></>,
  bas: <><path d="M6 9l6 6 6-6" /></>,
  panneau: <><rect x="3" y="4" width="18" height="16" rx="2" /><path d="M9 4v16" /></>,
  etincelle: <><path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3z" /><path d="M19 17v4M17 19h4" /></>,
  horloge: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
};

const Icon = ({ nom, taille = 18, className = '', titre }) => (
  <svg
    className={`icone ${className}`.trim()}
    width={taille}
    height={taille}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.9"
    strokeLinecap="round"
    strokeLinejoin="round"
    role={titre ? 'img' : undefined}
    aria-label={titre}
    aria-hidden={titre ? undefined : 'true'}
    focusable="false"
  >
    {FORMES[nom] || null}
  </svg>
);

export default Icon;

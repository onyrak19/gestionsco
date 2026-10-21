import { useCallback, useRef, useState } from 'react';

// État du menu de gauche : « etendu » (texte + icônes), « reduit » (icônes seules) ou « masque » (caché).
// Le choix est mémorisé sur l'appareil.
const CLE = 'menu_mode';
const MODES = ['etendu', 'reduit', 'masque'];

const lire = () => {
  try {
    const v = localStorage.getItem(CLE);
    return MODES.includes(v) ? v : 'etendu';
  } catch (e) { return 'etendu'; }
};

const useMenu = () => {
  const [mode, setModeBrut] = useState(lire);
  const dernierVisible = useRef(mode === 'masque' ? 'etendu' : mode);

  const changer = useCallback((m) => {
    if (m !== 'masque') dernierVisible.current = m;
    setModeBrut(m);
    try { localStorage.setItem(CLE, m); } catch (e) { /* le choix vaut pour cette session */ }
  }, []);

  // Bouton « panneau » de la barre du haut : cacher / montrer le menu
  const basculerMasque = useCallback(() => changer(mode === 'masque' ? dernierVisible.current : 'masque'), [mode, changer]);
  // Bouton du bas du menu : étendu <-> icônes seules
  const basculerReduit = useCallback(() => changer(mode === 'reduit' ? 'etendu' : 'reduit'), [mode, changer]);

  return { mode, basculerMasque, basculerReduit };
};

export default useMenu;

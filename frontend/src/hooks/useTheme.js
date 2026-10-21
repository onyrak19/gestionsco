import { useCallback, useState } from 'react';

const lire = () => document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark';

// Thème clair / sombre : le choix est mémorisé sur l'appareil (le thème initial est posé par index.html)
const useTheme = () => {
  const [theme, setTheme] = useState(lire);
  const basculer = useCallback(() => {
    const suivant = lire() === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', suivant);
    try { localStorage.setItem('theme', suivant); } catch (e) { /* stockage indisponible : le choix vaut pour cette session */ }
    setTheme(suivant);
  }, []);
  return [theme, basculer];
};

export default useTheme;

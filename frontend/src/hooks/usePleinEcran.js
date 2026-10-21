import { useCallback, useEffect, useState } from 'react';

// Plein écran de l'application (API Fullscreen du navigateur).
// `possible` vaut false sur les navigateurs qui ne l'offrent pas (iPhone, par exemple) : le bouton est alors masqué.
const usePleinEcran = () => {
  const possible = typeof document !== 'undefined' && !!document.fullscreenEnabled;
  const [actif, setActif] = useState(() => typeof document !== 'undefined' && !!document.fullscreenElement);

  useEffect(() => {
    const suivre = () => setActif(!!document.fullscreenElement);
    document.addEventListener('fullscreenchange', suivre);
    return () => document.removeEventListener('fullscreenchange', suivre);
  }, []);

  const basculer = useCallback(() => {
    if (document.fullscreenElement) {
      if (document.exitFullscreen) document.exitFullscreen();
    } else if (document.documentElement.requestFullscreen) {
      document.documentElement.requestFullscreen().catch(() => { /* refusé par le navigateur : rien à faire */ });
    }
  }, []);

  return [actif, basculer, possible];
};

export default usePleinEcran;

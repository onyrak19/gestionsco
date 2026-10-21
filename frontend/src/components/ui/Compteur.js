import React, { useEffect, useState } from 'react';

const sansAnimation = () => typeof window !== 'undefined' && window.matchMedia
  && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// Nombre qui monte jusqu'à sa valeur (sauf si l'utilisateur a demandé moins d'animations)
const Compteur = ({ valeur, duree = 700 }) => {
  const cible = Number(valeur) || 0;
  const [affiche, setAffiche] = useState(cible);

  useEffect(() => {
    if (cible === 0 || sansAnimation() || typeof requestAnimationFrame === 'undefined') { setAffiche(cible); return undefined; }
    let image;
    let debut;
    const etape = (t) => {
      if (debut === undefined) debut = t;
      const p = Math.min(1, (t - debut) / duree);
      setAffiche(Math.round(cible * (1 - Math.pow(1 - p, 3))));
      if (p < 1) image = requestAnimationFrame(etape);
    };
    setAffiche(0);
    image = requestAnimationFrame(etape);
    return () => cancelAnimationFrame(image);
  }, [cible, duree]);

  return <>{affiche}</>;
};

export default Compteur;

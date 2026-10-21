import React, { useEffect, useRef, useState } from 'react';
import api from '../../api/axios';

// Les photos ne sont jamais publiques : on les demande avec le jeton de connexion
// puis on les affiche. Chargement différé (seulement quand l'image devient visible).
const cache = new Map();   // « idÉlève:jeton » -> adresse locale de l'image

const AuthImage = ({ eleveId, jeton, alt = '', className = '', children }) => {
  const [src, setSrc] = useState(null);
  const ancre = useRef(null);

  useEffect(() => {
    if (!jeton) { setSrc(null); return undefined; }
    const cle = `${eleveId}:${jeton}`;
    if (cache.has(cle)) { setSrc(cache.get(cle)); return undefined; }

    let annule = false;
    const charger = () => api.get(`/school/eleves/${eleveId}/photo/`, { responseType: 'blob' })
      .then((res) => {
        const url = URL.createObjectURL(res.data);
        cache.set(cle, url);
        if (!annule) setSrc(url);
      })
      .catch(() => { /* pas de photo affichable : on garde les initiales */ });

    if (typeof IntersectionObserver === 'undefined' || !ancre.current) {
      charger();
      return () => { annule = true; };
    }
    const observateur = new IntersectionObserver((entrees) => {
      if (entrees.some((e) => e.isIntersecting)) { observateur.disconnect(); charger(); }
    }, { rootMargin: '150px' });
    observateur.observe(ancre.current);
    return () => { annule = true; observateur.disconnect(); };
  }, [eleveId, jeton]);

  if (src) return <img className={className} src={src} alt={alt} />;
  return <span ref={ancre} className={className}>{children}</span>;
};

export default AuthImage;

import React, { useEffect, useRef } from 'react';

// Fenêtre modale : se ferme avec Échap ou un clic à côté, bloque le défilement de la page derrière
// et place le focus à l'intérieur pour le clavier.
const Modal = ({ titre, onClose, children }) => {
  const boite = useRef(null);
  const fermer = useRef(onClose);   // les parents passent une nouvelle fonction à chaque rendu : on ne relance pas l'effet pour autant
  fermer.current = onClose;

  useEffect(() => {
    const precedent = document.activeElement;
    const surTouche = (e) => { if (e.key === 'Escape') fermer.current(); };
    document.addEventListener('keydown', surTouche);
    const debordement = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    if (boite.current && !boite.current.contains(document.activeElement)) boite.current.focus();
    return () => {
      document.removeEventListener('keydown', surTouche);
      document.body.style.overflow = debordement;
      if (precedent && precedent.focus) precedent.focus();
    };
  }, []);

  return (
    <div className="modal-fond" onClick={onClose} role="presentation">
      <div className="modal" role="dialog" aria-modal="true" aria-label={titre} tabIndex={-1} ref={boite} onClick={(e) => e.stopPropagation()}>
        <div className="modal-entete">
          <h3>{titre}</h3>
          <button type="button" className="modal-fermer" onClick={onClose} aria-label="Fermer">✕</button>
        </div>
        {children}
      </div>
    </div>
  );
};

export default Modal;

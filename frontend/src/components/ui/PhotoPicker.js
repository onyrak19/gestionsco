import React, { useEffect, useRef, useState } from 'react';
import Icon from './Icon';

const TAILLE_MAX = 8 * 1024 * 1024;

// Choix d'une photo (facultatif) avec aperçu.
// fichier : File choisi ou null ; actuelle : élément affiché quand aucun nouveau fichier n'est choisi.
const PhotoPicker = ({ fichier, onChange, actuelle = null, onRetirer, id = 'photo-eleve' }) => {
  const entree = useRef(null);
  const [apercu, setApercu] = useState('');
  const [erreur, setErreur] = useState('');

  useEffect(() => {
    if (!fichier) { setApercu(''); return undefined; }
    const url = URL.createObjectURL(fichier);
    setApercu(url);
    return () => URL.revokeObjectURL(url);
  }, [fichier]);

  const choisir = (e) => {
    const f = e.target.files && e.target.files[0];
    e.target.value = '';
    if (!f) return;
    if (!/^image\//.test(f.type)) { setErreur('Choisissez une image (JPG, PNG ou WebP).'); return; }
    if (f.size > TAILLE_MAX) { setErreur('La photo dépasse 8 Mo.'); return; }
    setErreur('');
    onChange(f);
  };

  return (
    <div className="photo-picker">
      <div className="photo-cadre">
        {apercu ? <img src={apercu} alt="Aperçu de la photo" /> : (actuelle || <Icon nom="appareil" taille={30} />)}
      </div>
      <div className="photo-actions">
        <input ref={entree} id={id} type="file" accept="image/*" onChange={choisir} hidden />
        <button type="button" className="btn-secondary btn-compact" onClick={() => entree.current.click()}>
          <Icon nom="televerser" taille={15} /> {fichier || actuelle ? 'Changer la photo' : 'Ajouter une photo'}
        </button>
        {(fichier || (actuelle && onRetirer)) && (
          <button type="button" className="btn-small btn-danger"
            onClick={() => { if (fichier) onChange(null); else onRetirer(); }}>
            Retirer
          </button>
        )}
        <small className="muted">Facultatif · JPG, PNG ou WebP · réduite automatiquement</small>
        {erreur && <small className="texte-erreur">{erreur}</small>}
      </div>
    </div>
  );
};

export default PhotoPicker;

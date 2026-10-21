import React, { useRef, useState } from 'react';
import Icon from './Icon';
import {
  EXTENSIONS_ACCEPTEES, NB_MAX_PIECES, TYPES_DOCUMENTS, formatTaille, verifierPiece,
} from '../../utils/fichiers';

// Pièces jointes facultatives : zéro, un ou plusieurs fichiers, chacun avec son type.
// items : [{ cle, fichier, libelle }]
let compteur = 0;

const FilePicker = ({ items, onChange }) => {
  const entree = useRef(null);
  const [erreur, setErreur] = useState('');

  const ajouter = (e) => {
    const choisis = Array.from(e.target.files || []);
    e.target.value = '';
    const refus = [];
    const acceptes = [];
    choisis.forEach((f) => {
      const probleme = verifierPiece(f);
      if (probleme) refus.push(probleme);
      else acceptes.push({ cle: `piece-${++compteur}`, fichier: f, libelle: '' });
    });
    if (items.length + acceptes.length > NB_MAX_PIECES) {
      refus.push(`Maximum ${NB_MAX_PIECES} fichiers à la fois.`);
      acceptes.splice(Math.max(0, NB_MAX_PIECES - items.length));
    }
    setErreur(refus.join(' '));
    if (acceptes.length) onChange([...items, ...acceptes]);
  };

  const maj = (cle, libelle) => onChange(items.map((i) => (i.cle === cle ? { ...i, libelle } : i)));
  const retirer = (cle) => onChange(items.filter((i) => i.cle !== cle));

  return (
    <div className="file-picker">
      <input ref={entree} type="file" multiple accept={EXTENSIONS_ACCEPTEES} onChange={ajouter} hidden
        aria-label="Choisir des pièces jointes" />
      <button type="button" className="btn-secondary btn-compact" onClick={() => entree.current.click()}>
        <Icon nom="trombone" taille={15} /> Ajouter des pièces jointes
      </button>
      <small className="muted">Facultatif · PDF, images, Word, Excel · 10 Mo maximum par fichier</small>
      {erreur && <div className="texte-erreur">{erreur}</div>}
      {items.length > 0 && (
        <ul className="liste-pieces">
          {items.map((i) => (
            <li key={i.cle}>
              <Icon nom="fichier" taille={18} />
              <span className="piece-nom" title={i.fichier.name}>{i.fichier.name}</span>
              <small className="muted">{formatTaille(i.fichier.size)}</small>
              <select value={i.libelle} aria-label={`Type de document pour ${i.fichier.name}`}
                onChange={(e) => maj(i.cle, e.target.value)}>
                <option value="">Type de document…</option>
                {TYPES_DOCUMENTS.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
              <button type="button" className="btn-small btn-danger" onClick={() => retirer(i.cle)}
                aria-label={`Retirer ${i.fichier.name}`}>
                <Icon nom="fermer" taille={14} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

export default FilePicker;

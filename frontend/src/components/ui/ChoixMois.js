import React, { useState } from 'react';
import { libelleMois } from '../../utils/argent';

// Choix de plusieurs mois. `options` : [{ mois: '2026-09', libelle, statut? }].
// `desactives` : mois non sélectionnables (déjà payés...). `libre` : permet d'ajouter un autre mois.
const ChoixMois = ({ options, valeur, onChange, desactives = [], libre = false, etiquette = 'Mois' }) => {
  const [autre, setAutre] = useState('');
  const connus = options.map((o) => o.mois);
  const supplementaires = valeur.filter((m) => !connus.includes(m));
  const tous = [...options, ...supplementaires.map((m) => ({ mois: m, libelle: libelleMois(m) }))];
  const basculer = (m) => onChange(valeur.includes(m) ? valeur.filter((x) => x !== m) : [...valeur, m].sort());
  const ajouter = () => {
    if (autre && !desactives.includes(autre) && !valeur.includes(autre)) onChange([...valeur, autre].sort());
    setAutre('');
  };

  return (
    <div>
      <div className="mois-grille" role="group" aria-label={etiquette}>
        {tous.map((o) => {
          const bloque = desactives.includes(o.mois);
          const coche = valeur.includes(o.mois);
          return (
            <label key={o.mois} className={`mois-puce ${coche ? 'cochee' : ''} ${bloque ? 'desactivee' : ''}`}>
              <input type="checkbox" checked={coche} disabled={bloque} onChange={() => basculer(o.mois)} />
              <span>{o.libelle || libelleMois(o.mois)}</span>
              {bloque && <small>déjà payé</small>}
            </label>
          );
        })}
      </div>
      {libre && (
        <div className="actions-ligne" style={{ marginTop: 8 }}>
          <input type="month" value={autre} onChange={(e) => setAutre(e.target.value)}
            aria-label="Ajouter un autre mois" style={{ width: 'auto' }} />
          <button type="button" className="btn-secondary btn-compact" disabled={!autre} onClick={ajouter}>
            Ajouter ce mois
          </button>
        </div>
      )}
    </div>
  );
};

export default ChoixMois;

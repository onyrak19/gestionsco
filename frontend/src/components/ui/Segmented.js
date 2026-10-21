import React from 'react';

// Choix entre quelques options toujours visibles (trimestre, mode d'affichage...)
const Segmented = ({ options, valeur, onChange, label }) => (
  <div className="segmente" role="group" aria-label={label}>
    {options.map((o) => (
      <button
        key={o.value}
        type="button"
        className={`segment ${String(o.value) === String(valeur) ? 'actif' : ''}`}
        aria-pressed={String(o.value) === String(valeur)}
        onClick={() => onChange(o.value)}
      >
        {o.label}
      </button>
    ))}
  </div>
);

export default Segmented;

import React from 'react';

// Liste déroulante des années scolaires
const SelectAnnee = ({ id = 'sel-annee', annees, valeur, onChange, label = 'Année scolaire' }) => (
  <div className="form-group">
    <label htmlFor={id}>{label}</label>
    <select id={id} value={valeur} onChange={(e) => onChange(e.target.value)}>
      {annees.map((a) => <option key={a.id} value={a.id}>{a.libelle}{a.active ? ' (en cours)' : ''}</option>)}
    </select>
  </div>
);

export default SelectAnnee;

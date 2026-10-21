import React, { useEffect, useState } from 'react';
import api from '../../api/axios';
import { formatApiError } from '../../utils/errors';
import ReleveClasse from './ReleveClasse';

const Releves = () => {
  const [annees, setAnnees] = useState([]);
  const [classes, setClasses] = useState([]);
  const [annee, setAnnee] = useState('');
  const [classe, setClasse] = useState('');
  const [erreur, setErreur] = useState('');

  useEffect(() => {
    api.get('/school/annees/').then(r => {
      setAnnees(r.data);
      const active = r.data.find(a => a.active) || r.data[0];
      if (active) setAnnee(active.id);
    }).catch(err => setErreur(formatApiError(err)));
  }, []);

  useEffect(() => {
    if (!annee) return;
    setClasse('');
    api.get('/school/classes/', { params: { annee } }).then(r => setClasses(r.data))
      .catch(err => setErreur(formatApiError(err)));
  }, [annee]);

  return (
    <div className="page">
      <h1>Relevés de classe</h1>
      <p className="page-subtitle">Consultez les notes, moyennes et rangs de n'importe quelle classe.</p>
      {erreur && <div className="error">{erreur}</div>}
      <div className="card">
        <div className="form-row">
          <div className="form-group"><label htmlFor="releve-annee">Année scolaire</label>
            <select id="releve-annee" value={annee} onChange={(e) => setAnnee(e.target.value)}>
              {annees.map(a => <option key={a.id} value={a.id}>{a.libelle}{a.active ? ' (en cours)' : ''}</option>)}
            </select></div>
          <div className="form-group"><label htmlFor="releve-classe">Classe</label>
            <select id="releve-classe" value={classe} onChange={(e) => setClasse(e.target.value)}>
              <option value="">-- Choisir une classe --</option>
              {classes.map(c => <option key={c.id} value={c.id}>{c.nom}</option>)}
            </select></div>
        </div>
      </div>
      {classe && <ReleveClasse classeId={classe} />}
    </div>
  );
};

export default Releves;

import React, { useEffect, useState } from 'react';
import api from '../../api/axios';
import { formatApiError } from '../../utils/errors';

const MesClasses = () => {
  const [affectations, setAffectations] = useState([]);
  const [selected, setSelected] = useState(null);
  const [eleves, setEleves] = useState([]);
  const [erreur, setErreur] = useState('');

  useEffect(() => {
    api.get('/school/affectations/mes/').then(r => setAffectations(r.data))
      .catch(err => setErreur(formatApiError(err)));
  }, []);

  useEffect(() => {
    if (!selected) return;
    api.get('/school/inscriptions/', { params: { classe: selected.classe } })
      .then(r => setEleves(r.data))
      .catch(err => setErreur(formatApiError(err)));
  }, [selected]);

  return (
    <div className="page">
      <h1>Mes classes</h1>
      {erreur && <div className="error">{erreur}</div>}

      <div className="card">
        <h3>Choisir une affectation</h3>
        {affectations.length === 0 && <p>Aucune affectation pour l'année en cours.</p>}
        <div className="checkbox-group">
          {affectations.map(a => (
            <button key={a.id}
              className={selected?.id === a.id ? 'btn-primary' : 'btn-secondary'}
              onClick={() => setSelected(a)}>
              {a.classe_nom} — {a.matiere_nom}
            </button>
          ))}
        </div>
      </div>

      {selected && (
        <div className="card">
          <h3>Élèves de {selected.classe_nom} ({eleves.length})</h3>
          <table className="data-table">
            <thead><tr><th>Matricule</th><th>Nom</th><th>Prénom</th></tr></thead>
            <tbody>
              {eleves.map(e => (
                <tr key={e.id}>
                  <td>{e.eleve_details?.matricule}</td>
                  <td>{e.eleve_details?.nom}</td>
                  <td>{e.eleve_details?.prenom}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default MesClasses;

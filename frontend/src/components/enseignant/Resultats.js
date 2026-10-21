import React, { useEffect, useState } from 'react';
import api from '../../api/axios';
import { formatApiError } from '../../utils/errors';
import { formatNote } from '../../utils/notes';

const Resultats = () => {
  const [affectations, setAffectations] = useState([]);
  const [selected, setSelected] = useState(null);
  const [trimestre, setTrimestre] = useState(1);
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [erreur, setErreur] = useState('');

  useEffect(() => {
    api.get('/school/affectations/mes/').then(r => {
      setAffectations(r.data);
      if (r.data.length > 0) setSelected(r.data[0]);
    }).catch(err => setErreur(formatApiError(err)));
  }, []);

  useEffect(() => {
    if (!selected) return;
    setLoading(true);
    setErreur('');
    api.get('/school/notes/', {
      params: { classe: selected.classe, matiere: selected.matiere, trimestre }
    }).then(r => {
      // Classement décroissant ; les élèves sans moyenne passent en dernier
      const sorted = [...r.data].sort((a, b) =>
        (b.moyenne_matiere ?? -1) - (a.moyenne_matiere ?? -1)
      );
      setData(sorted);
    }).catch(err => setErreur(formatApiError(err))).finally(() => setLoading(false));
  }, [selected, trimestre]);

  return (
    <div className="page">
      <h1>Résultats</h1>
      {erreur && <div className="error">{erreur}</div>}

      {affectations.length === 0 ? (
        <div className="card"><p>Aucune affectation.</p></div>
      ) : (
        <>
          <div className="card">
            <div className="form-row">
              <div className="form-group">
                <label>Classe / Matière</label>
                <select value={selected ? `${selected.classe}|${selected.matiere}` : ''}
                  onChange={(e) => {
                    const [classe, matiere] = e.target.value.split('|').map(Number);
                    setSelected(affectations.find(a => a.classe === classe && a.matiere === matiere));
                  }}>
                  {affectations.map(a => (
                    <option key={`${a.classe}|${a.matiere}`} value={`${a.classe}|${a.matiere}`}>
                      {a.classe_nom} — {a.matiere_nom}
                    </option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label>Trimestre</label>
                <select value={trimestre} onChange={(e) => setTrimestre(Number(e.target.value))}>
                  <option value={1}>1er trimestre</option>
                  <option value={2}>2e trimestre</option>
                  <option value={3}>3e trimestre</option>
                </select>
              </div>
            </div>
          </div>

          <div className="card">
            <h3>Classement ({data.length} élèves)</h3>
            {loading ? <p>Chargement...</p> : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Rang</th><th>Élève</th>
                    <th>Moy. journ.</th><th>Examen</th><th>Moy. matière</th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((n, i) => {
                    // Ex-aequo : même rang ; sans moyenne : pas de rang
                    const rang = n.moyenne_matiere == null
                      ? '-'
                      : `#${data.findIndex(x => x.moyenne_matiere === n.moyenne_matiere) + 1}`;
                    return (
                    <tr key={n.id}>
                      <td>{rang}</td>
                      <td>{n.eleve_nom} {n.eleve_prenom}</td>
                      <td>{formatNote(n.moyenne_journaliere)}</td>
                      <td>{formatNote(n.examen)}</td>
                      <td><strong>{formatNote(n.moyenne_matiere)}</strong></td>
                    </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}
    </div>
  );
};

export default Resultats;
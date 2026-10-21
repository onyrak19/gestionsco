import React, { useEffect, useState } from 'react';
import api from '../../api/axios';
import { formatApiError } from '../../utils/errors';
import { classeNote } from '../../utils/labels';
import { formatNote } from '../../utils/notes';
import DecisionBadge from '../ui/DecisionBadge';

// Relevé de notes d'une classe : tous les élèves × toutes les matières
const ReleveClasse = ({ classeId }) => {
  const [trimestre, setTrimestre] = useState('1');
  const [ordre, setOrdre] = useState('alpha');
  const [data, setData] = useState(null);
  const [erreur, setErreur] = useState('');

  useEffect(() => {
    if (!classeId) { setData(null); return; }
    setErreur('');
    api.get(`/school/classes/${classeId}/releve/`, { params: { trimestre, ordre } })
      .then(r => setData(r.data))
      .catch(err => { setData(null); setErreur(formatApiError(err)); });
  }, [classeId, trimestre, ordre]);

  return (
    <div className="card">
      <div className="card-titre">
        <h3>Relevé de notes {data && `— ${data.classe.nom}`}</h3>
        <div className="actions-ligne">
          <select value={trimestre} onChange={(e) => setTrimestre(e.target.value)} aria-label="Période" style={{ width: 'auto' }}>
            <option value="1">1er trimestre</option>
            <option value="2">2e trimestre</option>
            <option value="3">3e trimestre</option>
            <option value="annuel">Moyenne annuelle</option>
          </select>
          <select value={ordre} onChange={(e) => setOrdre(e.target.value)} aria-label="Ordre" style={{ width: 'auto' }}>
            <option value="alpha">Ordre alphabétique</option>
            <option value="numero">Par numéro</option>
            <option value="rang">Par rang (mérite)</option>
          </select>
        </div>
      </div>
      {erreur && <div className="error">{erreur}</div>}
      {data && (
        <>
          {data.matieres.length === 0 && (
            <p className="muted">Aucune note saisie pour cette classe. La saisie se fait dans « Saisie des notes ».</p>
          )}
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th className="centre">N°</th><th>Élève</th>
                  {data.matieres.map(m => (
                    <th key={m.id} className="centre" title={`${m.nom} — coefficient ${m.coefficient}`}>
                      <span className="col-matiere-nom" title={m.nom}>{m.nom}</span><br /><small>coef {m.coefficient}</small>
                    </th>
                  ))}
                  <th className="centre">Moyenne</th><th className="centre">Rang</th>
                  {trimestre === 'annuel' && <th>Décision</th>}
                </tr>
              </thead>
              <tbody>
                {data.eleves.map(e => (
                  <tr key={e.inscription}>
                    <td className="centre">{e.numero}</td>
                    <td>{e.nom} {e.prenom}</td>
                    {data.matieres.map(m => (
                      <td key={m.id} className={`centre ${classeNote(e.notes[m.id])}`}>{formatNote(e.notes[m.id])}</td>
                    ))}
                    <td className={`centre ${classeNote(e.generale)}`}><strong>{formatNote(e.generale)}</strong></td>
                    <td className="centre">{e.rang ?? '-'}</td>
                    {trimestre === 'annuel' && <td><DecisionBadge decision={e.decision} /></td>}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted">
            Moyenne de la classe : <strong>{formatNote(data.stats.moyenne)}</strong> · plus forte : {formatNote(data.stats.max)} · plus faible : {formatNote(data.stats.min)}
          </p>
        </>
      )}
    </div>
  );
};

export default ReleveClasse;

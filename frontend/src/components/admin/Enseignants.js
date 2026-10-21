import React, { useCallback, useEffect, useState } from 'react';
import api from '../../api/axios';
import { formatApiError } from '../../utils/errors';

const Enseignants = () => {
  const [statut, setStatut] = useState('en_attente');
  const [items, setItems] = useState([]);
  const [error, setError] = useState('');

  const load = useCallback(
    () => api.get('/auth/enseignants/', { params: { statut } }).then(r => setItems(r.data))
      .catch(err => setError(formatApiError(err))),
    [statut]
  );
  useEffect(() => { load(); }, [load]);

  const changeStatut = async (id, newStatut) => {
    setError('');
    try {
      await api.patch(`/auth/enseignants/${id}/`, { statut: newStatut });
    } catch (err) { setError(formatApiError(err)); }
    load();
  };

  return (
    <div className="page">
      <h1>Enseignants</h1>
      {error && <div className="error">{error}</div>}
      <div className="card">
        <div className="form-group">
          <label>Filtrer par statut</label>
          <select value={statut} onChange={(e) => setStatut(e.target.value)}>
            <option value="en_attente">En attente</option>
            <option value="valide">Validés</option>
            <option value="refuse">Refusés</option>
            <option value="desactive">Désactivés</option>
          </select>
        </div>
      </div>
      <div className="card">
        <h3>{items.length} enseignant(s)</h3>
        <table className="data-table">
          <thead><tr><th>Nom</th><th>Username</th><th>Email</th><th>Statut</th><th>Actions</th></tr></thead>
          <tbody>
            {items.map(u => (
              <tr key={u.id}>
                <td>{u.nom} {u.prenom}</td>
                <td>{u.username}</td>
                <td>{u.email}</td>
                <td><span className="badge">{u.profile?.statut}</span></td>
                <td>
                  {statut === 'en_attente' && (
                    <>
                      <button className="btn-small" onClick={() => changeStatut(u.id, 'valide')}>✓ Valider</button>
                      <button className="btn-small btn-danger" onClick={() => changeStatut(u.id, 'refuse')}>Refuser</button>
                    </>
                  )}
                  {statut === 'valide' && (
                    <button className="btn-small btn-danger" onClick={() => changeStatut(u.id, 'desactive')}>Désactiver</button>
                  )}
                  {statut === 'desactive' && (
                    <button className="btn-small" onClick={() => changeStatut(u.id, 'valide')}>Réactiver</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default Enseignants;
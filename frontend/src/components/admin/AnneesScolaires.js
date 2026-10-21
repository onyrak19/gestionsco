import React, { useCallback, useEffect, useState } from 'react';
import api from '../../api/axios';
import { formatApiError } from '../../utils/errors';
import Modal from '../ui/Modal';

const AnneesScolaires = () => {
  const [items, setItems] = useState([]);
  const [form, setForm] = useState({ libelle: '', date_debut: '', date_fin: '' });
  const [error, setError] = useState('');
  const [cible, setCible] = useState(null);        // année en cours de clôture
  const [motDePasse, setMotDePasse] = useState('');
  const [erreurModal, setErreurModal] = useState('');
  const [resume, setResume] = useState(null);
  const [enCours, setEnCours] = useState(false);

  const load = useCallback(
    () => api.get('/school/annees/').then(r => setItems(r.data))
      .catch(err => setError(formatApiError(err))),
    []
  );
  useEffect(() => { load(); }, [load]);

  const executer = async (action) => {
    setError('');
    try { await action(); } catch (err) { setError(formatApiError(err)); }
    load();
  };

  const create = async (e) => {
    e.preventDefault();
    setError('');
    try {
      await api.post('/school/annees/', form);
      setForm({ libelle: '', date_debut: '', date_fin: '' });
      load();
    } catch (err) { setError(formatApiError(err)); }
  };

  const activer = (id) => executer(() => api.patch(`/school/annees/${id}/`, { active: true }));

  const supprimer = (id) => {
    if (!window.confirm('Supprimer cette année et TOUTES ses données (classes, inscriptions, affectations, notes) ? Cette action est irréversible.')) return;
    return executer(() => api.delete(`/school/annees/${id}/`));
  };

  const ouvrirCloture = (annee) => {
    setCible(annee); setMotDePasse(''); setErreurModal(''); setResume(null);
  };

  const confirmerCloture = async (e) => {
    e.preventDefault();
    setEnCours(true);
    setErreurModal('');
    try {
      const res = await api.post(`/school/annees/${cible.id}/cloturer/`, { password: motDePasse });
      setResume({ annee: cible.libelle, ...res.data.resume });
      setCible(null);
      setMotDePasse('');
      load();
    } catch (err) {
      setErreurModal(formatApiError(err));
    } finally {
      setEnCours(false);
    }
  };

  return (
    <div className="page">
      <h1>Années scolaires</h1>
      <p className="page-subtitle">Une seule année est active à la fois. Les affectations des enseignants sont à redéfinir pour chaque nouvelle année.</p>
      {error && <div className="error">{error}</div>}

      {resume && (
        <div className="success">
          <strong>Année {resume.annee} clôturée.</strong> Décisions calculées automatiquement :{' '}
          <span className="badge badge-passant">{resume.passant} passant(s)</span>{' '}
          <span className="badge badge-redoublant">{resume.redoublant} redoublant(s)</span>
          {resume.non_decide > 0 && (
            <> <span className="badge badge-non_decide">{resume.non_decide} à décider</span>
              {' '}(élèves sans note : indiquez leur décision dans leur dossier)</>
          )}
        </div>
      )}

      <div className="card">
        <h3>Nouvelle année scolaire</h3>
        <form onSubmit={create} className="crud-form">
          <div className="form-row">
            <div className="form-group"><label htmlFor="libelle">Libellé (ex. 2026-2027)</label>
              <input id="libelle" value={form.libelle} required
                onChange={(e) => setForm({ ...form, libelle: e.target.value })} /></div>
            <div className="form-group"><label htmlFor="debut">Début</label>
              <input id="debut" type="date" value={form.date_debut} required
                onChange={(e) => setForm({ ...form, date_debut: e.target.value })} /></div>
            <div className="form-group"><label htmlFor="fin">Fin</label>
              <input id="fin" type="date" value={form.date_fin} required
                onChange={(e) => setForm({ ...form, date_fin: e.target.value })} /></div>
          </div>
          <button className="btn-primary" type="submit">Créer</button>
        </form>
      </div>

      <div className="card">
        <h3>Liste ({items.length})</h3>
        <div className="table-wrap">
          <table className="data-table">
            <thead><tr><th>Libellé</th><th>Période</th><th>État</th><th>Actions</th></tr></thead>
            <tbody>
              {items.map(a => (
                <tr key={a.id}>
                  <td><strong>{a.libelle}</strong></td>
                  <td>{a.date_debut} → {a.date_fin}</td>
                  <td>
                    {a.active && <span className="badge badge-active">Active</span>}
                    {a.cloturee && <span className="badge badge-cloturee">Clôturée</span>}
                    {!a.active && !a.cloturee && <span className="badge">À venir</span>}
                  </td>
                  <td>
                    {!a.active && !a.cloturee && (
                      <button className="btn-small" onClick={() => activer(a.id)}>Activer</button>
                    )}
                    {!a.cloturee && (
                      <button className="btn-small" onClick={() => ouvrirCloture(a)}>Clôturer</button>
                    )}
                    <button className="btn-small btn-danger" onClick={() => supprimer(a.id)}>Supprimer</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {cible && (
        <Modal titre={`Clôturer l'année ${cible.libelle}`} onClose={() => setCible(null)}>
          <form onSubmit={confirmerCloture}>
            <div className="info">
              La clôture calcule la moyenne annuelle de chaque élève et le classe <strong>passant</strong> ou{' '}
              <strong>redoublant</strong>. Les notes, classes, inscriptions et affectations de l'année ne
              pourront plus être modifiées.
            </div>
            {erreurModal && <div className="error">{erreurModal}</div>}
            <div className="form-group">
              <label htmlFor="mdp-cloture">Mot de passe administrateur</label>
              <input id="mdp-cloture" type="password" autoFocus required autoComplete="current-password"
                value={motDePasse} onChange={(e) => setMotDePasse(e.target.value)} />
            </div>
            <div className="actions-ligne">
              <button type="submit" className="btn-primary" disabled={enCours || !motDePasse}>
                {enCours ? 'Clôture…' : 'Confirmer la clôture'}
              </button>
              <button type="button" className="btn-secondary" onClick={() => setCible(null)}>Annuler</button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
};

export default AnneesScolaires;

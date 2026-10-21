import React, { useCallback, useEffect, useState } from 'react';
import api from '../../api/axios';
import { formatApiError } from '../../utils/errors';
import Icon from '../ui/Icon';
import PageHeader from '../ui/PageHeader';
import EmptyState from '../ui/EmptyState';

const Matieres = () => {
  const [items, setItems] = useState([]);
  const [form, setForm] = useState({ nom: '', coefficient: 1 });
  const [edition, setEdition] = useState(null);   // { id, nom, coefficient } de la ligne en cours de modification
  const [error, setError] = useState('');
  const [succes, setSucces] = useState('');

  const load = useCallback(
    () => api.get('/school/matieres/').then((r) => setItems(r.data))
      .catch((err) => setError(formatApiError(err))),
    [],
  );
  useEffect(() => { load(); }, [load]);

  const create = async (e) => {
    e.preventDefault();
    setError(''); setSucces('');
    try {
      await api.post('/school/matieres/', form);
      setForm({ nom: '', coefficient: 1 });
      load();
    } catch (err) { setError(formatApiError(err)); }
  };

  const enregistrer = async (e) => {
    e.preventDefault();
    setError(''); setSucces('');
    try {
      await api.patch(`/school/matieres/${edition.id}/`, { nom: edition.nom, coefficient: edition.coefficient });
      setSucces(`« ${edition.nom} » est à jour : coefficient par défaut ${edition.coefficient}.`);
      setEdition(null);
      load();
    } catch (err) { setError(formatApiError(err)); }
  };

  const supprimer = async (id) => {
    if (!window.confirm('Supprimer cette matière ? Ses affectations, sa configuration et toutes les notes de cette matière seront aussi supprimées.')) return;
    setError(''); setSucces('');
    try { await api.delete(`/school/matieres/${id}/`); } catch (err) { setError(formatApiError(err)); }
    load();
  };

  return (
    <div className="page">
      <PageHeader
        titre="Matières"
        sousTitre="Les coefficients propres à chaque niveau ou série se règlent dans « Classes → Matières »."
      />
      {error && <div className="error">{error}</div>}
      {succes && <div className="success">{succes}</div>}

      <div className="card">
        <h3>Nouvelle matière</h3>
        <form onSubmit={create} className="crud-form">
          <div className="form-row">
            <div className="form-group"><label htmlFor="mat-nom">Nom</label>
              <input id="mat-nom" value={form.nom} required maxLength={100}
                onChange={(e) => setForm({ ...form, nom: e.target.value })} /></div>
            <div className="form-group"><label htmlFor="mat-coef">Coefficient par défaut</label>
              <input id="mat-coef" type="number" min="1" value={form.coefficient}
                onChange={(e) => setForm({ ...form, coefficient: Number(e.target.value) || 1 })} /></div>
          </div>
          <button className="btn-primary" type="submit"><Icon nom="plus" taille={16} /> Ajouter</button>
        </form>
      </div>

      <div className="card">
        <h3>Liste ({items.length})</h3>
        {items.length === 0 ? (
          <EmptyState icone="livre" titre="Aucune matière">Ajoutez Mathématiques, Français, Histoire… avec leur coefficient.</EmptyState>
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead><tr><th>Matière</th><th className="centre">Coefficient par défaut</th><th></th></tr></thead>
              <tbody>
                {items.map((m) => (edition && edition.id === m.id ? (
                  <tr key={m.id} className="ligne-edition">
                    <td colSpan={3}>
                      <form onSubmit={enregistrer} className="edition-ligne">
                        <input aria-label="Nom de la matière" value={edition.nom} required maxLength={100} autoFocus
                          onChange={(e) => setEdition({ ...edition, nom: e.target.value })} />
                        <label className="edition-coef">Coefficient
                          <input aria-label="Coefficient par défaut" type="number" min="1" value={edition.coefficient}
                            onChange={(e) => setEdition({ ...edition, coefficient: Number(e.target.value) || 1 })} />
                        </label>
                        <button type="submit" className="btn-primary btn-compact">Enregistrer</button>
                        <button type="button" className="btn-secondary btn-compact" onClick={() => setEdition(null)}>Annuler</button>
                      </form>
                    </td>
                  </tr>
                ) : (
                  <tr key={m.id}>
                    <td><strong>{m.nom}</strong></td>
                    <td className="centre"><span className="badge badge-coef">{m.coefficient}</span></td>
                    <td className="actions-cell">
                      <button className="btn-small btn-secondary" aria-label={`Modifier ${m.nom}`}
                        onClick={() => setEdition({ id: m.id, nom: m.nom, coefficient: m.coefficient })}>
                        <Icon nom="crayonEdit" taille={14} /> Modifier
                      </button>
                      <button className="btn-small btn-danger" aria-label={`Supprimer ${m.nom}`} onClick={() => supprimer(m.id)}>Supprimer</button>
                    </td>
                  </tr>
                )))}
              </tbody>
            </table>
          </div>
        )}
        <p className="muted">Le coefficient par défaut ne sert que pour les classes dont les matières n'ont pas encore été configurées.</p>
      </div>
    </div>
  );
};

export default Matieres;

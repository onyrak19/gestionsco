import React, { useCallback, useEffect, useState } from 'react';
import api from '../../api/axios';
import { formatApiError } from '../../utils/errors';
import PageHeader from '../ui/PageHeader';
import Icon from '../ui/Icon';

const SENS = [
  { cle: 'depense', titre: 'Catégories de dépenses', exemple: 'Électricité, fournitures, entretien…' },
  { cle: 'entree', titre: 'Catégories d’entrées d’argent', exemple: 'Dons, subventions, location de salle…' },
];

// Catégories des dépenses et des entrées : à configurer selon l'établissement
const Categories = () => {
  const [liste, setListe] = useState([]);
  const [nouvelle, setNouvelle] = useState({ depense: '', entree: '' });
  const [erreur, setErreur] = useState('');

  const charger = useCallback(() => api.get('/finance/categories/')
    .then((r) => setListe(r.data.results || r.data)).catch((err) => setErreur(formatApiError(err))), []);
  useEffect(() => { charger(); }, [charger]);

  const ajouter = async (e, sens) => {
    e.preventDefault();
    setErreur('');
    try {
      await api.post('/finance/categories/', { nom: nouvelle[sens], sens, actif: true });
      setNouvelle({ ...nouvelle, [sens]: '' });
      charger();
    } catch (err) { setErreur(formatApiError(err)); }
  };
  const basculer = async (c) => {
    setErreur('');
    try { await api.patch(`/finance/categories/${c.id}/`, { actif: !c.actif }); charger(); } catch (err) { setErreur(formatApiError(err)); }
  };
  const supprimer = async (c) => {
    if (!window.confirm(`Supprimer la catégorie « ${c.nom} » ?`)) return;
    setErreur('');
    try { await api.delete(`/finance/categories/${c.id}/`); charger(); } catch (err) { setErreur(formatApiError(err)); }
  };

  return (
    <div className="page">
      <PageHeader titre="Catégories"
        sousTitre="Une catégorie utilisée ne peut pas être supprimée : désactivez-la pour ne plus la proposer." />
      {erreur && <div className="error">{erreur}</div>}
      <div className="grille-2">
        {SENS.map((s) => (
          <section className="card" key={s.cle}>
            <h3>{s.titre}</h3>
            <form onSubmit={(e) => ajouter(e, s.cle)} className="actions-ligne" style={{ margin: '12px 0' }}>
              <input aria-label={`Nouvelle ${s.cle === 'depense' ? 'catégorie de dépense' : 'catégorie d’entrée'}`}
                placeholder={s.exemple} value={nouvelle[s.cle]} required maxLength={100}
                onChange={(e) => setNouvelle({ ...nouvelle, [s.cle]: e.target.value })} style={{ flex: 1 }} />
              <button className="btn-primary btn-compact" type="submit"><Icon nom="plus" taille={14} /> Ajouter</button>
            </form>
            <table className="data-table"><tbody>
              {liste.filter((c) => c.sens === s.cle).map((c) => (
                <tr key={c.id} className={c.actif ? '' : 'ligne-annulee'}>
                  <td>{c.nom}{!c.actif && <> <span className="badge">Désactivée</span></>}<br /><small className="muted">{c.utilisations} opération{c.utilisations > 1 ? 's' : ''}</small></td>
                  <td>
                    <button type="button" className="btn-small btn-secondary" onClick={() => basculer(c)}>{c.actif ? 'Désactiver' : 'Réactiver'}</button>
                    <button type="button" className="btn-small btn-danger" onClick={() => supprimer(c)} aria-label={`Supprimer ${c.nom}`}>Supprimer</button>
                  </td>
                </tr>
              ))}
            </tbody></table>
          </section>
        ))}
      </div>
    </div>
  );
};

export default Categories;

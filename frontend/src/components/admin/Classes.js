import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../../api/axios';
import { formatApiError } from '../../utils/errors';
import { ouvrirPdf, lundiCourant } from '../../utils/pdf';
import useNiveaux from '../../hooks/useNiveaux';
import Icon from '../ui/Icon';

const LIBRE = '__libre__';
const FORM_VIDE = { niveau: '', niveauLibre: '', serie: '', serieLibre: '', numero: 1 };

const Classes = () => {
  const { niveaux, niveaux_avec_serie: avecSerie, series } = useNiveaux();
  const [items, setItems] = useState([]);
  const [annees, setAnnees] = useState([]);
  const [anneeFilter, setAnneeFilter] = useState('');
  const [anneeForm, setAnneeForm] = useState('');
  const [form, setForm] = useState(FORM_VIDE);
  const [editId, setEditId] = useState(null);
  const [creee, setCreee] = useState(null);
  const [error, setError] = useState('');
  const [selection, setSelection] = useState([]);
  const [semaine, setSemaine] = useState(lundiCourant());

  const loadClasses = useCallback((anneeId) => {
    const params = anneeId ? { annee: anneeId } : {};
    return api.get('/school/classes/', { params }).then(r => setItems(r.data))
      .catch(err => setError(formatApiError(err)));
  }, []);

  useEffect(() => {
    api.get('/school/annees/').then(r => {
      setAnnees(r.data);
      const active = r.data.find(a => a.active);
      if (active) { setAnneeFilter(active.id); setAnneeForm(active.id); }
    }).catch(err => setError(formatApiError(err)));
  }, []);
  useEffect(() => { loadClasses(anneeFilter); setSelection([]); }, [anneeFilter, loadClasses]);

  const niveauEffectif = form.niveau === LIBRE ? form.niveauLibre.trim() : form.niveau;
  const serieEffective = form.serie === LIBRE ? form.serieLibre.trim() : form.serie;
  const besoinSerie = avecSerie.includes(niveauEffectif);
  const apercu = niveauEffectif
    ? [niveauEffectif, besoinSerie ? serieEffective.toUpperCase() : '', form.numero].filter(Boolean).join(' ')
    : '';

  const reinit = () => { setForm(FORM_VIDE); setEditId(null); };

  const soumettre = async (e) => {
    e.preventDefault();
    setError(''); setCreee(null);
    const donnees = {
      niveau: niveauEffectif, serie: besoinSerie ? serieEffective : '',
      numero: Number(form.numero) || 1,
    };
    try {
      if (editId) {
        await api.patch(`/school/classes/${editId}/`, donnees);
      } else {
        const res = await api.post('/school/classes/', { ...donnees, annee_scolaire: anneeForm });
        setCreee(res.data);
      }
      reinit();
      loadClasses(anneeFilter);
    } catch (err) { setError(formatApiError(err)); }
  };

  const modifier = (c) => {
    const connu = niveaux.includes(c.niveau);
    const serieConnue = series.includes(c.serie);
    setEditId(c.id); setCreee(null);
    setForm({
      niveau: c.niveau ? (connu ? c.niveau : LIBRE) : LIBRE, niveauLibre: connu ? '' : (c.niveau || c.nom),
      serie: c.serie ? (serieConnue ? c.serie : LIBRE) : '', serieLibre: serieConnue ? '' : c.serie,
      numero: c.numero,
    });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const supprimer = async (c) => {
    if (!window.confirm(`Supprimer la classe ${c.nom} ? Ses inscriptions, affectations et notes seront aussi supprimées.`)) return;
    setError('');
    try { await api.delete(`/school/classes/${c.id}/`); } catch (err) { setError(formatApiError(err)); }
    loadClasses(anneeFilter);
  };

  const basculer = (id) => setSelection(s => (s.includes(id) ? s.filter(x => x !== id) : [...s, id]));
  const toutSelectionne = items.length > 0 && selection.length === items.length;

  const imprimerFiches = async () => {
    setError('');
    try { await ouvrirPdf('/school/pdf/fiches-appel/', { classes: selection, semaine }); }
    catch (e) { setError(e.message); }
  };

  return (
    <div className="page">
      <h1>Classes</h1>
      <p className="page-subtitle">Du niveau « Petite section » à « Terminale ». Les matières et coefficients se configurent par niveau (et par série en Première et Terminale).</p>
      {error && <div className="error">{error}</div>}

      {creee && (
        <div className="success">
          Classe <strong>{creee.nom}</strong> créée.{' '}
          <Link to={`/admin/classes/${creee.id}/config`} className="btn-small">Configurer ses matières et coefficients</Link>
        </div>
      )}

      <div className="card">
        <h3>{editId ? 'Modifier la classe' : 'Nouvelle classe'}</h3>
        <form onSubmit={soumettre} className="crud-form">
          <div className="form-row">
            {!editId && (
              <div className="form-group"><label htmlFor="annee-classe">Année scolaire</label>
                <select id="annee-classe" value={anneeForm} required onChange={(e) => setAnneeForm(e.target.value)}>
                  <option value="">--</option>
                  {annees.filter(a => !a.cloturee).map(a => <option key={a.id} value={a.id}>{a.libelle}{a.active ? ' (en cours)' : ''}</option>)}
                </select></div>
            )}
            <div className="form-group"><label htmlFor="niveau">Niveau</label>
              <select id="niveau" value={form.niveau} required
                onChange={(e) => setForm({ ...form, niveau: e.target.value, serie: '' })}>
                <option value="">-- Choisir --</option>
                {niveaux.map(n => <option key={n} value={n}>{n}</option>)}
                <option value={LIBRE}>Autre (saisir)…</option>
              </select></div>
            {form.niveau === LIBRE && (
              <div className="form-group"><label htmlFor="niveau-libre">Nom du niveau</label>
                <input id="niveau-libre" value={form.niveauLibre} required placeholder="ex. Maternelle"
                  onChange={(e) => setForm({ ...form, niveauLibre: e.target.value })} /></div>
            )}
            {besoinSerie && (
              <div className="form-group"><label htmlFor="serie">Série</label>
                <select id="serie" value={form.serie} required onChange={(e) => setForm({ ...form, serie: e.target.value })}>
                  <option value="">-- Choisir --</option>
                  {series.map(s => <option key={s} value={s}>Série {s}</option>)}
                  <option value={LIBRE}>Autre (saisir)…</option>
                </select></div>
            )}
            {besoinSerie && form.serie === LIBRE && (
              <div className="form-group"><label htmlFor="serie-libre">Nom de la série</label>
                <input id="serie-libre" value={form.serieLibre} required maxLength={20}
                  onChange={(e) => setForm({ ...form, serieLibre: e.target.value })} /></div>
            )}
            <div className="form-group"><label htmlFor="numero">N° de la classe</label>
              <input id="numero" type="number" min="1" max="99" value={form.numero} required
                onChange={(e) => setForm({ ...form, numero: e.target.value })} /></div>
          </div>
          {apercu && <p className="muted">Nom de la classe : <strong>{apercu}</strong></p>}
          <div className="actions-ligne">
            <button className="btn-primary" type="submit">{editId ? 'Enregistrer' : 'Créer la classe'}</button>
            {editId && <button type="button" className="btn-secondary" onClick={reinit}>Annuler</button>}
          </div>
        </form>
      </div>

      <div className="card">
        <div className="card-titre">
          <h3>Classes ({items.length})</h3>
          <div className="form-group" style={{ margin: 0 }}>
            <select value={anneeFilter} onChange={(e) => setAnneeFilter(e.target.value)} aria-label="Filtrer par année">
              <option value="">Toutes les années</option>
              {annees.map(a => <option key={a.id} value={a.id}>{a.libelle}</option>)}
            </select>
          </div>
        </div>

        <div className="print-bar">
          <span className="print-bar-titre">Fiche d'appel de la semaine du</span>
          <input type="date" value={semaine} onChange={(e) => setSemaine(e.target.value)}
            style={{ width: 'auto' }} aria-label="Semaine" />
          <button type="button" className="btn-small" disabled={selection.length === 0} onClick={imprimerFiches}>
            Imprimer pour {selection.length} classe{selection.length > 1 ? 's' : ''}
          </button>
        </div>

        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th><input type="checkbox" checked={toutSelectionne} aria-label="Tout sélectionner"
                  onChange={() => setSelection(toutSelectionne ? [] : items.map(c => c.id))} /></th>
                <th>Classe</th><th>Année</th><th className="centre">Élèves</th><th>Matières</th><th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map(c => (
                <tr key={c.id}>
                  <td><input type="checkbox" checked={selection.includes(c.id)} onChange={() => basculer(c.id)}
                    aria-label={`Sélectionner ${c.nom}`} /></td>
                  <td><Link to={`/admin/classes/${c.id}`}><strong>{c.nom}</strong></Link></td>
                  <td>{c.annee_scolaire_libelle}</td>
                  <td className="centre">{c.effectif ?? 0}</td>
                  <td>
                    {!c.niveau ? <span className="badge badge-alerte">Niveau à définir</span>
                      : c.configuree ? <span className="badge badge-active">Configurées</span>
                        : <span className="badge badge-alerte">À configurer</span>}
                  </td>
                  <td>
                    <Link className="btn-small btn-secondary" to={`/admin/classes/${c.id}`}>Élèves</Link>
                    {c.niveau && <Link className="btn-small btn-secondary" to={`/admin/classes/${c.id}/config`}>Matières</Link>}
                    <button className="btn-small btn-secondary" onClick={() => modifier(c)} aria-label={`Modifier ${c.nom}`} title="Modifier"><Icon nom="crayonEdit" taille={14} /></button>
                    <button className="btn-small btn-danger" onClick={() => supprimer(c)} aria-label={`Supprimer ${c.nom}`} title="Supprimer"><Icon nom="corbeille" taille={14} /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {items.length === 0 && <p className="muted">Aucune classe pour cette année.</p>}
        </div>
      </div>
    </div>
  );
};

export default Classes;

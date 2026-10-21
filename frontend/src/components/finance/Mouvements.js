import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../../api/axios';
import { formatApiError } from '../../utils/errors';
import { dateDuJour, dateFr, lireMontant } from '../../utils/argent';
import useFinance from '../../hooks/useFinance';
import PageHeader from '../ui/PageHeader';
import EmptyState from '../ui/EmptyState';
import Icon from '../ui/Icon';

const TEXTES = {
  depense: {
    titre: 'Dépenses', sous: 'Dépenses de fonctionnement de l’établissement. Cochez « imprévu » pour une dépense non prévue.',
    nouveau: 'Nouvelle dépense', vide: 'Aucune dépense enregistrée.', icone: 'montee',
  },
  entree: {
    titre: 'Entrées d’argent', sous: 'Argent reçu en dehors de la scolarité des élèves : dons, subventions, locations…',
    nouveau: 'Nouvelle entrée', vide: 'Aucune entrée d’argent enregistrée.', icone: 'descente',
  },
};

const formVide = () => ({ date: dateDuJour(), categorie: '', libelle: '', montant: '', imprevu: false, reference: '', notes: '' });

// Dépenses (sens = 'depense') ou entrées d'argent (sens = 'entree')
const Mouvements = ({ sens = 'depense' }) => {
  const T = TEXTES[sens];
  const { argent } = useFinance();
  const [categories, setCategories] = useState([]);
  const [lignes, setLignes] = useState([]);
  const [filtres, setFiltres] = useState({ q: '', date_debut: '', date_fin: '', categorie: '', imprevu: '' });
  const [form, setForm] = useState(formVide);
  const [enEdition, setEnEdition] = useState(null);
  const [erreur, setErreur] = useState('');
  const [message, setMessage] = useState('');

  useEffect(() => {
    setEnEdition(null); setForm(formVide()); setFiltres({ q: '', date_debut: '', date_fin: '', categorie: '', imprevu: '' });
    api.get('/finance/categories/', { params: { sens, actif: 'true' } })
      .then((r) => setCategories(r.data)).catch((err) => setErreur(formatApiError(err)));
  }, [sens]);

  const charger = useCallback(() => {
    const params = { sens };
    Object.entries(filtres).forEach(([k, v]) => { if (v) params[k] = v; });
    return api.get('/finance/mouvements/', { params })
      .then((r) => setLignes(r.data.results || r.data)).catch((err) => setErreur(formatApiError(err)));
  }, [sens, filtres]);
  useEffect(() => {
    const t = setTimeout(charger, filtres.q ? 300 : 0);
    return () => clearTimeout(t);
  }, [charger, filtres.q]);

  const total = lignes.reduce((t, l) => t + Number(l.montant), 0);
  const changer = (champ, valeur) => setFiltres((f) => ({ ...f, [champ]: valeur }));

  const enregistrer = async (e) => {
    e.preventDefault();
    setErreur(''); setMessage('');
    const montant = lireMontant(form.montant);
    if (montant === null) { setErreur('Le montant est obligatoire.'); return; }
    const corps = { ...form, categorie: Number(form.categorie), montant, imprevu: sens === 'depense' ? form.imprevu : false };
    try {
      if (enEdition) await api.put(`/finance/mouvements/${enEdition}/`, corps);
      else await api.post('/finance/mouvements/', corps);
      setMessage(enEdition ? 'Opération modifiée.' : 'Opération enregistrée.');
      setForm(formVide()); setEnEdition(null);
      charger();
    } catch (err) { setErreur(formatApiError(err)); }
  };

  const modifier = (l) => {
    setEnEdition(l.id);
    setForm({ date: l.date, categorie: String(l.categorie), libelle: l.libelle, montant: String(l.montant),
      imprevu: l.imprevu, reference: l.reference || '', notes: l.notes || '' });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };
  const supprimer = async (l) => {
    if (!window.confirm(`Supprimer « ${l.libelle} » (${argent(l.montant)}) ?`)) return;
    setErreur('');
    try { await api.delete(`/finance/mouvements/${l.id}/`); charger(); } catch (err) { setErreur(formatApiError(err)); }
  };

  return (
    <div className="page">
      <PageHeader titre={T.titre} sousTitre={T.sous}>
        <Link className="btn-secondary" to="/admin/finances/categories"><Icon nom="etiquette" taille={16} /> Catégories</Link>
      </PageHeader>
      {erreur && <div className="error">{erreur}</div>}
      {message && <div className="success">{message}</div>}

      <div className="card">
        <h3>{enEdition ? 'Modifier l’opération' : T.nouveau}</h3>
        {categories.length === 0 && <p className="info alerte">Aucune catégorie : <Link to="/admin/finances/categories">créez-en une</Link> d'abord.</p>}
        <form onSubmit={enregistrer}>
          <div className="form-row">
            <div className="form-group"><label htmlFor="mv-date">Date</label>
              <input id="mv-date" type="date" value={form.date} required onChange={(e) => setForm({ ...form, date: e.target.value })} /></div>
            <div className="form-group"><label htmlFor="mv-cat">Catégorie</label>
              <select id="mv-cat" value={form.categorie} required onChange={(e) => setForm({ ...form, categorie: e.target.value })}>
                <option value="">Choisir…</option>
                {categories.map((c) => <option key={c.id} value={c.id}>{c.nom}</option>)}
              </select></div>
            <div className="form-group"><label htmlFor="mv-lib">Libellé</label>
              <input id="mv-lib" value={form.libelle} required maxLength={200} onChange={(e) => setForm({ ...form, libelle: e.target.value })} /></div>
            <div className="form-group"><label htmlFor="mv-montant">Montant</label>
              <input id="mv-montant" inputMode="decimal" value={form.montant} required onChange={(e) => setForm({ ...form, montant: e.target.value })} /></div>
          </div>
          <div className="form-row">
            <div className="form-group"><label htmlFor="mv-ref">Pièce / référence (facultatif)</label>
              <input id="mv-ref" value={form.reference} maxLength={100} onChange={(e) => setForm({ ...form, reference: e.target.value })} /></div>
            <div className="form-group"><label htmlFor="mv-notes">Notes (facultatif)</label>
              <input id="mv-notes" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></div>
          </div>
          {sens === 'depense' && (
            <label className="case-ligne" style={{ marginBottom: 14 }}>
              <input type="checkbox" checked={form.imprevu} onChange={(e) => setForm({ ...form, imprevu: e.target.checked })} />
              Dépense imprévue
            </label>
          )}
          <div className="actions-ligne">
            <button className="btn-primary" type="submit"><Icon nom={enEdition ? 'valider' : 'plus'} taille={16} /> {enEdition ? 'Enregistrer' : 'Ajouter'}</button>
            {enEdition && <button type="button" className="btn-secondary" onClick={() => { setEnEdition(null); setForm(formVide()); }}>Annuler</button>}
          </div>
        </form>
      </div>

      <div className="card">
        <div className="card-titre">
          <h3>Liste ({lignes.length})</h3>
          <span>Total : <strong>{argent(total)}</strong></span>
        </div>
        <div className="form-row">
          <div className="form-group"><label htmlFor="fl-q">Recherche</label>
            <input id="fl-q" type="search" value={filtres.q} onChange={(e) => changer('q', e.target.value)} /></div>
          <div className="form-group"><label htmlFor="fl-cat">Catégorie</label>
            <select id="fl-cat" value={filtres.categorie} onChange={(e) => changer('categorie', e.target.value)}>
              <option value="">Toutes</option>
              {categories.map((c) => <option key={c.id} value={c.id}>{c.nom}</option>)}
            </select></div>
          <div className="form-group"><label htmlFor="fl-debut">Du</label>
            <input id="fl-debut" type="date" value={filtres.date_debut} onChange={(e) => changer('date_debut', e.target.value)} /></div>
          <div className="form-group"><label htmlFor="fl-fin">Au</label>
            <input id="fl-fin" type="date" value={filtres.date_fin} onChange={(e) => changer('date_fin', e.target.value)} /></div>
          {sens === 'depense' && (
            <div className="form-group"><label htmlFor="fl-imp">Imprévus</label>
              <select id="fl-imp" value={filtres.imprevu} onChange={(e) => changer('imprevu', e.target.value)}>
                <option value="">Toutes les dépenses</option><option value="true">Imprévus seulement</option><option value="false">Hors imprévus</option>
              </select></div>
          )}
        </div>
        {lignes.length === 0 ? <EmptyState icone={T.icone} titre={T.vide} /> : (
          <div className="table-wrap">
            <table className="data-table">
              <thead><tr><th>Date</th><th>Catégorie</th><th>Libellé</th><th>Montant</th><th></th></tr></thead>
              <tbody>
                {lignes.map((l) => (
                  <tr key={l.id}>
                    <td>{dateFr(l.date)}</td>
                    <td>{l.categorie_nom}{l.imprevu && <> <span className="badge badge-pay-a_payer">Imprévu</span></>}</td>
                    <td>{l.libelle}{l.reference && <><br /><small className="muted">Pièce {l.reference}</small></>}</td>
                    <td className="montant">{argent(l.montant)}</td>
                    <td>
                      <button type="button" className="btn-small btn-secondary" onClick={() => modifier(l)} aria-label={`Modifier ${l.libelle}`}>Modifier</button>
                      <button type="button" className="btn-small btn-danger" onClick={() => supprimer(l)} aria-label={`Supprimer ${l.libelle}`}>Supprimer</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default Mouvements;

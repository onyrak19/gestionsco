import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../../api/axios';
import { formatApiError } from '../../utils/errors';
import { lireMontant } from '../../utils/argent';
import useFinance from '../../hooks/useFinance';
import PageHeader from '../ui/PageHeader';
import EmptyState from '../ui/EmptyState';
import Icon from '../ui/Icon';

const formVide = () => ({ nom: '', prenom: '', poste: '', telephone: '', salaire_mensuel: '', date_embauche: '', actif: true });

// Personnel (enseignants et autres employés) avec leur salaire mensuel
const Employes = () => {
  const { argent } = useFinance();
  const [liste, setListe] = useState([]);
  const [form, setForm] = useState(formVide);
  const [enEdition, setEnEdition] = useState(null);
  const [q, setQ] = useState('');
  const [erreur, setErreur] = useState('');
  const [message, setMessage] = useState('');

  const charger = useCallback(() => api.get('/finance/employes/', { params: q.trim() ? { q: q.trim() } : {} })
    .then((r) => setListe(r.data.results || r.data)).catch((err) => setErreur(formatApiError(err))), [q]);
  useEffect(() => {
    const t = setTimeout(charger, q ? 300 : 0);
    return () => clearTimeout(t);
  }, [charger, q]);

  const enregistrer = async (e) => {
    e.preventDefault();
    setErreur(''); setMessage('');
    const salaire = lireMontant(form.salaire_mensuel);
    if (salaire === null) { setErreur('Le salaire mensuel est obligatoire.'); return; }
    const corps = { ...form, salaire_mensuel: salaire, date_embauche: form.date_embauche || null };
    try {
      if (enEdition) await api.put(`/finance/employes/${enEdition}/`, corps);
      else await api.post('/finance/employes/', corps);
      setMessage(enEdition ? 'Employé modifié.' : 'Employé ajouté.');
      setForm(formVide()); setEnEdition(null);
      charger();
    } catch (err) { setErreur(formatApiError(err)); }
  };
  const modifier = (e) => {
    setEnEdition(e.id);
    setForm({ nom: e.nom, prenom: e.prenom || '', poste: e.poste || '', telephone: e.telephone || '',
      salaire_mensuel: String(e.salaire_mensuel), date_embauche: e.date_embauche || '', actif: e.actif });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };
  const supprimer = async (e) => {
    if (!window.confirm(`Supprimer ${e.nom_complet} ?`)) return;
    setErreur('');
    try { await api.delete(`/finance/employes/${e.id}/`); charger(); } catch (err) { setErreur(formatApiError(err)); }
  };
  const champ = (cle, valeur) => setForm({ ...form, [cle]: valeur });

  return (
    <div className="page">
      <PageHeader titre="Employés"
        sousTitre="Personnel payé par l'établissement. Le salaire mensuel sert de base au calcul automatique des paies.">
        <Link className="btn-primary" to="/admin/finances/salaires"><Icon nom="portefeuille" taille={16} /> Payer les salaires</Link>
      </PageHeader>
      {erreur && <div className="error">{erreur}</div>}
      {message && <div className="success">{message}</div>}

      <div className="card">
        <h3>{enEdition ? 'Modifier l’employé' : 'Nouvel employé'}</h3>
        <form onSubmit={enregistrer}>
          <div className="form-row">
            <div className="form-group"><label htmlFor="em-nom">Nom</label>
              <input id="em-nom" value={form.nom} required maxLength={100} onChange={(e) => champ('nom', e.target.value)} /></div>
            <div className="form-group"><label htmlFor="em-prenom">Prénom</label>
              <input id="em-prenom" value={form.prenom} maxLength={100} onChange={(e) => champ('prenom', e.target.value)} /></div>
            <div className="form-group"><label htmlFor="em-poste">Poste</label>
              <input id="em-poste" value={form.poste} maxLength={100} placeholder="Enseignant, gardien…" onChange={(e) => champ('poste', e.target.value)} /></div>
          </div>
          <div className="form-row">
            <div className="form-group"><label htmlFor="em-tel">Téléphone</label>
              <input id="em-tel" value={form.telephone} maxLength={30} onChange={(e) => champ('telephone', e.target.value)} /></div>
            <div className="form-group"><label htmlFor="em-salaire">Salaire mensuel</label>
              <input id="em-salaire" inputMode="decimal" value={form.salaire_mensuel} required onChange={(e) => champ('salaire_mensuel', e.target.value)} /></div>
            <div className="form-group"><label htmlFor="em-date">Date d'embauche</label>
              <input id="em-date" type="date" value={form.date_embauche} onChange={(e) => champ('date_embauche', e.target.value)} /></div>
          </div>
          <label className="case-ligne" style={{ marginBottom: 14 }}>
            <input type="checkbox" checked={form.actif} onChange={(e) => champ('actif', e.target.checked)} /> Employé en activité
          </label>
          <div className="actions-ligne">
            <button className="btn-primary" type="submit"><Icon nom={enEdition ? 'valider' : 'plus'} taille={16} /> {enEdition ? 'Enregistrer' : 'Ajouter'}</button>
            {enEdition && <button type="button" className="btn-secondary" onClick={() => { setEnEdition(null); setForm(formVide()); }}>Annuler</button>}
          </div>
        </form>
      </div>

      <div className="card">
        <div className="card-titre">
          <h3>Liste ({liste.length})</h3>
          <div className="champ-recherche"><Icon nom="recherche" taille={16} />
            <input placeholder="Rechercher (nom, poste)" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Rechercher un employé" /></div>
        </div>
        {liste.length === 0 ? <EmptyState icone="enseignant" titre="Aucun employé">Ajoutez le personnel avec le formulaire ci-dessus.</EmptyState> : (
          <div className="table-wrap">
            <table className="data-table">
              <thead><tr><th>Employé</th><th>Poste</th><th>Salaire mensuel</th><th>Avances dues</th><th></th></tr></thead>
              <tbody>
                {liste.map((e) => (
                  <tr key={e.id} className={e.actif ? '' : 'ligne-annulee'}>
                    <td><strong>{e.nom_complet}</strong>{!e.actif && <> <span className="badge">Inactif</span></>}<br /><small className="muted">{e.telephone}</small></td>
                    <td>{e.poste}</td>
                    <td className="montant">{argent(e.salaire_mensuel)}</td>
                    <td className={`montant ${e.avances_dues > 0 ? 'solde-neg' : ''}`}>{argent(e.avances_dues)}</td>
                    <td>
                      <button type="button" className="btn-small btn-secondary" onClick={() => modifier(e)} aria-label={`Modifier ${e.nom_complet}`}>Modifier</button>
                      <button type="button" className="btn-small btn-danger" onClick={() => supprimer(e)} aria-label={`Supprimer ${e.nom_complet}`}>Supprimer</button>
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

export default Employes;

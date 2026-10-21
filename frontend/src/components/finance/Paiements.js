import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../../api/axios';
import { formatApiError } from '../../utils/errors';
import { ouvrirPdfGet } from '../../utils/pdf';
import { dateFr } from '../../utils/argent';
import useAnnees from '../../hooks/useAnnees';
import useFinance from '../../hooks/useFinance';
import PageHeader from '../ui/PageHeader';
import SelectAnnee from '../ui/SelectAnnee';
import EmptyState from '../ui/EmptyState';
import Icon from '../ui/Icon';
import StatutPaiement from '../ui/StatutPaiement';
import AnnulerModal from './AnnulerModal';

// Historique des encaissements : reçus, annulations (un paiement annulé reste visible)
const Paiements = () => {
  const { argent, types_paiement: types } = useFinance();
  const { annees, annee, setAnnee, pret } = useAnnees();
  const [filtres, setFiltres] = useState({ type: '', q: '', annule: '', date_debut: '', date_fin: '' });
  const [donnees, setDonnees] = useState({ total: 0, paiements: [] });
  const [erreur, setErreur] = useState('');
  const [message, setMessage] = useState('');
  const [aAnnuler, setAAnnuler] = useState(null);

  const charger = useCallback(() => {
    if (!annee) return Promise.resolve();
    const params = { annee };
    Object.entries(filtres).forEach(([k, v]) => { if (v) params[k] = v; });
    return api.get('/finance/paiements/', { params })
      .then((r) => { setDonnees(r.data); setErreur(''); })
      .catch((err) => setErreur(formatApiError(err)));
  }, [annee, filtres]);

  useEffect(() => {
    const t = setTimeout(charger, filtres.q ? 300 : 0);
    return () => clearTimeout(t);
  }, [charger, filtres.q]);

  const changer = (champ, valeur) => setFiltres((f) => ({ ...f, [champ]: valeur }));
  const recu = async (p) => {
    setErreur('');
    try { await ouvrirPdfGet(`/finance/paiements/${p.id}/recu/`); } catch (e) { setErreur(e.message); }
  };

  return (
    <div className="page">
      <PageHeader titre="Paiements des élèves"
        sousTitre="Tous les encaissements, avec leur reçu. Un paiement annulé n'est jamais effacé : il reste visible avec son motif." />
      {erreur && <div className="error">{erreur}</div>}
      {message && <div className="success">{message}</div>}

      <div className="card">
        <div className="form-row">
          {pret && <SelectAnnee id="pa-annee" annees={annees} valeur={annee} onChange={setAnnee} />}
          <div className="form-group"><label htmlFor="pa-type">Type</label>
            <select id="pa-type" value={filtres.type} onChange={(e) => changer('type', e.target.value)}>
              <option value="">Tous</option>
              {types.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select></div>
          <div className="form-group"><label htmlFor="pa-etat">État</label>
            <select id="pa-etat" value={filtres.annule} onChange={(e) => changer('annule', e.target.value)}>
              <option value="">Tous</option><option value="false">Valides</option><option value="true">Annulés</option>
            </select></div>
          <div className="form-group"><label htmlFor="pa-debut">Du</label>
            <input id="pa-debut" type="date" value={filtres.date_debut} onChange={(e) => changer('date_debut', e.target.value)} /></div>
          <div className="form-group"><label htmlFor="pa-fin">Au</label>
            <input id="pa-fin" type="date" value={filtres.date_fin} onChange={(e) => changer('date_fin', e.target.value)} /></div>
          <div className="form-group"><label htmlFor="pa-q">Recherche</label>
            <input id="pa-q" type="search" placeholder="Élève, matricule ou n° de reçu" value={filtres.q} onChange={(e) => changer('q', e.target.value)} /></div>
        </div>
      </div>

      <div className="card">
        <div className="card-titre">
          <h3>{donnees.paiements.length} paiement{donnees.paiements.length > 1 ? 's' : ''}</h3>
          <span>Total encaissé : <strong className="solde-pos">{argent(donnees.total)}</strong></span>
        </div>
        {donnees.paiements.length === 0 ? (
          <EmptyState icone="recu" titre="Aucun paiement">
            Les paiements apparaissent ici dès qu'ils sont encaissés depuis <Link to="/admin/finances/encaissements">Encaissements</Link>.
          </EmptyState>
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead><tr><th>Reçu</th><th>Date</th><th>Élève</th><th>Détail</th><th>Mode</th><th>Montant</th><th></th></tr></thead>
              <tbody>
                {donnees.paiements.map((p) => (
                  <tr key={p.id} className={p.annule ? 'ligne-annulee' : ''}>
                    <td>{p.numero}{p.annule && <> <StatutPaiement statut="annule" /></>}</td>
                    <td>{dateFr(p.date)}</td>
                    <td>
                      {p.inscription
                        ? <Link to={`/admin/finances/eleves/${p.inscription}`}>{p.eleve_nom}</Link>
                        : p.eleve_nom}
                      <br /><small className="muted">{p.classe_nom}</small>
                    </td>
                    <td>{p.lignes.map((l) => l.libelle).join(', ')}{p.annule && <><br /><small className="muted">Annulé : {p.motif_annulation}</small></>}</td>
                    <td>{p.mode_libelle}</td>
                    <td className="montant">{argent(p.montant_total)}</td>
                    <td>
                      <button type="button" className="btn-small btn-secondary" onClick={() => recu(p)}><Icon nom="recu" taille={14} /> Reçu</button>
                      {!p.annule && <button type="button" className="btn-small btn-danger" onClick={() => setAAnnuler(p)}>Annuler</button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {aAnnuler && (
        <AnnulerModal titre={`Annuler le paiement ${aAnnuler.numero}`}
          description={`Le paiement de ${argent(aAnnuler.montant_total)} (${aAnnuler.eleve_nom}) restera visible, barré « annulé ».`}
          envoyer={(motif) => api.post(`/finance/paiements/${aAnnuler.id}/annuler/`, { motif })}
          onClose={() => setAAnnuler(null)}
          onDone={() => { setAAnnuler(null); setMessage('Paiement annulé.'); charger(); }} />
      )}
    </div>
  );
};

export default Paiements;

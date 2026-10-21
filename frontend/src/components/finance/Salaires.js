import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../../api/axios';
import { formatApiError } from '../../utils/errors';
import { ouvrirPdf, ouvrirPdfGet } from '../../utils/pdf';
import { dateDuJour, dateFr, lireMontant, moisCourant } from '../../utils/argent';
import useFinance from '../../hooks/useFinance';
import PageHeader from '../ui/PageHeader';
import EmptyState from '../ui/EmptyState';
import Icon from '../ui/Icon';
import StatutPaiement from '../ui/StatutPaiement';
import AnnulerModal from './AnnulerModal';
import PaieIndividuelle from './PaieIndividuelle';
import PaieGroupee from './PaieGroupee';

const ONGLETS = [
  { cle: 'individuelle', libelle: 'Payer un employé' },
  { cle: 'groupee', libelle: 'Paie en un clic' },
  { cle: 'historique', libelle: 'Historique' },
  { cle: 'avances', libelle: 'Avances' },
];

const Historique = ({ version, argent, onChange }) => {
  const [data, setData] = useState({ total_net: 0, paies: [] });
  const [aAnnuler, setAAnnuler] = useState(null);
  const [erreur, setErreur] = useState('');
  const [moisEtat, setMoisEtat] = useState(moisCourant());

  const charger = useCallback(() => api.get('/finance/salaires/')
    .then((r) => setData(r.data)).catch((err) => setErreur(formatApiError(err))), []);
  useEffect(() => { charger(); }, [charger, version]);

  const fiche = async (p) => { setErreur(''); try { await ouvrirPdfGet(`/finance/salaires/${p.id}/fiche/`); } catch (e) { setErreur(e.message); } };
  const etat = async () => { setErreur(''); try { await ouvrirPdf('/finance/pdf/etat-salaires/', { mois: moisEtat }); } catch (e) { setErreur(e.message); } };

  return (
    <div className="card">
      {erreur && <div className="error">{erreur}</div>}
      <div className="card-titre">
        <h3>Paies ({data.paies.length}) — net payé : <span className="solde-pos">{argent(data.total_net)}</span></h3>
        <div className="actions-ligne">
          <input type="month" value={moisEtat} onChange={(e) => setMoisEtat(e.target.value)} aria-label="Mois de l'état des salaires" style={{ width: 'auto' }} />
          <button type="button" className="btn-secondary btn-compact" disabled={!moisEtat} onClick={etat}><Icon nom="imprimante" taille={14} /> État des salaires</button>
        </div>
      </div>
      {data.paies.length === 0 ? <EmptyState icone="portefeuille" titre="Aucune paie">Les salaires payés apparaîtront ici.</EmptyState> : (
        <div className="table-wrap">
          <table className="data-table">
            <thead><tr><th>N°</th><th>Date</th><th>Employé</th><th>Mois</th><th>Brut</th><th>Retenues</th><th>Net</th><th></th></tr></thead>
            <tbody>
              {data.paies.map((p) => (
                <tr key={p.id} className={p.annule ? 'ligne-annulee' : ''}>
                  <td>{p.numero}{p.annule && <> <StatutPaiement statut="annule" /></>}</td>
                  <td>{dateFr(p.date)}</td>
                  <td>{p.employe_nom}<br /><small className="muted">{p.poste}</small></td>
                  <td>{p.exceptionnel ? <span title={p.motif_exceptionnel}>Exceptionnel</span> : p.mois.map((m) => m.libelle).join(', ')}</td>
                  <td className="montant">{argent(p.montant_brut)}</td>
                  <td className="montant">{argent(p.retenue_avances + p.autres_retenues)}</td>
                  <td className="montant">{argent(p.net_paye)}</td>
                  <td>
                    <button type="button" className="btn-small btn-secondary" onClick={() => fiche(p)}><Icon nom="recu" taille={14} /> Fiche</button>
                    {!p.annule && <button type="button" className="btn-small btn-danger" onClick={() => setAAnnuler(p)}>Annuler</button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {aAnnuler && (
        <AnnulerModal titre={`Annuler la paie ${aAnnuler.numero}`}
          description="Les avances retenues sur cette paie redeviennent dues."
          envoyer={(motif) => api.post(`/finance/salaires/${aAnnuler.id}/annuler/`, { motif })}
          onClose={() => setAAnnuler(null)} onDone={() => { setAAnnuler(null); charger(); onChange(); }} />
      )}
    </div>
  );
};

const Avances = ({ employes, argent, onChange }) => {
  const [liste, setListe] = useState([]);
  const [form, setForm] = useState({ employe: '', date: dateDuJour(), montant: '', motif: '' });
  const [erreur, setErreur] = useState('');

  const charger = useCallback(() => api.get('/finance/avances/')
    .then((r) => setListe(r.data.results || r.data)).catch((err) => setErreur(formatApiError(err))), []);
  useEffect(() => { charger(); }, [charger]);

  const ajouter = async (e) => {
    e.preventDefault();
    setErreur('');
    const montant = lireMontant(form.montant);
    if (montant === null) { setErreur('Le montant est obligatoire.'); return; }
    try {
      await api.post('/finance/avances/', { ...form, employe: Number(form.employe), montant });
      setForm({ ...form, montant: '', motif: '' });
      charger(); onChange();
    } catch (err) { setErreur(formatApiError(err)); }
  };
  const annuler = async (a) => {
    if (!window.confirm(`Annuler l'avance de ${argent(a.montant)} de ${a.employe_nom} ?`)) return;
    setErreur('');
    try { await api.post(`/finance/avances/${a.id}/annuler/`); charger(); onChange(); } catch (err) { setErreur(formatApiError(err)); }
  };

  return (
    <>
      <form className="card" onSubmit={ajouter}>
        <h3>Nouvelle avance sur salaire</h3>
        {erreur && <div className="error">{erreur}</div>}
        <div className="form-row">
          <div className="form-group"><label htmlFor="av-emp">Employé</label>
            <select id="av-emp" value={form.employe} required onChange={(e) => setForm({ ...form, employe: e.target.value })}>
              <option value="">Choisir…</option>
              {employes.map((e) => <option key={e.id} value={e.id}>{e.nom_complet}</option>)}
            </select></div>
          <div className="form-group"><label htmlFor="av-date">Date</label>
            <input id="av-date" type="date" value={form.date} max={dateDuJour()} required onChange={(e) => setForm({ ...form, date: e.target.value })} /></div>
          <div className="form-group"><label htmlFor="av-montant">Montant</label>
            <input id="av-montant" inputMode="decimal" value={form.montant} required onChange={(e) => setForm({ ...form, montant: e.target.value })} /></div>
          <div className="form-group"><label htmlFor="av-motif">Motif</label>
            <input id="av-motif" value={form.motif} maxLength={255} onChange={(e) => setForm({ ...form, motif: e.target.value })} /></div>
        </div>
        <button className="btn-primary" type="submit"><Icon nom="plus" taille={16} /> Enregistrer l'avance</button>
        <p className="muted" style={{ marginTop: 10 }}>L'avance sera retenue automatiquement sur les prochaines paies.</p>
      </form>
      <div className="card">
        <h3>Avances ({liste.length})</h3>
        {liste.length === 0 ? <p className="muted">Aucune avance.</p> : (
          <div className="table-wrap">
            <table className="data-table">
              <thead><tr><th>Date</th><th>Employé</th><th>Montant</th><th>Reste à rembourser</th><th></th></tr></thead>
              <tbody>
                {liste.map((a) => (
                  <tr key={a.id} className={a.annulee ? 'ligne-annulee' : ''}>
                    <td>{dateFr(a.date)}</td>
                    <td>{a.employe_nom}{a.motif && <><br /><small className="muted">{a.motif}</small></>}</td>
                    <td className="montant">{argent(a.montant)}</td>
                    <td className="montant">{a.annulee ? <StatutPaiement statut="annule" /> : argent(a.restant)}</td>
                    <td>{!a.annulee && <button type="button" className="btn-small btn-danger" onClick={() => annuler(a)}>Annuler</button>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
};

// Salaires : paie individuelle, paie en un clic, historique et avances
const Salaires = () => {
  const { argent } = useFinance();
  const [onglet, setOnglet] = useState('individuelle');
  const [employes, setEmployes] = useState([]);
  const [version, setVersion] = useState(0);
  const [erreur, setErreur] = useState('');

  const chargerEmployes = useCallback(() => api.get('/finance/employes/', { params: { actif: 'true' } })
    .then((r) => setEmployes(r.data.results || r.data)).catch((err) => setErreur(formatApiError(err))), []);
  useEffect(() => { chargerEmployes(); }, [chargerEmployes]);
  const apresChangement = () => { setVersion((v) => v + 1); chargerEmployes(); };

  return (
    <div className="page">
      <PageHeader titre="Salaires"
        sousTitre="Le montant est calculé : salaire de l'employé × nombre de mois, moins les avances et retenues." />
      {erreur && <div className="error">{erreur}</div>}
      <div className="onglets" role="tablist">
        {ONGLETS.map((o) => (
          <button key={o.cle} type="button" role="tab" aria-selected={onglet === o.cle}
            className={`onglet ${onglet === o.cle ? 'actif' : ''}`} onClick={() => setOnglet(o.cle)}>{o.libelle}</button>
        ))}
      </div>
      {employes.length === 0 && onglet !== 'historique' && (
        <div className="info alerte">Aucun employé en activité. Ajoutez-en dans <Link to="/admin/finances/employes">Employés</Link>.</div>
      )}
      {onglet === 'individuelle' && <PaieIndividuelle employes={employes} onPaye={apresChangement} />}
      {onglet === 'groupee' && <PaieGroupee employes={employes} onPaye={apresChangement} />}
      {onglet === 'historique' && <Historique version={version} argent={argent} onChange={apresChangement} />}
      {onglet === 'avances' && <Avances employes={employes} argent={argent} onChange={apresChangement} />}
    </div>
  );
};

export default Salaires;

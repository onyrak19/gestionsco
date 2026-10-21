import React, { useState } from 'react';
import api from '../../api/axios';
import { formatApiError } from '../../utils/errors';
import { dateDuJour, lireMontant } from '../../utils/argent';
import useFinance from '../../hooks/useFinance';
import ChoixMois from '../ui/ChoixMois';
import StatutPaiement from '../ui/StatutPaiement';

// Paie de plusieurs employés en un clic, pour les mêmes mois (aperçu d'abord)
const PaieGroupee = ({ employes, onPaye }) => {
  const { argent, modes_paiement: modes, annee_active: anneeActive } = useFinance();
  const [choisis, setChoisis] = useState([]);
  const [mois, setMois] = useState([]);
  const [date, setDate] = useState(dateDuJour());
  const [mode, setMode] = useState('especes');
  const [retenues, setRetenues] = useState({});
  const [resultat, setResultat] = useState(null);
  const [erreur, setErreur] = useState('');
  const [envoi, setEnvoi] = useState(false);

  const toutes = employes.length > 0 && choisis.length === employes.length;
  const basculer = (id) => { setResultat(null); setChoisis((c) => (c.includes(id) ? c.filter((x) => x !== id) : [...c, id])); };
  const majRetenue = (id, champ, valeur) => { setResultat(null); setRetenues((r) => ({ ...r, [id]: { ...(r[id] || {}), [champ]: valeur } })); };

  const corps = (apercu) => {
    const r = {};
    choisis.forEach((id) => {
      const v = retenues[id];
      const montant = v ? lireMontant(v.montant) : null;
      if (montant) r[id] = { montant, motif: v.motif || '' };
    });
    return { employes: choisis, mois, date, mode, retenues: r, apercu };
  };

  const lancer = async (apercu) => {
    setErreur(''); setEnvoi(true);
    try {
      const res = await api.post('/finance/salaires/groupe/', corps(apercu));
      setResultat(res.data);
      if (!apercu) onPaye();
    } catch (err) { setErreur(formatApiError(err)); }
    setEnvoi(false);
  };

  const pret = choisis.length > 0 && mois.length > 0;
  const apercuFait = resultat && resultat.apercu;

  return (
    <div className="card">
      {erreur && <div className="error">{erreur}</div>}
      <div className="card-titre">
        <h3>Employés à payer ({choisis.length})</h3>
        <button type="button" className="btn-secondary btn-compact"
          onClick={() => { setResultat(null); setChoisis(toutes ? [] : employes.map((e) => e.id)); }}>
          {toutes ? 'Tout désélectionner' : 'Tous les employés'}
        </button>
      </div>
      <div className="liste-cases" role="group" aria-label="Employés à payer">
        {employes.map((e) => (
          <label key={e.id} className={`case-ligne ${choisis.includes(e.id) ? 'cochee' : ''}`}>
            <input type="checkbox" checked={choisis.includes(e.id)} onChange={() => basculer(e.id)} />
            <span>{e.nom_complet}</span><small className="muted">{argent(e.salaire_mensuel)}</small>
          </label>
        ))}
      </div>

      <div className="form-group" style={{ marginTop: 16 }}>
        <label>Mois payés</label>
        <ChoixMois options={anneeActive?.mois || []} valeur={mois} onChange={(m) => { setResultat(null); setMois(m); }} libre etiquette="Mois à payer" />
      </div>
      <div className="form-row">
        <div className="form-group"><label htmlFor="pg-date">Date du paiement</label>
          <input id="pg-date" type="date" value={date} max={dateDuJour()} onChange={(e) => setDate(e.target.value)} /></div>
        <div className="form-group"><label htmlFor="pg-mode">Mode</label>
          <select id="pg-mode" value={mode} onChange={(e) => setMode(e.target.value)}>
            {(modes.length ? modes : [{ value: 'especes', label: 'Espèces' }]).map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
          </select></div>
      </div>

      {choisis.length > 0 && (
        <details className="repliable-details">
          <summary>Retenues supplémentaires (pénalités…) — facultatif</summary>
          {choisis.map((id) => {
            const e = employes.find((x) => x.id === id);
            return (
              <div className="form-row" key={id}>
                <div className="form-group"><label htmlFor={`pg-m-${id}`}>{e.nom_complet} — montant</label>
                  <input id={`pg-m-${id}`} inputMode="decimal" value={retenues[id]?.montant || ''} onChange={(ev) => majRetenue(id, 'montant', ev.target.value)} /></div>
                <div className="form-group"><label htmlFor={`pg-t-${id}`}>Motif</label>
                  <input id={`pg-t-${id}`} value={retenues[id]?.motif || ''} onChange={(ev) => majRetenue(id, 'motif', ev.target.value)} /></div>
              </div>
            );
          })}
        </details>
      )}

      <div className="actions-ligne" style={{ marginTop: 14 }}>
        <button type="button" className="btn-secondary" disabled={!pret || envoi} onClick={() => lancer(true)}>Voir le récapitulatif</button>
        <button type="button" className="btn-primary" disabled={!apercuFait || envoi || resultat.nb_erreurs === resultat.resultats.length}
          onClick={() => lancer(false)}>{envoi ? 'Paiement…' : 'Payer en un clic'}</button>
      </div>

      {resultat && (
        <div style={{ marginTop: 18 }}>
          {!resultat.apercu && <div className="success">{resultat.nb_payes} salaire(s) payé(s).{resultat.nb_erreurs > 0 && ` ${resultat.nb_erreurs} en erreur.`}</div>}
          <div className="table-wrap">
            <table className="data-table">
              <thead><tr><th>Employé</th><th>Brut</th><th>Retenues</th><th>Net</th><th>Statut</th></tr></thead>
              <tbody>
                {resultat.resultats.map((r) => (
                  <tr key={r.employe}>
                    <td>{r.nom}<br /><small className="muted">{r.poste}</small></td>
                    <td className="montant">{argent(r.brut)}</td>
                    <td className="montant">{argent(r.retenue_avance + r.autres_retenues)}</td>
                    <td className="montant">{argent(r.net)}</td>
                    <td><StatutPaiement statut={r.statut} />{r.message && <><br /><small className="muted">{r.message}</small></>}</td>
                  </tr>
                ))}
                <tr className="ligne-total"><td>Total</td><td className="montant">{argent(resultat.total_brut)}</td><td></td><td className="montant">{argent(resultat.total_net)}</td><td></td></tr>
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

export default PaieGroupee;

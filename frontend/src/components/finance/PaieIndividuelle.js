import React, { useEffect, useState } from 'react';
import api from '../../api/axios';
import { formatApiError } from '../../utils/errors';
import { ouvrirPdfGet } from '../../utils/pdf';
import { dateDuJour, lireMontant } from '../../utils/argent';
import useFinance from '../../hooks/useFinance';
import ChoixMois from '../ui/ChoixMois';

// Paie d'un employé : le brut = salaire × nombre de mois ; les avances sont retenues automatiquement
const PaieIndividuelle = ({ employes, onPaye }) => {
  const { argent, modes_paiement: modes, annee_active: anneeActive } = useFinance();
  const [employe, setEmploye] = useState('');
  const [situation, setSituation] = useState(null);
  const [mois, setMois] = useState([]);
  const [exceptionnel, setExceptionnel] = useState(false);
  const [montantExc, setMontantExc] = useState('');
  const [motifExc, setMotifExc] = useState('');
  const [retenue, setRetenue] = useState('');
  const [motifRetenue, setMotifRetenue] = useState('');
  const [date, setDate] = useState(dateDuJour());
  const [mode, setMode] = useState('especes');
  const [apercu, setApercu] = useState(null);
  const [erreur, setErreur] = useState('');
  const [message, setMessage] = useState('');
  const [envoi, setEnvoi] = useState(false);

  useEffect(() => {
    setSituation(null); setMois([]); setApercu(null);
    if (!employe) return;
    api.get(`/finance/employes/${employe}/situation/`).then((r) => setSituation(r.data))
      .catch((err) => setErreur(formatApiError(err)));
  }, [employe]);

  const corps = (sansEnregistrer) => ({
    employe: Number(employe), date, mode, apercu: sansEnregistrer,
    mois: exceptionnel ? [] : mois,
    exceptionnel,
    ...(exceptionnel ? { montant_exceptionnel: lireMontant(montantExc), motif_exceptionnel: motifExc } : {}),
    autres_retenues: lireMontant(retenue) || 0, motif_retenues: motifRetenue,
  });
  const complet = employe && (exceptionnel ? lireMontant(montantExc) !== null && motifExc.trim() : mois.length > 0);

  // Aperçu automatique du net à payer
  useEffect(() => {
    setApercu(null);
    if (!complet) return undefined;
    let annule = false;
    const t = setTimeout(() => {
      api.post('/finance/salaires/', corps(true))
        .then((r) => { if (!annule) { setApercu(r.data); setErreur(''); } })
        .catch((err) => { if (!annule) setErreur(formatApiError(err)); });
    }, 250);
    return () => { annule = true; clearTimeout(t); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [employe, mois, exceptionnel, montantExc, motifExc, retenue, motifRetenue, complet]);

  const payer = async (e) => {
    e.preventDefault();
    setErreur(''); setMessage(''); setEnvoi(true);
    try {
      const r = await api.post('/finance/salaires/', corps(false));
      setMessage(`Paie ${r.data.numero} enregistrée : ${argent(r.data.net_paye)} net à ${r.data.employe_nom}.`);
      setMois([]); setRetenue(''); setMotifRetenue(''); setMontantExc(''); setMotifExc(''); setExceptionnel(false);
      const s = await api.get(`/finance/employes/${employe}/situation/`);
      setSituation(s.data);
      onPaye();
      try { await ouvrirPdfGet(`/finance/salaires/${r.data.id}/fiche/`); } catch (err) { setErreur(err.message); }
    } catch (err) { setErreur(formatApiError(err)); }
    setEnvoi(false);
  };

  return (
    <form className="card" onSubmit={payer}>
      {erreur && <div className="error">{erreur}</div>}
      {message && <div className="success">{message}</div>}
      <div className="form-row">
        <div className="form-group"><label htmlFor="pi-emp">Employé</label>
          <select id="pi-emp" value={employe} onChange={(e) => { setEmploye(e.target.value); setMessage(''); }}>
            <option value="">Choisir…</option>
            {employes.map((e) => <option key={e.id} value={e.id}>{e.nom_complet}{e.poste ? ` — ${e.poste}` : ''}</option>)}
          </select></div>
        <div className="form-group"><label htmlFor="pi-date">Date du paiement</label>
          <input id="pi-date" type="date" value={date} max={dateDuJour()} onChange={(e) => setDate(e.target.value)} /></div>
        <div className="form-group"><label htmlFor="pi-mode">Mode</label>
          <select id="pi-mode" value={mode} onChange={(e) => setMode(e.target.value)}>
            {(modes.length ? modes : [{ value: 'especes', label: 'Espèces' }]).map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
          </select></div>
      </div>

      {situation && (
        <>
          <p>Salaire mensuel : <strong>{argent(situation.salaire_mensuel)}</strong>
            {situation.total_avances > 0 && <> · avances à rembourser : <strong className="solde-neg">{argent(situation.total_avances)}</strong> (retenues automatiquement)</>}</p>

          <label className="case-ligne" style={{ marginBottom: 12 }}>
            <input type="checkbox" checked={exceptionnel} onChange={(e) => setExceptionnel(e.target.checked)} />
            Situation exceptionnelle (autre montant que le salaire × mois)
          </label>

          {exceptionnel ? (
            <div className="form-row">
              <div className="form-group"><label htmlFor="pi-mexc">Montant exceptionnel</label>
                <input id="pi-mexc" inputMode="decimal" value={montantExc} onChange={(e) => setMontantExc(e.target.value)} /></div>
              <div className="form-group"><label htmlFor="pi-motexc">Motif (obligatoire)</label>
                <input id="pi-motexc" value={motifExc} maxLength={255} onChange={(e) => setMotifExc(e.target.value)} /></div>
            </div>
          ) : (
            <div className="form-group">
              <label>Mois payés (plusieurs possibles)</label>
              <ChoixMois options={anneeActive?.mois || []} valeur={mois} onChange={setMois}
                desactives={situation.mois_payes} libre etiquette="Mois à payer" />
            </div>
          )}

          <div className="form-row">
            <div className="form-group"><label htmlFor="pi-ret">Autre retenue (pénalité…)</label>
              <input id="pi-ret" inputMode="decimal" value={retenue} onChange={(e) => setRetenue(e.target.value)} /></div>
            <div className="form-group"><label htmlFor="pi-motret">Motif de la retenue</label>
              <input id="pi-motret" value={motifRetenue} maxLength={255} onChange={(e) => setMotifRetenue(e.target.value)} /></div>
          </div>

          <div className="apercu-montant" aria-live="polite">
            {apercu ? (
              <>
                <ul>
                  <li><span>Brut ({apercu.mois.length} mois × {argent(apercu.salaire_mensuel)})</span><span>{argent(apercu.brut)}</span></li>
                  {apercu.retenue_avance > 0 && <li><span>Avance retenue</span><span>- {argent(apercu.retenue_avance)}</span></li>}
                  {apercu.autres_retenues > 0 && <li><span>Autre retenue</span><span>- {argent(apercu.autres_retenues)}</span></li>}
                </ul>
                <div className="apercu-total"><span>Net à payer</span><strong>{argent(apercu.net)}</strong></div>
              </>
            ) : <span className="muted">{complet ? 'Calcul du net…' : 'Choisissez les mois : le montant s\u2019affiche ici.'}</span>}
          </div>
          <button className="btn-primary" type="submit" disabled={!apercu || envoi}>{envoi ? 'Enregistrement…' : 'Payer et imprimer la fiche'}</button>
        </>
      )}
    </form>
  );
};

export default PaieIndividuelle;

import React, { useEffect, useState } from 'react';
import api from '../../api/axios';
import { formatApiError } from '../../utils/errors';
import { dateDuJour } from '../../utils/argent';
import useFinance from '../../hooks/useFinance';
import Modal from '../ui/Modal';
import ChoixMois from '../ui/ChoixMois';

// Encaissement : l'utilisateur choisit QUOI payer ; le montant est calculé par le serveur
// (aperçu avant validation). `situation` vient de GET /finance/inscriptions/<id>/situation/.
const EncaisserModal = ({ inscription, situation, typeInitial, onClose, onDone }) => {
  const { argent, modes_paiement: modes } = useFinance();
  const { droit, ecolage, autres } = situation;
  const peutEcolage = ecolage.mensuel !== null;
  const peutDroit = droit.montant !== null && !droit.paye;
  const autresLibres = autres.filter((a) => !a.paye);

  const premierType = () => {
    if (typeInitial) return typeInitial;
    if (peutEcolage) return 'ecolage';
    if (peutDroit) return 'droit';
    return autresLibres.length ? 'autre' : 'ecolage';
  };
  const [type, setType] = useState(premierType);
  const [mois, setMois] = useState([]);
  const [tarif, setTarif] = useState(autresLibres[0]?.tarif ? String(autresLibres[0].tarif) : '');
  const [date, setDate] = useState(dateDuJour());
  const [mode, setMode] = useState('especes');
  const [reference, setReference] = useState('');
  const [observation, setObservation] = useState('');
  const [apercu, setApercu] = useState(null);
  const [erreur, setErreur] = useState('');
  const [envoi, setEnvoi] = useState(false);

  const complet = type === 'droit' || (type === 'ecolage' && mois.length > 0) || (type === 'autre' && tarif);
  const corps = (sansEnregistrer) => ({
    inscription, type, date, mode, reference, observation, apercu: sansEnregistrer,
    ...(type === 'ecolage' ? { mois } : {}),
    ...(type === 'autre' ? { tarif: Number(tarif) } : {}),
  });

  // Montant automatique : recalculé à chaque changement de choix
  useEffect(() => {
    setApercu(null);
    if (!complet) return undefined;
    let annule = false;
    api.post('/finance/paiements/', corps(true))
      .then((r) => { if (!annule) { setApercu(r.data); setErreur(''); } })
      .catch((err) => { if (!annule) setErreur(formatApiError(err)); });
    return () => { annule = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [type, mois, tarif, complet]);

  const valider = async (e) => {
    e.preventDefault();
    setErreur(''); setEnvoi(true);
    try {
      const r = await api.post('/finance/paiements/', corps(false));
      onDone(r.data);
    } catch (err) { setErreur(formatApiError(err)); setEnvoi(false); }
  };

  const optionsMois = ecolage.mois.map((m) => ({ mois: m.mois, libelle: m.libelle }));
  const dejaPayes = ecolage.mois.filter((m) => m.statut === 'paye' || m.statut === 'non_defini').map((m) => m.mois);

  return (
    <Modal titre="Encaisser un paiement" onClose={onClose}>
      <form onSubmit={valider}>
        {erreur && <div className="error">{erreur}</div>}
        <div className="form-group">
          <label htmlFor="enc-type">Que paie l'élève ?</label>
          <select id="enc-type" value={type} onChange={(e) => { setType(e.target.value); setMois([]); setErreur(''); }}>
            <option value="ecolage" disabled={!peutEcolage}>Écolage (un ou plusieurs mois){peutEcolage ? '' : ' — tarif non défini'}</option>
            <option value="droit" disabled={!peutDroit}>Droit d'inscription{droit.paye ? ' — déjà payé' : peutDroit ? '' : ' — tarif non défini'}</option>
            <option value="autre" disabled={!autresLibres.length}>Autre frais{autresLibres.length ? '' : ' — aucun à payer'}</option>
          </select>
        </div>

        {type === 'ecolage' && (
          <div className="form-group">
            <label>Mois à payer (écolage {argent(ecolage.mensuel)} par mois)</label>
            <ChoixMois options={optionsMois} valeur={mois} onChange={setMois} desactives={dejaPayes} etiquette="Mois à payer" />
          </div>
        )}
        {type === 'autre' && (
          <div className="form-group">
            <label htmlFor="enc-frais">Frais</label>
            <select id="enc-frais" value={tarif} onChange={(e) => setTarif(e.target.value)}>
              {autresLibres.map((a) => <option key={a.tarif} value={a.tarif}>{a.libelle} — {argent(a.montant)}</option>)}
            </select>
          </div>
        )}

        <div className="form-row">
          <div className="form-group"><label htmlFor="enc-date">Date</label>
            <input id="enc-date" type="date" value={date} max={dateDuJour()} onChange={(e) => setDate(e.target.value)} /></div>
          <div className="form-group"><label htmlFor="enc-mode">Mode de paiement</label>
            <select id="enc-mode" value={mode} onChange={(e) => setMode(e.target.value)}>
              {(modes.length ? modes : [{ value: 'especes', label: 'Espèces' }]).map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
            </select></div>
        </div>
        {mode !== 'especes' && (
          <div className="form-group"><label htmlFor="enc-ref">Référence (n° de chèque, de transaction…)</label>
            <input id="enc-ref" value={reference} maxLength={100} onChange={(e) => setReference(e.target.value)} /></div>
        )}
        <div className="form-group"><label htmlFor="enc-obs">Observation (facultatif)</label>
          <input id="enc-obs" value={observation} maxLength={255} onChange={(e) => setObservation(e.target.value)} /></div>

        <div className="apercu-montant" aria-live="polite">
          {apercu ? (
            <>
              <ul>{apercu.lignes.map((l, i) => <li key={i}><span>{l.libelle}</span><span>{argent(l.montant)}</span></li>)}</ul>
              <div className="apercu-total"><span>Total à encaisser</span><strong>{argent(apercu.total)}</strong></div>
            </>
          ) : <span className="muted">{complet ? 'Calcul du montant…' : 'Choisissez ce qui est payé : le montant s\u2019affiche ici.'}</span>}
        </div>

        <div className="actions-ligne">
          <button className="btn-primary" type="submit" disabled={!apercu || envoi}>{envoi ? 'Enregistrement…' : 'Encaisser'}</button>
          <button type="button" className="btn-secondary" onClick={onClose}>Annuler</button>
        </div>
      </form>
    </Modal>
  );
};

export default EncaisserModal;

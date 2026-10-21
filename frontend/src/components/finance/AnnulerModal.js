import React, { useState } from 'react';
import Modal from '../ui/Modal';
import { formatApiError } from '../../utils/errors';

// Annulation d'un paiement, d'une paie ou d'une avance : le motif est obligatoire (traçabilité).
// `envoyer(motif)` : fonction asynchrone qui appelle l'API.
const AnnulerModal = ({ titre, description, avecMotif = true, envoyer, onClose, onDone }) => {
  const [motif, setMotif] = useState('');
  const [erreur, setErreur] = useState('');
  const [envoi, setEnvoi] = useState(false);

  const valider = async (e) => {
    e.preventDefault();
    setErreur(''); setEnvoi(true);
    try {
      await envoyer(motif.trim());
      onDone();
    } catch (err) { setErreur(formatApiError(err)); setEnvoi(false); }
  };

  return (
    <Modal titre={titre} onClose={onClose}>
      <form onSubmit={valider}>
        <p className="muted">{description}</p>
        {erreur && <div className="error">{erreur}</div>}
        {avecMotif && (
          <div className="form-group">
            <label htmlFor="an-motif">Motif de l'annulation</label>
            <input id="an-motif" value={motif} required maxLength={255} autoFocus onChange={(e) => setMotif(e.target.value)} />
          </div>
        )}
        <div className="actions-ligne">
          <button className="btn-danger" type="submit" disabled={envoi || (avecMotif && !motif.trim())}>
            {envoi ? 'Annulation…' : 'Confirmer l\u2019annulation'}
          </button>
          <button type="button" className="btn-secondary" onClick={onClose}>Retour</button>
        </div>
      </form>
    </Modal>
  );
};

export default AnnulerModal;

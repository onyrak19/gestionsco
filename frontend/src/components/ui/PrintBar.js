import React, { useState } from 'react';
import { ouvrirPdf } from '../../utils/pdf';
import { TRIMESTRES } from '../../utils/labels';

// Barre d'impression des élèves sélectionnés : cartes, certificats, bulletins.
// ids = identifiants d'inscriptions sélectionnées
const PrintBar = ({ ids, ordre = 'alpha', onError }) => {
  const [trimestre, setTrimestre] = useState(1);
  const [enCours, setEnCours] = useState('');

  const lancer = async (type, chemin, extra = {}) => {
    setEnCours(type);
    onError && onError('');
    try {
      await ouvrirPdf(chemin, { inscriptions: ids, ordre, ...extra });
    } catch (e) {
      onError && onError(e.message);
    } finally {
      setEnCours('');
    }
  };
  const vide = ids.length === 0;

  return (
    <div className="print-bar">
      <span className="print-bar-titre">Imprimer pour <strong>{ids.length}</strong> élève{ids.length > 1 ? 's' : ''} :</span>
      <button type="button" className="btn-small" disabled={vide || !!enCours}
        onClick={() => lancer('cartes', '/school/pdf/cartes/')}>
        {enCours === 'cartes' ? '…' : 'Cartes d\'élève'}
      </button>
      <button type="button" className="btn-small" disabled={vide || !!enCours}
        onClick={() => lancer('certificats', '/school/pdf/certificats/')}>
        {enCours === 'certificats' ? '…' : 'Certificats de scolarité'}
      </button>
      <span className="print-bar-groupe">
        <select value={trimestre} onChange={(e) => setTrimestre(Number(e.target.value))} aria-label="Trimestre du bulletin">
          {TRIMESTRES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
        </select>
        <button type="button" className="btn-small" disabled={vide || !!enCours}
          onClick={() => lancer('bulletins', '/school/pdf/bulletins/', { trimestre })}>
          {enCours === 'bulletins' ? '…' : 'Bulletins'}
        </button>
      </span>
    </div>
  );
};

export default PrintBar;

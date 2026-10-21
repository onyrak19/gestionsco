import React from 'react';

const LIBELLES = {
  paye: 'Payé', impaye: 'Impayé', a_venir: 'À venir', non_defini: 'Tarif non défini',
  annule: 'Annulé', a_payer: 'À payer', deja_paye: 'Déjà payé', erreur: 'Erreur',
};

// Pastille de statut (payé, impayé, annulé...)
const StatutPaiement = ({ statut }) => (
  <span className={`badge badge-pay-${statut}`}>{LIBELLES[statut] || statut}</span>
);

export default StatutPaiement;

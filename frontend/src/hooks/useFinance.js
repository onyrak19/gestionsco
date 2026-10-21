import { useCallback, useEffect, useState } from 'react';
import api from '../api/axios';
import { formaterMontant } from '../utils/argent';

const PAR_DEFAUT = {
  devise: 'Ar', types_paiement: [], modes_paiement: [], types_tarif: [], annee_active: null, mois_courant: '',
};

// Listes et réglages des écrans financiers (devise, modes de paiement, mois de l'année...).
// `argent(25000)` -> « 25 000 Ar » avec la devise configurée sur le serveur.
const useFinance = () => {
  const [params, setParams] = useState(PAR_DEFAUT);
  const [pret, setPret] = useState(false);
  useEffect(() => {
    api.get('/finance/parametres/')
      .then((r) => setParams({ ...PAR_DEFAUT, ...r.data }))
      .catch(() => {})
      .finally(() => setPret(true));
  }, []);
  const devise = params.devise;
  const argent = useCallback((v) => formaterMontant(v, devise), [devise]);
  return { ...params, pret, argent };
};

export default useFinance;

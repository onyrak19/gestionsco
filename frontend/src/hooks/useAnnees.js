import { useEffect, useState } from 'react';
import api from '../api/axios';
import { formatApiError } from '../utils/errors';

// Années scolaires + année choisie (l'année en cours par défaut)
const useAnnees = () => {
  const [annees, setAnnees] = useState([]);
  const [annee, setAnnee] = useState('');
  const [pret, setPret] = useState(false);
  const [erreur, setErreur] = useState('');

  useEffect(() => {
    api.get('/school/annees/').then((r) => {
      setAnnees(r.data);
      const active = r.data.find((a) => a.active) || r.data[0];
      if (active) setAnnee(String(active.id));
    }).catch((err) => setErreur(formatApiError(err))).finally(() => setPret(true));
  }, []);

  const anneeObj = annees.find((a) => String(a.id) === String(annee)) || null;
  return { annees, annee, setAnnee, anneeObj, pret, erreur };
};

export default useAnnees;

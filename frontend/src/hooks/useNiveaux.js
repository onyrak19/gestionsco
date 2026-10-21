import { useEffect, useState } from 'react';
import api from '../api/axios';

// Niveaux, niveaux avec série et séries proposées (fournis par le serveur)
const useNiveaux = () => {
  const [data, setData] = useState({ niveaux: [], niveaux_avec_serie: [], series: [] });
  useEffect(() => {
    api.get('/school/niveaux/').then(r => setData(r.data)).catch(() => {});
  }, []);
  return data;
};

export default useNiveaux;

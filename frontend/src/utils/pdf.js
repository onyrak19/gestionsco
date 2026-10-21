import api from '../api/axios';
import { formatApiError } from './errors';

// Demande un PDF au serveur et l'ouvre dans un nouvel onglet (impression / téléchargement).
// L'onglet est ouvert tout de suite, sinon le navigateur bloque la fenêtre (pop-up).
export const ouvrirPdf = async (chemin, corps) => {
  const fenetre = window.open('', '_blank');
  try {
    const res = await api.post(chemin, corps, { responseType: 'blob' });
    const url = URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }));
    if (fenetre) {
      fenetre.location.href = url;
    } else {
      const lien = document.createElement('a');   // pop-up bloquée : on télécharge
      lien.href = url;
      lien.download = 'document.pdf';
      lien.click();
    }
    setTimeout(() => URL.revokeObjectURL(url), 120000);
  } catch (err) {
    if (fenetre) fenetre.close();
    // en mode "blob", le message d'erreur JSON arrive sous forme de Blob
    if (err.response?.data instanceof Blob) {
      try { err.response.data = JSON.parse(await err.response.data.text()); } catch (e) { /* ignore */ }
    }
    throw new Error(formatApiError(err));
  }
};

// Même chose pour un PDF obtenu par GET (reçu, fiche de paie). `params` : ex. { telecharger: 1 }
export const ouvrirPdfGet = async (chemin, params) => {
  const fenetre = window.open('', '_blank');
  try {
    const res = await api.get(chemin, { params, responseType: 'blob' });
    const url = URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }));
    if (fenetre) {
      fenetre.location.href = url;
    } else {
      const lien = document.createElement('a');
      lien.href = url;
      lien.download = 'document.pdf';
      lien.click();
    }
    setTimeout(() => URL.revokeObjectURL(url), 120000);
  } catch (err) {
    if (fenetre) fenetre.close();
    if (err.response?.data instanceof Blob) {
      try { err.response.data = JSON.parse(await err.response.data.text()); } catch (e) { /* ignore */ }
    }
    throw new Error(formatApiError(err));
  }
};

// Lundi de la semaine courante au format AAAA-MM-JJ
export const lundiCourant = () => {
  const d = new Date();
  d.setDate(d.getDate() - ((d.getDay() + 6) % 7));
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
};

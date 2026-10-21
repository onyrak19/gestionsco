import api from '../api/axios';
import { formatApiError } from './errors';

export const EXTENSIONS_ACCEPTEES = '.pdf,.jpg,.jpeg,.png,.webp,.doc,.docx,.xls,.xlsx,.odt';
export const TAILLE_MAX_PIECE = 10 * 1024 * 1024;
export const NB_MAX_PIECES = 10;

export const TYPES_DOCUMENTS = [
  'Acte de naissance',
  'Certificat médical',
  'Bulletin précédent',
  'Carnet de santé',
  "Pièce d'identité du tuteur",
  'Autre document',
];

export const formatTaille = (octets) => {
  if (octets === null || octets === undefined) return '';
  if (octets < 1024) return `${octets} o`;
  if (octets < 1024 * 1024) return `${Math.round(octets / 1024)} Ko`;
  return `${(octets / (1024 * 1024)).toFixed(1).replace('.', ',')} Mo`;
};

// Message d'erreur si le fichier sera refusé par le serveur, sinon ''
export const verifierPiece = (fichier) => {
  const extension = (fichier.name.match(/\.[^.]+$/) || [''])[0].toLowerCase();
  if (!EXTENSIONS_ACCEPTEES.split(',').includes(extension)) {
    return `« ${fichier.name} » : type de fichier non accepté (PDF, images, Word, Excel ou ODT).`;
  }
  if (fichier.size === 0) return `« ${fichier.name} » est vide.`;
  if (fichier.size > TAILLE_MAX_PIECE) return `« ${fichier.name} » dépasse 10 Mo.`;
  return '';
};

// Récupère un fichier protégé (le jeton est envoyé) et l'ouvre : PDF et images dans un
// nouvel onglet, les autres formats sont téléchargés.
export const ouvrirPiece = async (piece) => {
  const affichable = /^(application\/pdf|image\/)/.test(piece.type_mime || '');
  const fenetre = affichable ? window.open('', '_blank') : null;   // avant l'appel : évite le blocage des pop-ups
  try {
    const res = await api.get(`/school/pieces-jointes/${piece.id}/`, { responseType: 'blob' });
    const url = URL.createObjectURL(new Blob([res.data], { type: piece.type_mime || 'application/octet-stream' }));
    if (fenetre) {
      fenetre.location.href = url;
    } else {
      const lien = document.createElement('a');
      lien.href = url;
      lien.download = piece.nom_original;
      document.body.appendChild(lien);
      lien.click();
      lien.remove();
    }
    setTimeout(() => URL.revokeObjectURL(url), 120000);
  } catch (err) {
    if (fenetre) fenetre.close();
    throw new Error(formatApiError(err, 'Impossible d’ouvrir le fichier.'));
  }
};

// Enregistre un fichier reçu du serveur (Blob) sur l'appareil de l'utilisateur
export const enregistrerBlob = (blob, nom) => {
  const url = URL.createObjectURL(blob);
  const lien = document.createElement('a');
  lien.href = url;
  lien.download = nom;
  document.body.appendChild(lien);
  lien.click();
  lien.remove();
  setTimeout(() => URL.revokeObjectURL(url), 60000);
};

// Nom de fichier proposé par le serveur (en-tête Content-Disposition), sinon `defaut`
export const nomFichierRecu = (res, defaut) => {
  const entete = (res.headers && (res.headers['content-disposition'] || res.headers.get?.('content-disposition'))) || '';
  const m = /filename="?([^";]+)"?/i.exec(entete);
  return m ? m[1] : defaut;
};

// En mode « blob », le message d'erreur JSON du serveur arrive lui aussi sous forme de Blob
export const messageErreurBlob = async (err, defaut) => {
  if (err.response?.data instanceof Blob) {
    try { err.response.data = JSON.parse(await err.response.data.text()); } catch (e) { /* ignoré */ }
  }
  return formatApiError(err, defaut);
};

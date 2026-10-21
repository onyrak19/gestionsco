// Transforme une erreur axios / Django REST framework en message lisible.
// Ex : {"date_fin": ["La date de fin doit ..."]} -> "date_fin : La date de fin doit ..."
const aplatir = (valeur) => {
  if (Array.isArray(valeur)) return valeur.map(aplatir).join(' ');
  if (valeur && typeof valeur === 'object') {
    return Object.entries(valeur)
      .map(([cle, v]) => (['non_field_errors', 'detail', 'error'].includes(cle)
        ? aplatir(v)
        : `${cle} : ${aplatir(v)}`))
      .join(' — ');
  }
  return String(valeur);
};

export const formatApiError = (err, defaut = 'Une erreur est survenue.') => {
  if (!err) return defaut;
  if (!err.response) return 'Impossible de joindre le serveur. Vérifiez que le backend est démarré.';
  const data = err.response.data;
  if (!data || typeof data === 'string') {
    if (err.response.status >= 500) return 'Erreur du serveur. Réessayez plus tard.';
    return defaut;
  }
  const message = aplatir(data);
  return message || defaut;
};

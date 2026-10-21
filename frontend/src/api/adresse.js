const HOTES_LOCAUX = ['localhost', '127.0.0.1', '::1', '[::1]'];

// Adresse de l'API. Doit fonctionner depuis n'importe quel appareil du réseau Wi-Fi :
// « 127.0.0.1 » désigne l'appareil lui-même, pas le PC qui héberge l'application.
//  - REACT_APP_API_URL (si défini) est respecté, sauf s'il pointe vers ce PC alors que la
//    page est ouverte depuis un autre appareil : on remplace alors par l'adresse de la page ;
//  - serveur de développement React (port 3000) : l'API est sur le même PC, port 8000 ;
//  - interface servie par Django : même adresse, chemin /api.
export const calculerApiUrl = (configuree, lieu) => {
  const { protocol, hostname, port } = lieu;
  if (configuree) {
    try {
      const url = new URL(configuree);
      if (HOTES_LOCAUX.includes(url.hostname) && !HOTES_LOCAUX.includes(hostname)) {
        url.hostname = hostname;
      }
      return url.toString().replace(/\/$/, '');
    } catch (e) {
      return configuree.replace(/\/$/, '');   // adresse relative (ex. /api)
    }
  }
  if (port === '3000') return `${protocol}//${hostname}:8000/api`;
  return '/api';
};

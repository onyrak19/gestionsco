import { calculerApiUrl } from './adresse';

const lieu = (hostname, port = '', protocol = 'http:') => ({ protocol, hostname, port });

describe("adresse de l'API (accès depuis le réseau Wi-Fi)", () => {
  test('serveur de développement React : l’API est sur le même PC, port 8000', () => {
    expect(calculerApiUrl(undefined, lieu('192.168.1.20', '3000'))).toBe('http://192.168.1.20:8000/api');
    expect(calculerApiUrl(undefined, lieu('localhost', '3000'))).toBe('http://localhost:8000/api');
  });

  test('interface servie par Django : même adresse, chemin /api', () => {
    expect(calculerApiUrl(undefined, lieu('192.168.1.20', '8000'))).toBe('/api');
  });

  test('une adresse « 127.0.0.1 » configurée est remplacée quand la page vient d’un autre appareil', () => {
    expect(calculerApiUrl('http://127.0.0.1:8000/api', lieu('192.168.1.20', '3000'))).toBe('http://192.168.1.20:8000/api');
    expect(calculerApiUrl('http://localhost:8000/api/', lieu('pc-ecole', '8000'))).toBe('http://pc-ecole:8000/api');
  });

  test('une adresse configurée est respectée sur le PC lui-même ou si elle est distante', () => {
    expect(calculerApiUrl('http://127.0.0.1:8000/api', lieu('localhost', '3000'))).toBe('http://127.0.0.1:8000/api');
    expect(calculerApiUrl('https://api.ecole.org/api', lieu('192.168.1.20', '3000', 'https:'))).toBe('https://api.ecole.org/api');
    expect(calculerApiUrl('/api', lieu('192.168.1.20', '8000'))).toBe('/api');
  });
});

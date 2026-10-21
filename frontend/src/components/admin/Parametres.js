import React, { useEffect, useState } from 'react';
import api from '../../api/axios';
import { formatApiError } from '../../utils/errors';

const CHAMPS = [
  ['nom', "Nom de l'établissement", 'text'],
  ['directeur', 'Directeur / Directrice', 'text'],
  ['adresse', 'Adresse', 'text'],
  ['ville', 'Ville (pour « Fait à … »)', 'text'],
  ['telephone', 'Téléphone', 'text'],
  ['email', 'Email', 'email'],
];

const Parametres = () => {
  const [form, setForm] = useState(null);
  const [erreur, setErreur] = useState('');
  const [message, setMessage] = useState('');

  useEffect(() => {
    api.get('/school/etablissement/').then(r => setForm(r.data))
      .catch(err => setErreur(formatApiError(err)));
  }, []);

  const enregistrer = async (e) => {
    e.preventDefault();
    setErreur(''); setMessage('');
    try {
      const res = await api.put('/school/etablissement/', form);
      setForm(res.data);
      setMessage('Informations enregistrées : elles apparaissent sur les cartes, bulletins et certificats.');
    } catch (err) { setErreur(formatApiError(err)); }
  };

  return (
    <div className="page">
      <h1>Établissement</h1>
      <p className="page-subtitle">Ces informations figurent en en-tête des cartes d'élève, bulletins, certificats et fiches d'appel.</p>
      {erreur && <div className="error">{erreur}</div>}
      {message && <div className="success">{message}</div>}
      {form && (
        <div className="card">
          <form onSubmit={enregistrer}>
            <div className="form-row">
              {CHAMPS.map(([cle, libelle, type]) => (
                <div className="form-group" key={cle} style={{ flexBasis: 280 }}>
                  <label htmlFor={`etab-${cle}`}>{libelle}</label>
                  <input id={`etab-${cle}`} type={type} value={form[cle] || ''} required={cle === 'nom'}
                    onChange={(e) => setForm({ ...form, [cle]: e.target.value })} />
                </div>
              ))}
            </div>
            <button className="btn-primary" type="submit">Enregistrer</button>
          </form>
        </div>
      )}
    </div>
  );
};

export default Parametres;

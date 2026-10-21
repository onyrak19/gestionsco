import React, { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import api from '../../api/axios';
import { formatApiError } from '../../utils/errors';

const ClasseConfig = () => {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [lignes, setLignes] = useState([]);
  const [erreur, setErreur] = useState('');
  const [message, setMessage] = useState('');
  const [nouvelle, setNouvelle] = useState('');
  const [modifie, setModifie] = useState(false);

  const charger = useCallback(() => {
    return api.get('/school/config-matieres/', { params: { classe: id } }).then(r => {
      setData(r.data);
      setLignes(r.data.matieres.map(m => ({ ...m })));
      setModifie(r.data.propose);   // une proposition reprise de l'an dernier reste à valider
    }).catch(err => setErreur(formatApiError(err)));
  }, [id]);
  useEffect(() => { charger(); }, [charger]);

  const maj = (matiere, champs) => {
    setLignes(ls => ls.map(l => (l.matiere === matiere ? { ...l, ...champs } : l)));
    setModifie(true); setMessage('');
  };
  const toutCocher = (valeur) => { setLignes(ls => ls.map(l => ({ ...l, enseignee: valeur }))); setModifie(true); };

  const enregistrer = async () => {
    setErreur(''); setMessage('');
    try {
      const res = await api.put('/school/config-matieres/', {
        classe: Number(id),
        matieres: lignes.filter(l => l.enseignee)
          .map(l => ({ matiere: l.matiere, coefficient: Number(l.coefficient) || 1 })),
      });
      setData(res.data);
      setLignes(res.data.matieres.map(m => ({ ...m })));
      setModifie(false);
      setMessage(`Configuration enregistrée pour ${res.data.classes.length} classe(s).`);
    } catch (err) { setErreur(formatApiError(err)); }
  };

  const ajouterMatiere = async (e) => {
    e.preventDefault();
    if (!nouvelle.trim()) return;
    setErreur('');
    try {
      const res = await api.post('/school/matieres/', { nom: nouvelle.trim(), coefficient: 1 });
      setNouvelle('');
      setLignes(ls => [...ls, { matiere: res.data.id, nom: res.data.nom, code: res.data.code, enseignee: true, coefficient: 1 }]
        .sort((a, b) => a.nom.localeCompare(b.nom)));
      setModifie(true);
    } catch (err) { setErreur(formatApiError(err)); }
  };

  if (!data) {
    return <div className="page"><h1>Configuration</h1>{erreur ? <div className="error">{erreur}</div> : <p className="loading">Chargement…</p>}
      <Link className="btn-secondary" to="/admin/classes">← Retour aux classes</Link></div>;
  }

  const titre = data.serie ? `${data.niveau} — série ${data.serie}` : data.niveau;
  const lecture = data.annee_cloturee;
  const nbActives = lignes.filter(l => l.enseignee).length;

  return (
    <div className="page">
      <p><Link to="/admin/classes">← Classes</Link></p>
      <h1>Matières et coefficients — {titre}</h1>
      <p className="page-subtitle">Année scolaire {data.annee}</p>
      {erreur && <div className="error">{erreur}</div>}
      {message && <div className="success">{message}</div>}

      <div className="info">
        Cette configuration s'applique à <strong>toutes les classes {data.serie ? `de ${data.niveau} série ${data.serie}` : `de ${data.niveau}`}</strong> :{' '}
        {data.classes.map(c => c.nom).join(', ')}.
        {data.niveau && ['Première', 'Terminale'].includes(data.niveau) &&
          ' Chaque série se configure séparément (les coefficients peuvent différer entre L, S et OSE).'}
      </div>
      {data.propose && (
        <div className="alerte info">Aucune configuration pour cette année : celle de l'année précédente est proposée. Vérifiez-la puis enregistrez.</div>
      )}
      {!data.configuree && !data.propose && (
        <div className="alerte info">Classe non configurée : toutes les matières comptent avec leur coefficient par défaut. Cochez les matières enseignées et fixez leurs coefficients.</div>
      )}
      {lecture && <div className="alerte info">Année clôturée : la configuration ne peut plus être modifiée.</div>}

      <div className="card">
        <div className="card-titre">
          <h3>{nbActives} matière{nbActives > 1 ? 's' : ''} enseignée{nbActives > 1 ? 's' : ''}</h3>
          {!lecture && (
            <div className="actions-ligne">
              <button type="button" className="btn-small" onClick={() => toutCocher(true)}>Tout cocher</button>
              <button type="button" className="btn-small" onClick={() => toutCocher(false)}>Tout décocher</button>
            </div>
          )}
        </div>

        <div className="matiere-config muted"><span /><span>Matière</span><span>Coefficient</span></div>
        {lignes.map(l => (
          <div key={l.matiere} className={`matiere-config ${l.enseignee ? '' : 'desactivee'}`}>
            <input type="checkbox" checked={l.enseignee} disabled={lecture} aria-label={`Enseigner ${l.nom}`}
              onChange={(e) => maj(l.matiere, { enseignee: e.target.checked })} />
            <span>{l.nom}</span>
            <input type="number" min="1" max="20" value={l.coefficient} disabled={lecture || !l.enseignee}
              aria-label={`Coefficient ${l.nom}`}
              onChange={(e) => maj(l.matiere, { coefficient: e.target.value })} />
          </div>
        ))}
        {lignes.length === 0 && <p className="muted">Aucune matière : créez-en une ci-dessous.</p>}

        {!lecture && (
          <>
            <form onSubmit={ajouterMatiere} className="form-row" style={{ marginTop: 18 }}>
              <div className="form-group">
                <label htmlFor="nouvelle-matiere">Ajouter une nouvelle matière</label>
                <input id="nouvelle-matiere" value={nouvelle} placeholder="ex. Informatique"
                  onChange={(e) => setNouvelle(e.target.value)} />
              </div>
              <div className="form-group"><button type="submit" className="btn-secondary">+ Ajouter</button></div>
            </form>
            <div className="actions-ligne">
              <button type="button" className="btn-primary" disabled={!modifie} onClick={enregistrer}>
                Enregistrer pour toutes les classes
              </button>
              {modifie && <span className="muted">Modifications non enregistrées</span>}
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default ClasseConfig;

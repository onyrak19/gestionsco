import React, { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import api from '../../api/axios';
import { formatApiError } from '../../utils/errors';
import { ouvrirPdf, lundiCourant } from '../../utils/pdf';
import DecisionBadge from '../ui/DecisionBadge';
import PrintBar from '../ui/PrintBar';
import ReleveClasse from './ReleveClasse';

const ClasseDetail = () => {
  const { id } = useParams();
  const [classe, setClasse] = useState(null);
  const [inscriptions, setInscriptions] = useState([]);
  const [ordre, setOrdre] = useState('alpha');
  const [onglet, setOnglet] = useState('eleves');
  const [selection, setSelection] = useState([]);
  const [semaine, setSemaine] = useState(lundiCourant());
  const [erreur, setErreur] = useState('');

  useEffect(() => {
    api.get(`/school/classes/${id}/`).then(r => setClasse(r.data))
      .catch(err => setErreur(formatApiError(err)));
  }, [id]);

  const charger = useCallback(() => {
    return api.get('/school/inscriptions/', { params: { classe: id, ordre } })
      .then(r => { setInscriptions(r.data); setSelection(s => s.filter(x => r.data.some(i => i.id === x))); })
      .catch(err => setErreur(formatApiError(err)));
  }, [id, ordre]);
  useEffect(() => { charger(); }, [charger]);

  const basculer = (iid) => setSelection(s => (s.includes(iid) ? s.filter(x => x !== iid) : [...s, iid]));
  const tout = inscriptions.length > 0 && selection.length === inscriptions.length;

  const desinscrire = async (ins) => {
    if (!window.confirm(`Désinscrire ${ins.eleve_details.nom} ${ins.eleve_details.prenom} de cette classe ? Ses notes de l'année seront supprimées.`)) return;
    setErreur('');
    try { await api.delete(`/school/inscriptions/${ins.id}/`); } catch (err) { setErreur(formatApiError(err)); }
    charger();
  };

  const ficheAppel = async () => {
    setErreur('');
    try { await ouvrirPdf('/school/pdf/fiches-appel/', { classes: [Number(id)], semaine, ordre }); }
    catch (e) { setErreur(e.message); }
  };

  if (!classe) {
    return <div className="page"><h1>Classe</h1>{erreur ? <div className="error">{erreur}</div> : <p className="loading">Chargement…</p>}</div>;
  }

  return (
    <div className="page">
      <p><Link to="/admin/classes">← Classes</Link></p>
      <h1>{classe.nom}</h1>
      <p className="page-subtitle">Année {classe.annee_scolaire_libelle} · {inscriptions.length} élève{inscriptions.length > 1 ? 's' : ''}</p>
      {erreur && <div className="error">{erreur}</div>}

      <div className="actions-ligne">
        {classe.niveau && <Link className="btn-secondary" to={`/admin/classes/${id}/config`}>Matières et coefficients</Link>}
        <Link className="btn-secondary" to={`/admin/notes?classe=${id}`}>Saisir les notes</Link>
      </div>

      <div className="onglets">
        <button type="button" className={`onglet ${onglet === 'eleves' ? 'actif' : ''}`} onClick={() => setOnglet('eleves')}>Élèves inscrits</button>
        <button type="button" className={`onglet ${onglet === 'notes' ? 'actif' : ''}`} onClick={() => setOnglet('notes')}>Notes de la classe</button>
      </div>

      {onglet === 'eleves' && (
        <div className="card">
          <div className="card-titre">
            <h3>Élèves inscrits</h3>
            <select value={ordre} onChange={(e) => setOrdre(e.target.value)} aria-label="Ordre d'affichage" style={{ width: 'auto' }}>
              <option value="alpha">Par ordre alphabétique</option>
              <option value="numero">Par numéro</option>
            </select>
          </div>

          <PrintBar ids={selection} ordre={ordre} onError={setErreur} />
          <div className="print-bar">
            <span className="print-bar-titre">Fiche d'appel de la semaine du</span>
            <input type="date" value={semaine} onChange={(e) => setSemaine(e.target.value)} style={{ width: 'auto' }} aria-label="Semaine" />
            <button type="button" className="btn-small" onClick={ficheAppel}>Imprimer la fiche d'appel</button>
          </div>

          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th><input type="checkbox" checked={tout} aria-label="Tout sélectionner"
                    onChange={() => setSelection(tout ? [] : inscriptions.map(i => i.id))} /></th>
                  <th className="centre">N°</th><th>Matricule</th><th>Nom</th><th>Prénom</th><th>Décision</th><th></th>
                </tr>
              </thead>
              <tbody>
                {inscriptions.map(i => (
                  <tr key={i.id}>
                    <td><input type="checkbox" checked={selection.includes(i.id)} onChange={() => basculer(i.id)}
                      aria-label={`Sélectionner ${i.eleve_details.nom}`} /></td>
                    <td className="centre">{i.numero}</td>
                    <td>{i.eleve_details.matricule}</td>
                    <td><Link to={`/admin/eleves/${i.eleve}`}>{i.eleve_details.nom}</Link></td>
                    <td>{i.eleve_details.prenom}</td>
                    <td><DecisionBadge decision={i.decision} /></td>
                    <td>
                      <Link className="btn-small" to={`/admin/eleves/${i.eleve}`}>Détails</Link>
                      <button className="btn-small btn-danger" onClick={() => desinscrire(i)}>Désinscrire</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {inscriptions.length === 0 && <p className="muted">Aucun élève inscrit dans cette classe. Inscrivez-les dans le menu « Inscriptions ».</p>}
          </div>
        </div>
      )}

      {onglet === 'notes' && <ReleveClasse classeId={id} />}
    </div>
  );
};

export default ClasseDetail;

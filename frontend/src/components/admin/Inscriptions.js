import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../../api/axios';
import { formatApiError } from '../../utils/errors';
import DecisionBadge from '../ui/DecisionBadge';
import PrintBar from '../ui/PrintBar';
import Icon from '../ui/Icon';
import PageHeader from '../ui/PageHeader';
import EmptyState from '../ui/EmptyState';
import FilePicker from '../ui/FilePicker';
import Avatar from '../ui/Avatar';

const Inscriptions = () => {
  const [items, setItems] = useState([]);
  const [eleves, setEleves] = useState([]);
  const [classes, setClasses] = useState([]);
  const [annees, setAnnees] = useState([]);
  const [anneeForm, setAnneeForm] = useState('');
  const [anneeFiltre, setAnneeFiltre] = useState('');
  const [classeFiltre, setClasseFiltre] = useState('');
  const [ordre, setOrdre] = useState('alpha');
  const [form, setForm] = useState({ eleve: '', classe: '' });
  const [pieces, setPieces] = useState([]);   // pièces jointes facultatives
  const [recherche, setRecherche] = useState('');
  const [selection, setSelection] = useState([]);
  const [error, setError] = useState('');
  const [succes, setSucces] = useState(null);

  const chargerReferentiel = useCallback(() => {
    return Promise.all([api.get('/school/eleves/'), api.get('/school/classes/'), api.get('/school/annees/')])
      .then(([e, c, a]) => { setEleves(e.data); setClasses(c.data); setAnnees(a.data); return a.data; })
      .catch(err => setError(formatApiError(err)));
  }, []);

  useEffect(() => {
    chargerReferentiel().then(a => {
      const active = a && a.find(x => x.active);
      if (active) { setAnneeForm(active.id); setAnneeFiltre(active.id); }   // année en cours sélectionnée automatiquement
    });
  }, [chargerReferentiel]);

  const charger = useCallback(() => {
    const params = { ordre };
    if (anneeFiltre) params.annee = anneeFiltre;
    if (classeFiltre) params.classe = classeFiltre;
    return api.get('/school/inscriptions/', { params }).then(r => {
      setItems(r.data);
      setSelection(s => s.filter(x => r.data.some(i => i.id === x)));
    }).catch(err => setError(formatApiError(err)));
  }, [anneeFiltre, classeFiltre, ordre]);
  useEffect(() => { charger(); }, [charger]);

  const anneeActive = annees.find(a => a.active);
  const classesForm = classes.filter(c => String(c.annee_scolaire) === String(anneeForm));
  const classesFiltre = anneeFiltre ? classes.filter(c => String(c.annee_scolaire) === String(anneeFiltre)) : classes;
  const elevesFiltres = eleves.filter(e => {
    const q = recherche.trim().toLowerCase();
    return !q || `${e.nom} ${e.prenom} ${e.matricule || ''}`.toLowerCase().includes(q);
  });

  const inscrire = async (e) => {
    e.preventDefault();
    setError(''); setSucces(null);
    try {
      let res;
      if (pieces.length) {
        const corps = new FormData();
        corps.append('eleve', form.eleve);
        corps.append('classe', form.classe);
        pieces.forEach((p) => { corps.append('fichiers', p.fichier); corps.append('libelles', p.libelle || ''); });
        res = await api.post('/school/inscriptions/', corps, { headers: { 'Content-Type': 'multipart/form-data' } });
      } else {
        res = await api.post('/school/inscriptions/', form);
      }
      setSucces(res.data);
      setPieces([]);
      setForm({ eleve: '', classe: form.classe });
      setRecherche('');
      charger();
      chargerReferentiel();
    } catch (err) { setError(formatApiError(err)); }
  };

  const supprimer = async (ins) => {
    if (!window.confirm('Supprimer cette inscription ? Les notes de cet élève pour cette année seront aussi supprimées.')) return;
    setError('');
    try { await api.delete(`/school/inscriptions/${ins.id}/`); } catch (err) { setError(formatApiError(err)); }
    charger();
    chargerReferentiel();
  };

  const basculer = (id) => setSelection(s => (s.includes(id) ? s.filter(x => x !== id) : [...s, id]));
  const tout = items.length > 0 && selection.length === items.length;

  return (
    <div className="page">
      <PageHeader titre="Inscriptions"
        sousTitre="Le matricule et le numéro dans la classe sont attribués automatiquement. Un élève ne peut être que dans une seule classe par année." />
      {error && <div className="error">{error}</div>}
      {succes && (
        <div className="success">
          <strong>{succes.eleve_details.nom} {succes.eleve_details.prenom}</strong> inscrit(e) en <strong>{succes.classe_details.nom}</strong> —
          n° <strong>{succes.numero}</strong> — matricule <strong>{succes.eleve_details.matricule}</strong>
          {succes.pieces_jointes && succes.pieces_jointes.length > 0 && (
            <> — {succes.pieces_jointes.length} pièce{succes.pieces_jointes.length > 1 ? 's' : ''} jointe{succes.pieces_jointes.length > 1 ? 's' : ''}</>
          )}
        </div>
      )}
      {!anneeActive && annees.length > 0 && (
        <div className="info alerte">Aucune année scolaire n'est active. Activez-en une dans « Années scolaires ».</div>
      )}

      <div className="card">
        <h3>Nouvelle inscription</h3>
        <form onSubmit={inscrire} className="crud-form">
          <div className="form-row">
            <div className="form-group"><label htmlFor="ins-annee">Année scolaire {anneeActive && String(anneeForm) === String(anneeActive.id) ? '(en cours)' : ''}</label>
              <select id="ins-annee" value={anneeForm} required
                onChange={(e) => { setAnneeForm(e.target.value); setForm({ ...form, classe: '' }); }}>
                <option value="">--</option>
                {annees.filter(a => !a.cloturee).map(a => <option key={a.id} value={a.id}>{a.libelle}{a.active ? ' (en cours)' : ''}</option>)}
              </select></div>
            <div className="form-group"><label htmlFor="ins-classe">Classe</label>
              <select id="ins-classe" value={form.classe} required onChange={(e) => setForm({ ...form, classe: e.target.value })}>
                <option value="">-- Choisir --</option>
                {classesForm.map(c => <option key={c.id} value={c.id}>{c.nom} ({c.effectif ?? 0} élèves)</option>)}
              </select></div>
          </div>
          <div className="form-row">
            <div className="form-group"><label htmlFor="ins-recherche">Rechercher un élève</label>
              <input id="ins-recherche" value={recherche} placeholder="Nom, prénom ou matricule…"
                onChange={(e) => setRecherche(e.target.value)} /></div>
            <div className="form-group"><label htmlFor="ins-eleve">Élève</label>
              <select id="ins-eleve" value={form.eleve} required onChange={(e) => setForm({ ...form, eleve: e.target.value })}>
                <option value="">-- Choisir ({elevesFiltres.length}) --</option>
                {elevesFiltres.map(e => (
                  <option key={e.id} value={e.id}>
                    {e.nom} {e.prenom}{e.derniere_classe ? ` — dernière classe : ${e.derniere_classe} (${e.derniere_annee})` : ' — nouvel élève'}
                  </option>
                ))}
              </select></div>
          </div>
          <div className="form-group">
            <label>Pièces jointes <span className="muted">(facultatif)</span></label>
            <FilePicker items={pieces} onChange={setPieces} />
          </div>
          <div className="actions-ligne">
            <button className="btn-primary" type="submit"><Icon nom="inscription" taille={16} /> Inscrire</button>
            <Link to="/admin/eleves" className="btn-secondary"><Icon nom="plus" taille={16} /> Nouvel élève</Link>
          </div>
        </form>
      </div>

      <div className="card">
        <div className="card-titre">
          <h3>Inscriptions ({items.length})</h3>
          <div className="actions-ligne">
            <select value={anneeFiltre} onChange={(e) => { setAnneeFiltre(e.target.value); setClasseFiltre(''); }} aria-label="Année" style={{ width: 'auto' }}>
              <option value="">Toutes les années</option>
              {annees.map(a => <option key={a.id} value={a.id}>{a.libelle}</option>)}
            </select>
            <select value={classeFiltre} onChange={(e) => setClasseFiltre(e.target.value)} aria-label="Classe" style={{ width: 'auto' }}>
              <option value="">Toutes les classes</option>
              {classesFiltre.map(c => <option key={c.id} value={c.id}>{c.nom}</option>)}
            </select>
            <select value={ordre} onChange={(e) => setOrdre(e.target.value)} aria-label="Ordre" style={{ width: 'auto' }}>
              <option value="alpha">Ordre alphabétique</option>
              <option value="numero">Par numéro</option>
            </select>
          </div>
        </div>

        <PrintBar ids={selection} ordre={ordre} onError={setError} />

        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th><input type="checkbox" checked={tout} aria-label="Tout sélectionner"
                  onChange={() => setSelection(tout ? [] : items.map(i => i.id))} /></th>
                <th className="centre">N°</th><th>Matricule</th><th>Élève</th><th>Classe</th><th>Année</th><th>Décision</th><th></th>
              </tr>
            </thead>
            <tbody>
              {items.map(i => (
                <tr key={i.id}>
                  <td><input type="checkbox" checked={selection.includes(i.id)} onChange={() => basculer(i.id)}
                    aria-label={`Sélectionner ${i.eleve_details.nom}`} /></td>
                  <td className="centre">{i.numero}</td>
                  <td>{i.eleve_details.matricule}</td>
                  <td>
                    <div className="cellule-eleve">
                      <Avatar eleve={i.eleve_details} taille="s" />
                      <Link to={`/admin/eleves/${i.eleve}`}>{i.eleve_details.nom} {i.eleve_details.prenom}</Link>
                      {i.pieces_jointes && i.pieces_jointes.length > 0 && (
                        <span className="badge badge-piece" title={`${i.pieces_jointes.length} pièce(s) jointe(s)`}>
                          <Icon nom="trombone" taille={12} /> {i.pieces_jointes.length}
                        </span>
                      )}
                    </div>
                  </td>
                  <td>{i.classe_details.nom}</td>
                  <td>{i.classe_details.annee_scolaire_libelle}</td>
                  <td><DecisionBadge decision={i.decision} /></td>
                  <td><button className="btn-small btn-danger" onClick={() => supprimer(i)}>Supprimer</button></td>
                </tr>
              ))}
            </tbody>
          </table>
          {items.length === 0 && (
            <EmptyState icone="inscription" titre="Aucune inscription">
              Choisissez une classe et un élève dans le formulaire ci-dessus.
            </EmptyState>
          )}
        </div>
      </div>
    </div>
  );
};

export default Inscriptions;

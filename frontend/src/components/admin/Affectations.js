import React, { useCallback, useEffect, useMemo, useState } from 'react';
import api from '../../api/axios';
import { formatApiError } from '../../utils/errors';
import Icon from '../ui/Icon';
import PageHeader from '../ui/PageHeader';
import EmptyState from '../ui/EmptyState';

const nomDe = (a) => a.enseignant_nom || a.enseignant_username;

// Règle : une matière n'a qu'UN SEUL enseignant dans une classe.
const Affectations = () => {
  const [items, setItems] = useState([]);
  const [enseignants, setEnseignants] = useState([]);
  const [matieres, setMatieres] = useState([]);
  const [matieresClasse, setMatieresClasse] = useState(null);   // matières enseignées dans la classe choisie
  const [classes, setClasses] = useState([]);
  const [annees, setAnnees] = useState([]);
  const [anneeForm, setAnneeForm] = useState('');
  const [anneeFiltre, setAnneeFiltre] = useState('');
  const [form, setForm] = useState({ classe: '', matiere: '', enseignant: '' });
  const [edition, setEdition] = useState(null);   // { id, enseignant } : changement d'enseignant en cours
  const [error, setError] = useState('');
  const [succes, setSucces] = useState('');

  useEffect(() => {
    Promise.all([
      api.get('/auth/enseignants/', { params: { statut: 'valide' } }),
      api.get('/school/matieres/'),
      api.get('/school/classes/'),
      api.get('/school/annees/'),
    ]).then(([e, m, c, a]) => {
      setEnseignants(e.data); setMatieres(m.data); setClasses(c.data); setAnnees(a.data);
      const active = a.data.find((x) => x.active);
      if (active) { setAnneeForm(active.id); setAnneeFiltre(active.id); }   // année en cours automatique
    }).catch((err) => setError(formatApiError(err)));
  }, []);

  const load = useCallback(() => {
    const params = anneeFiltre ? { annee: anneeFiltre } : {};
    return api.get('/school/affectations/', { params }).then((r) => setItems(r.data))
      .catch((err) => setError(formatApiError(err)));
  }, [anneeFiltre]);
  useEffect(() => { load(); }, [load]);

  // Quand on choisit une classe, on ne propose que les matières qui y sont enseignées
  useEffect(() => {
    if (!form.classe) { setMatieresClasse(null); return; }
    api.get('/school/config-matieres/', { params: { classe: form.classe } })
      .then((r) => setMatieresClasse(r.data.configuree ? r.data.matieres.filter((m) => m.enseignee).map((m) => m.matiere) : null))
      .catch(() => setMatieresClasse(null));
  }, [form.classe]);

  const classesForm = classes.filter((c) => String(c.annee_scolaire) === String(anneeForm));
  const matieresProposees = matieresClasse ? matieres.filter((m) => matieresClasse.includes(m.id)) : matieres;

  // Qui enseigne déjà cette matière dans cette classe ?
  const titulaire = useMemo(() => items.find(
    (a) => String(a.classe) === String(form.classe) && String(a.matiere) === String(form.matiere),
  ), [items, form.classe, form.matiere]);
  const choisi = enseignants.find((u) => String(u.id) === String(form.enseignant));

  const valider = async (e) => {
    e.preventDefault();
    setError(''); setSucces('');
    try {
      if (titulaire) {
        await api.patch(`/school/affectations/${titulaire.id}/`, { enseignant: form.enseignant });
        setSucces(`${titulaire.matiere_nom} (${titulaire.classe_nom}) est maintenant confiée à ${choisi.nom} ${choisi.prenom}.`);
      } else {
        await api.post('/school/affectations/', { enseignant: form.enseignant, classe: form.classe, matiere: form.matiere });
        setSucces('Affectation enregistrée.');
      }
      setForm({ ...form, matiere: '', enseignant: '' });
    } catch (err) { setError(formatApiError(err)); }
    load();
  };

  const changer = async (e) => {
    e.preventDefault();
    setError(''); setSucces('');
    try {
      await api.patch(`/school/affectations/${edition.id}/`, { enseignant: edition.enseignant });
      setSucces("L'enseignant a été changé.");
      setEdition(null);
    } catch (err) { setError(formatApiError(err)); }
    load();
  };

  const supprimer = async (id) => {
    if (!window.confirm('Retirer cet enseignant de cette matière ?')) return;
    setError(''); setSucces('');
    try { await api.delete(`/school/affectations/${id}/`); } catch (err) { setError(formatApiError(err)); }
    load();
  };

  // classe -> matière -> affectations (plusieurs seulement pour d'anciennes données à corriger)
  const groupes = useMemo(() => {
    const parClasse = new Map();
    items.forEach((a) => {
      if (!parClasse.has(a.classe_nom)) parClasse.set(a.classe_nom, new Map());
      const parMatiere = parClasse.get(a.classe_nom);
      if (!parMatiere.has(a.matiere_nom)) parMatiere.set(a.matiere_nom, []);
      parMatiere.get(a.matiere_nom).push(a);
    });
    return Array.from(parClasse.entries());
  }, [items]);
  const nbDoublons = groupes.reduce((t, [, m]) => t + Array.from(m.values()).filter((v) => v.length > 1).length, 0);

  const active = annees.find((a) => a.active);

  return (
    <div className="page">
      <PageHeader
        titre="Affectations"
        sousTitre="Chaque matière a un seul enseignant par classe. Les affectations sont à refaire chaque année."
      />
      {error && <div className="error">{error}</div>}
      {succes && <div className="success">{succes}</div>}
      {nbDoublons > 0 && (
        <div className="alerte">
          <strong>À corriger :</strong> {nbDoublons} matière{nbDoublons > 1 ? 's ont' : ' a'} plusieurs enseignants dans la
          même classe (ancienne saisie). Retirez les enseignants en trop dans la liste ci-dessous.
        </div>
      )}

      <div className="card">
        <h3>Nouvelle affectation</h3>
        <form onSubmit={valider} className="crud-form">
          <div className="form-row">
            <div className="form-group"><label htmlFor="af-annee">Année {active && String(anneeForm) === String(active.id) ? '(en cours)' : ''}</label>
              <select id="af-annee" value={anneeForm} required
                onChange={(e) => { setAnneeForm(e.target.value); setForm({ classe: '', matiere: '', enseignant: '' }); }}>
                <option value="">--</option>
                {annees.filter((a) => !a.cloturee).map((a) => <option key={a.id} value={a.id}>{a.libelle}{a.active ? ' (en cours)' : ''}</option>)}
              </select></div>
            <div className="form-group"><label htmlFor="af-classe">Classe</label>
              <select id="af-classe" value={form.classe} required onChange={(e) => setForm({ classe: e.target.value, matiere: '', enseignant: '' })}>
                <option value="">--</option>
                {classesForm.map((c) => <option key={c.id} value={c.id}>{c.nom}</option>)}
              </select></div>
            <div className="form-group"><label htmlFor="af-matiere">Matière</label>
              <select id="af-matiere" value={form.matiere} required onChange={(e) => setForm({ ...form, matiere: e.target.value, enseignant: '' })}>
                <option value="">--</option>
                {matieresProposees.map((m) => <option key={m.id} value={m.id}>{m.nom}</option>)}
              </select></div>
            <div className="form-group"><label htmlFor="af-ens">Enseignant</label>
              <select id="af-ens" value={form.enseignant} required disabled={!form.matiere}
                onChange={(e) => setForm({ ...form, enseignant: e.target.value })}>
                <option value="">--</option>
                {enseignants.filter((u) => !titulaire || u.id !== titulaire.enseignant)
                  .map((u) => <option key={u.id} value={u.id}>{u.nom} {u.prenom} ({u.username})</option>)}
              </select></div>
          </div>
          {matieresClasse && <p className="muted">Seules les matières configurées pour cette classe sont proposées.</p>}
          {titulaire && (
            <div className="info">
              {titulaire.matiere_nom} est déjà confiée à <strong>{nomDe(titulaire)}</strong> en {titulaire.classe_nom}.
              Choisissez un autre enseignant pour le <strong>remplacer</strong>.
            </div>
          )}
          <button className="btn-primary" type="submit" disabled={!form.enseignant || !form.classe || !form.matiere}>
            <Icon nom="lien" taille={16} /> {titulaire ? `Remplacer ${nomDe(titulaire)}` : 'Affecter'}
          </button>
        </form>
      </div>

      <div className="card">
        <div className="card-titre">
          <h3>Liste ({items.length})</h3>
          <select value={anneeFiltre} onChange={(e) => setAnneeFiltre(e.target.value)} aria-label="Année" style={{ width: 'auto' }}>
            <option value="">Toutes les années</option>
            {annees.map((a) => <option key={a.id} value={a.id}>{a.libelle}</option>)}
          </select>
        </div>
        {groupes.length === 0 ? (
          <EmptyState icone="lien" titre="Aucune affectation pour cette année">
            Choisissez une classe, une matière et un enseignant ci-dessus.
          </EmptyState>
        ) : groupes.map(([classe, parMatiere]) => (
          <div key={classe} className="groupe-affectation">
            <h4>{classe}</h4>
            <div className="table-wrap">
              <table className="data-table">
                <tbody>
                  {Array.from(parMatiere.entries()).map(([matiere, affs]) => (
                    <tr key={matiere}>
                      <td className="col-matiere-aff"><strong>{matiere}</strong></td>
                      <td>
                        {affs.map((a) => (
                          <div key={a.id} className="aff-enseignant">
                            {edition && edition.id === a.id ? (
                              <form className="aff-changer" onSubmit={changer}>
                                <select aria-label={`Nouvel enseignant pour ${matiere} (${classe})`} value={edition.enseignant} required autoFocus
                                  onChange={(e) => setEdition({ ...edition, enseignant: e.target.value })}>
                                  <option value="">Choisir…</option>
                                  {enseignants.filter((u) => u.id !== a.enseignant)
                                    .map((u) => <option key={u.id} value={u.id}>{u.nom} {u.prenom} ({u.username})</option>)}
                                </select>
                                <button type="submit" className="btn-primary btn-compact" disabled={!edition.enseignant}>Valider</button>
                                <button type="button" className="btn-secondary btn-compact" onClick={() => setEdition(null)}>Annuler</button>
                              </form>
                            ) : (
                              <>
                                <span className="nom">{nomDe(a)}</span>
                                {affs.length > 1 && <span className="badge badge-alerte">à corriger</span>}
                                <button type="button" className="btn-small btn-secondary" aria-label={`Changer d'enseignant pour ${matiere} (${classe})`}
                                  onClick={() => setEdition({ id: a.id, enseignant: '' })}>
                                  <Icon nom="actualiser" taille={13} /> Changer d'enseignant
                                </button>
                                <button type="button" className="btn-small btn-danger"
                                  aria-label={`Retirer ${nomDe(a)} de ${matiere} (${classe})`} onClick={() => supprimer(a.id)}>
                                  <Icon nom="corbeille" taille={13} /> Retirer
                                </button>
                              </>
                            )}
                          </div>
                        ))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default Affectations;

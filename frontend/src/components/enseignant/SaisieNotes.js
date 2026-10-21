import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import api from '../../api/axios';
import { useAuth } from '../../context/AuthContext';
import { formatApiError } from '../../utils/errors';
import { calculerMoyennes, formatNote } from '../../utils/notes';
import { classeNote, TRIMESTRES } from '../../utils/labels';
import PageHeader from '../ui/PageHeader';
import Segmented from '../ui/Segmented';
import Icon from '../ui/Icon';
import EmptyState from '../ui/EmptyState';
import Avatar from '../ui/Avatar';
import SaisiePasAPas from './SaisiePasAPas';

const CHAMPS = ['j1', 'j2', 'j3', 'examen'];

// Saisie des notes. Un enseignant ne voit que ses (classe, matière) ;
// l'administrateur peut choisir n'importe quelle année, classe et matière.
const SaisieNotes = () => {
  const { isAdmin } = useAuth();
  const admin = isAdmin();
  const [params] = useSearchParams();

  // --- Choix enseignant
  const [affectations, setAffectations] = useState([]);
  const [affectation, setAffectation] = useState(null);

  // --- Choix administrateur
  const [annees, setAnnees] = useState([]);
  const [annee, setAnnee] = useState('');
  const [classes, setClasses] = useState([]);
  const [classeId, setClasseId] = useState('');
  const [matieres, setMatieres] = useState([]);
  const [matiereId, setMatiereId] = useState('');

  const [trimestre, setTrimestre] = useState(1);
  const [eleves, setEleves] = useState([]);
  const [notes, setNotes] = useState({});
  const [statuts, setStatuts] = useState({});
  const [loading, setLoading] = useState(false);
  const [erreur, setErreur] = useState('');
  const [initialise, setInitialise] = useState(false);
  const [mode, setMode] = useState('tableau');     // 'tableau' (vue habituelle) ou 'pas' (saisie élève par élève)
  const [bilan, setBilan] = useState('');

  useEffect(() => {
    if (admin) {
      const preselection = params.get('classe');
      Promise.all([
        api.get('/school/annees/'),
        preselection ? api.get(`/school/classes/${preselection}/`) : Promise.resolve(null),
      ]).then(([a, c]) => {
        setAnnees(a.data);
        if (c) { setAnnee(c.data.annee_scolaire); setClasseId(String(c.data.id)); }
        else {
          const active = a.data.find(x => x.active) || a.data[0];
          if (active) setAnnee(active.id);
        }
      }).catch(err => setErreur(formatApiError(err))).finally(() => setInitialise(true));
    } else {
      api.get('/school/affectations/mes/').then(r => {
        setAffectations(r.data);
        if (r.data.length > 0) setAffectation(r.data[0]);
      }).catch(err => setErreur(formatApiError(err))).finally(() => setInitialise(true));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [admin]);

  // Admin : classes de l'année choisie
  useEffect(() => {
    if (!admin || !annee) return;
    api.get('/school/classes/', { params: { annee } }).then(r => {
      setClasses(r.data);
      setClasseId(c => (r.data.some(x => String(x.id) === String(c)) ? c : ''));
    }).catch(err => setErreur(formatApiError(err)));
  }, [admin, annee]);

  // Admin : matières enseignées dans la classe choisie (toutes si non configurée)
  useEffect(() => {
    if (!admin) return;
    if (!classeId) { setMatieres([]); setMatiereId(''); return; }
    Promise.all([
      api.get('/school/matieres/'),
      api.get('/school/config-matieres/', { params: { classe: classeId } }).catch(() => null),
    ]).then(([m, cfg]) => {
      const liste = cfg && cfg.data.configuree
        ? m.data.filter(x => cfg.data.matieres.some(y => y.matiere === x.id && y.enseignee))
        : m.data;
      setMatieres(liste);
      setMatiereId(liste.length ? String(liste[0].id) : '');
    }).catch(err => setErreur(formatApiError(err)));
  }, [admin, classeId]);

  const selected = admin
    ? (classeId && matiereId ? { classe: Number(classeId), matiere: Number(matiereId) } : null)
    : affectation;

  useEffect(() => {
    if (!selected) { setEleves([]); setNotes({}); return; }
    setLoading(true);
    setErreur('');
    setStatuts({});
    setMode('tableau');
    setBilan('');
    Promise.all([
      api.get('/school/inscriptions/', { params: { classe: selected.classe, ordre: 'numero' } }),
      api.get('/school/notes/', { params: { classe: selected.classe, matiere: selected.matiere, trimestre } }),
    ]).then(([insRes, notesRes]) => {
      setEleves(insRes.data);
      const map = {};
      notesRes.data.forEach(n => { map[n.inscription] = n; });
      setNotes(map);
    }).catch(err => setErreur(formatApiError(err)))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected?.classe, selected?.matiere, trimestre]);

  const updateNote = (inscriptionId, field, value) => {
    setNotes(prev => ({ ...prev, [inscriptionId]: { ...(prev[inscriptionId] || {}), [field]: value } }));
    setStatuts(prev => ({ ...prev, [inscriptionId]: { type: 'modifie', message: 'Non enregistré' } }));
  };

  const saveNote = async (inscriptionId) => {
    const n = notes[inscriptionId] || {};
    setStatuts(prev => ({ ...prev, [inscriptionId]: { type: 'attente', message: 'Enregistrement...' } }));
    try {
      const res = await api.post('/school/notes/upsert/', {
        inscription: inscriptionId, matiere: selected.matiere, trimestre,
        // une case vide efface la note ; 0 est conservé
        j1: n.j1 ?? null, j2: n.j2 ?? null, j3: n.j3 ?? null, examen: n.examen ?? null,
      });
      setNotes(prev => ({ ...prev, [inscriptionId]: res.data }));
      setStatuts(prev => ({ ...prev, [inscriptionId]: { type: 'ok', message: '✓ Enregistré' } }));
      return true;
    } catch (err) {
      setStatuts(prev => ({ ...prev, [inscriptionId]: { type: 'erreur', message: formatApiError(err) } }));
      return false;
    }
  };

  const enregistrerTout = async () => {
    for (const ins of eleves) {
      if (statuts[ins.id]?.type === 'modifie') await saveNote(ins.id);   // eslint-disable-line no-await-in-loop
    }
  };
  const nbModifies = Object.values(statuts).filter(s => s.type === 'modifie').length;

  if (!admin && initialise && affectations.length === 0) {
    return (
      <div className="page">
        <PageHeader titre="Saisie des notes" />
        {erreur && <div className="error">{erreur}</div>}
        <div className="card">
          <EmptyState icone="lien" titre="Aucune affectation pour l'année en cours">
            Contactez l'administration : elle doit vous affecter à une classe et à une matière.
          </EmptyState>
        </div>
      </div>
    );
  }

  const contexte = {
    classe: admin ? (classes.find((c) => String(c.id) === String(classeId))?.nom || '') : (affectation?.classe_nom || ''),
    matiere: admin ? (matieres.find((m) => String(m.id) === String(matiereId))?.nom || '') : (affectation?.matiere_nom || ''),
    trimestre: TRIMESTRES.find((t) => t.value === trimestre)?.label || '',
  };

  return (
    <div className="page">
      {mode === 'tableau' && (
        <PageHeader titre="Saisie des notes"
          sousTitre={admin
            ? 'Mode administrateur : vous pouvez saisir et consulter les notes de toutes les classes.'
            : 'Choisissez votre classe et la période, puis saisissez dans le tableau ou élève par élève.'} />
      )}
      {erreur && <div className="error">{erreur}</div>}
      {bilan && <div className="success">{bilan}</div>}

      {mode === 'tableau' && (
      <div className="card">
        <div className="form-row">
          {admin ? (
            <>
              <div className="form-group"><label htmlFor="sn-annee">Année</label>
                <select id="sn-annee" value={annee} onChange={(e) => setAnnee(e.target.value)}>
                  {annees.map(a => <option key={a.id} value={a.id}>{a.libelle}{a.active ? ' (en cours)' : ''}</option>)}
                </select></div>
              <div className="form-group"><label htmlFor="sn-classe">Classe</label>
                <select id="sn-classe" value={classeId} onChange={(e) => setClasseId(e.target.value)}>
                  <option value="">-- Choisir une classe --</option>
                  {classes.map(c => <option key={c.id} value={c.id}>{c.nom}</option>)}
                </select></div>
              <div className="form-group"><label htmlFor="sn-matiere">Matière</label>
                <select id="sn-matiere" value={matiereId} onChange={(e) => setMatiereId(e.target.value)} disabled={!classeId}>
                  {matieres.map(m => <option key={m.id} value={m.id}>{m.nom}</option>)}
                </select></div>
            </>
          ) : (
            <div className="form-group">
              <label htmlFor="sn-aff">Classe / Matière</label>
              <select id="sn-aff" value={affectation ? `${affectation.classe}|${affectation.matiere}` : ''}
                onChange={(e) => {
                  const [classe, matiere] = e.target.value.split('|').map(Number);
                  setAffectation(affectations.find(a => a.classe === classe && a.matiere === matiere));
                }}>
                {affectations.map(a => (
                  <option key={`${a.classe}|${a.matiere}`} value={`${a.classe}|${a.matiere}`}>
                    {a.classe_nom} — {a.matiere_nom}
                  </option>
                ))}
              </select>
            </div>
          )}
          <div className="form-group">
            <label>Trimestre</label>
            <Segmented label="Trimestre" valeur={trimestre} onChange={setTrimestre}
              options={TRIMESTRES.map((t) => ({ value: t.value, label: t.label.replace(' trimestre', ' trim.') }))} />
          </div>
        </div>
      </div>
      )}

      {selected && mode === 'pas' && !loading && (
        <SaisiePasAPas
          eleves={eleves} notes={notes} statuts={statuts} contexte={contexte}
          onChange={updateNote} onSave={saveNote}
          onQuitter={() => setMode('tableau')}
          onTerminer={({ saisis, total }) => {
            setMode('tableau');
            setBilan(`Saisie terminée : ${saisis} élève${saisis > 1 ? 's' : ''} sur ${total} ${saisis > 1 ? 'ont' : 'a'} une note enregistrée.`);
          }}
        />
      )}

      {selected && mode === 'tableau' && (
        <div className="card">
          <div className="card-titre">
            <h3>{eleves.length} élève{eleves.length > 1 ? 's' : ''}</h3>
            <div className="actions-ligne">
              <button type="button" className="btn-primary" disabled={eleves.length === 0 || loading}
                onClick={() => { setBilan(''); setMode('pas'); }}>
                <Icon nom="lecture" taille={15} /> Commencer la saisie
              </button>
              <button type="button" className="btn-secondary" disabled={nbModifies === 0} onClick={enregistrerTout}>
                <Icon nom="valider" taille={15} /> Tout enregistrer{nbModifies > 0 ? ` (${nbModifies})` : ''}
              </button>
            </div>
          </div>
          <p className="muted aide-saisie">
            <strong>Vue tableau</strong> : saisissez directement dans les cases. Ou cliquez sur
            « Commencer la saisie » pour saisir élève par élève, du n° 1 au dernier, avec enregistrement automatique.
          </p>
          {loading ? <p className="loading">Chargement...</p> : (
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th className="centre">N°</th><th>Élève</th><th>J1</th><th>J2</th><th>J3</th><th>Examen</th>
                    <th className="centre">Moy. journ.</th><th className="centre">Moy. matière</th><th></th><th></th>
                  </tr>
                </thead>
                <tbody>
                  {eleves.map((ins) => {
                    const n = notes[ins.id] || {};
                    const { moyenneJournaliere, moyenneMatiere } = calculerMoyennes(n);
                    const st = statuts[ins.id];
                    return (
                      <tr key={ins.id}>
                        <td className="centre">{ins.numero}</td>
                        <td>
                          <div className="cellule-eleve">
                            <Avatar eleve={ins.eleve_details} taille="s" />
                            <span>{ins.eleve_details?.nom} {ins.eleve_details?.prenom}</span>
                          </div>
                        </td>
                        {CHAMPS.map(f => (
                          <td key={f}>
                            <input type="number" step="0.01" min="0" max="20" value={n[f] ?? ''}
                              aria-label={`${f} ${ins.eleve_details?.nom}`}
                              onChange={(e) => updateNote(ins.id, f, e.target.value)} style={{ width: 78 }} />
                          </td>
                        ))}
                        <td className="centre">{formatNote(moyenneJournaliere)}</td>
                        <td className={`centre ${classeNote(moyenneMatiere)}`}><strong>{formatNote(moyenneMatiere)}</strong></td>
                        <td><button className="btn-small btn-secondary" title="Enregistrer" aria-label={`Enregistrer ${ins.eleve_details?.nom}`} onClick={() => saveNote(ins.id)}><Icon nom="valider" taille={14} /></button></td>
                        <td className={st ? `statut-${st.type}` : ''}>{st?.message}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              {eleves.length === 0 && (
                <EmptyState icone="eleve" titre="Aucun élève inscrit dans cette classe">
                  Inscrivez d'abord les élèves pour pouvoir saisir leurs notes.
                </EmptyState>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default SaisieNotes;

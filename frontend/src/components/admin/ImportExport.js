import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import api from '../../api/axios';
import { formatApiError } from '../../utils/errors';
import { enregistrerBlob, formatTaille, messageErreurBlob, nomFichierRecu } from '../../utils/fichiers';
import PageHeader from '../ui/PageHeader';
import Segmented from '../ui/Segmented';
import Icon from '../ui/Icon';
import EmptyState from '../ui/EmptyState';

const aujourdhui = () => new Date().toISOString().slice(0, 10);

// ---------------------------------------------------------------------------
// EXPORT
// ---------------------------------------------------------------------------
const Export = () => {
  const [annees, setAnnees] = useState([]);
  const [annee, setAnnee] = useState('');
  const [classes, setClasses] = useState([]);
  const [classesChoisies, setClassesChoisies] = useState([]);
  const [trimestre, setTrimestre] = useState('');
  const [jeux, setJeux] = useState([]);                 // catalogue : [{cle, libelle, description, nombre, importable}]
  const [mode, setMode] = useState('tout');             // 'tout' | 'choix'
  const [choisis, setChoisis] = useState([]);
  const [erreur, setErreur] = useState('');
  const [succes, setSucces] = useState('');
  const [envoi, setEnvoi] = useState(false);

  useEffect(() => {
    api.get('/school/annees/').then((r) => setAnnees(r.data)).catch((e) => setErreur(formatApiError(e)));
  }, []);

  // Les classes proposées dépendent de l'année choisie
  useEffect(() => {
    setClassesChoisies([]);
    if (!annee) { setClasses([]); return; }
    api.get('/school/classes/', { params: { annee } }).then((r) => setClasses(r.data)).catch(() => setClasses([]));
  }, [annee]);

  const filtres = useMemo(() => {
    const f = {};
    if (annee) f.annee = annee;
    if (classesChoisies.length) f.classes = classesChoisies;
    if (trimestre) f.trimestre = Number(trimestre);
    return f;
  }, [annee, classesChoisies, trimestre]);

  // Le nombre de lignes de chaque jeu suit les filtres
  const charger = useCallback(() => {
    const params = {};
    if (filtres.annee) params.annee = filtres.annee;
    if (filtres.classes) params.classes = filtres.classes.join(',');
    if (filtres.trimestre) params.trimestre = filtres.trimestre;
    return api.get('/school/export/catalogue/', { params })
      .then((r) => setJeux(r.data.jeux))
      .catch((e) => setErreur(formatApiError(e)));
  }, [filtres]);
  useEffect(() => { charger(); }, [charger]);

  const cles = mode === 'tout' ? jeux.map((j) => j.cle) : choisis;
  const lignes = jeux.filter((j) => cles.includes(j.cle)).reduce((t, j) => t + j.nombre, 0);
  const basculer = (cle) => setChoisis((c) => (c.includes(cle) ? c.filter((x) => x !== cle) : [...c, cle]));
  const basculerClasse = (id) => setClassesChoisies((c) => (c.includes(id) ? c.filter((x) => x !== id) : [...c, id]));

  const exporter = async () => {
    setErreur(''); setSucces(''); setEnvoi(true);
    try {
      const corps = { jeux: mode === 'tout' ? 'tous' : choisis, ...filtres };
      const res = await api.post('/school/export/', corps, { responseType: 'blob' });
      const nom = nomFichierRecu(res, `export-gestion-scolaire-${aujourdhui()}.xlsx`);
      enregistrerBlob(new Blob([res.data], { type: res.data.type }), nom);
      setSucces(`Fichier « ${nom} » téléchargé : ${cles.length} feuille${cles.length > 1 ? 's' : ''}, ${lignes} ligne${lignes > 1 ? 's' : ''}.`);
    } catch (err) { setErreur(await messageErreurBlob(err, "L'export a échoué.")); }
    setEnvoi(false);
  };

  return (
    <>
      {erreur && <div className="error">{erreur}</div>}
      {succes && <div className="success">{succes}</div>}

      <div className="docs-choix" role="group" aria-label="Quoi exporter">
        <button type="button" className={`doc-tuile ${mode === 'tout' ? 'actif' : ''}`} aria-pressed={mode === 'tout'} onClick={() => setMode('tout')}>
          <span className="icone-doc"><Icon nom="tableur" taille={22} /></span>
          <strong>Toutes les données</strong>
          <span className="aide">Un classeur complet : une feuille par type de données</span>
        </button>
        <button type="button" className={`doc-tuile ${mode === 'choix' ? 'actif' : ''}`} aria-pressed={mode === 'choix'} onClick={() => setMode('choix')}>
          <span className="icone-doc"><Icon nom="valider" taille={22} /></span>
          <strong>Choisir les données</strong>
          <span className="aide">Seulement ce dont vous avez besoin (élèves, notes…)</span>
        </button>
      </div>

      {mode === 'choix' && (
        <div className="card">
          <div className="card-titre">
            <h3>Données à exporter ({choisis.length})</h3>
            <div className="actions-ligne">
              <button type="button" className="btn-secondary btn-compact" onClick={() => setChoisis(jeux.map((j) => j.cle))}>Tout cocher</button>
              <button type="button" className="btn-secondary btn-compact" onClick={() => setChoisis([])}>Tout décocher</button>
            </div>
          </div>
          <div className="jeux-grille" role="group" aria-label="Données à exporter">
            {jeux.map((j) => (
              <label key={j.cle} className={`jeu-carte ${choisis.includes(j.cle) ? 'cochee' : ''}`}>
                <input type="checkbox" checked={choisis.includes(j.cle)} onChange={() => basculer(j.cle)} />
                <strong>{j.libelle}</strong>
                <span className="aide">{j.description}</span>
                <span className="nombre">{j.nombre} ligne{j.nombre > 1 ? 's' : ''}</span>
              </label>
            ))}
          </div>
        </div>
      )}

      <div className="card">
        <h3>Filtres <span className="muted">(facultatif)</span></h3>
        <div className="form-row">
          <div className="form-group">
            <label htmlFor="ex-annee">Année scolaire</label>
            <select id="ex-annee" value={annee} onChange={(e) => setAnnee(e.target.value)}>
              <option value="">Toutes les années</option>
              {annees.map((a) => <option key={a.id} value={a.id}>{a.libelle}{a.active ? ' (en cours)' : ''}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label>Trimestre <span className="muted">(notes)</span></label>
            <Segmented label="Trimestre" valeur={trimestre} onChange={setTrimestre}
              options={[{ value: '', label: 'Tous' }, { value: 1, label: '1er' }, { value: 2, label: '2e' }, { value: 3, label: '3e' }]} />
          </div>
        </div>
        <div className="form-group">
          <label>Classes</label>
          {!annee ? (
            <p className="muted">Choisissez une année pour pouvoir limiter l'export à certaines classes (sinon, toutes les classes sont exportées).</p>
          ) : (
            <div className="grille-classes" role="group" aria-label="Classes à exporter">
              {classes.map((c) => (
                <label key={c.id} className={`tuile-classe ${classesChoisies.includes(c.id) ? 'cochee' : ''}`}>
                  <input type="checkbox" checked={classesChoisies.includes(c.id)} onChange={() => basculerClasse(c.id)} />
                  <span className="tuile-nom">{c.nom}</span>
                  <span className="tuile-effectif">{c.effectif || 0} élève{(c.effectif || 0) > 1 ? 's' : ''}</span>
                </label>
              ))}
              {classes.length === 0 && <p className="muted">Aucune classe pour cette année.</p>}
            </div>
          )}
        </div>
        <p className="muted">Les filtres s'appliquent aux élèves, inscriptions, classes, notes, résultats et affectations. Aucune classe cochée = toutes les classes.</p>
      </div>

      <div className="barre-action-fixe">
        <div>
          {cles.length === 0
            ? <span className="muted">Cochez au moins un type de données.</span>
            : <><strong>{cles.length}</strong> feuille{cles.length > 1 ? 's' : ''} · <strong>{lignes}</strong> ligne{lignes > 1 ? 's' : ''}</>}
        </div>
        <button type="button" className="btn-primary btn-grand" disabled={cles.length === 0 || envoi} onClick={exporter}>
          <Icon nom="telecharger" taille={17} /> {envoi ? 'Préparation du fichier…' : 'Télécharger le fichier Excel'}
        </button>
      </div>
    </>
  );
};

// ---------------------------------------------------------------------------
// IMPORT
// ---------------------------------------------------------------------------
const Import = () => {
  const [modeles, setModeles] = useState([]);
  const [cle, setCle] = useState('');
  const [fichier, setFichier] = useState(null);
  const [rapport, setRapport] = useState(null);
  const [ignorer, setIgnorer] = useState(false);
  const [occupe, setOccupe] = useState('');
  const [erreur, setErreur] = useState('');
  const [succes, setSucces] = useState('');
  const [survol, setSurvol] = useState(false);
  const entree = useRef(null);

  useEffect(() => {
    api.get('/school/import/jeux/').then((r) => { setModeles(r.data.jeux); setCle(r.data.jeux[0]?.cle || ''); })
      .catch((e) => setErreur(formatApiError(e)));
  }, []);

  const modele = modeles.find((m) => m.cle === cle);

  const choisirFichier = (f) => {
    setRapport(null); setSucces(''); setErreur(''); setIgnorer(false);
    if (!f) { setFichier(null); return; }
    if (!f.name.toLowerCase().endsWith('.xlsx')) {
      setFichier(null);
      setErreur('Le fichier doit être un classeur Excel au format .xlsx (dans Excel : Fichier → Enregistrer sous → Classeur Excel).');
      return;
    }
    setFichier(f);
  };

  const telechargerModele = async () => {
    setErreur('');
    try {
      const res = await api.get(`/school/import/modele/${cle}/`, { responseType: 'blob' });
      enregistrerBlob(new Blob([res.data], { type: res.data.type }), nomFichierRecu(res, `modele-import-${cle}.xlsx`));
    } catch (err) { setErreur(await messageErreurBlob(err, 'Téléchargement impossible.')); }
  };

  const envoyer = async (apercu) => {
    setErreur(''); setSucces(''); setOccupe(apercu ? 'verif' : 'import');
    const corps = new FormData();
    corps.append('jeu', cle);
    corps.append('fichier', fichier);
    corps.append('apercu', apercu ? 'true' : 'false');
    corps.append('ignorer_erreurs', ignorer ? 'true' : 'false');
    try {
      const res = await api.post('/school/import/', corps, { headers: { 'Content-Type': 'multipart/form-data' } });
      setRapport(res.data);
      if (!apercu) {
        if (res.data.applique) {
          setSucces(`Import terminé : ${res.data.crees} créé${res.data.crees > 1 ? 's' : ''}, ${res.data.mis_a_jour} mis à jour, ${res.data.ignores} déjà présent${res.data.ignores > 1 ? 's' : ''}.`);
          setFichier(null); setRapport(null);
        } else {
          setErreur("Rien n'a été importé : corrigez les erreurs ci-dessous, ou cochez « importer quand même les lignes valides ».");
        }
      }
    } catch (err) { setErreur(formatApiError(err, "L'import a échoué.")); }
    setOccupe('');
  };

  const aImporter = rapport ? rapport.crees + rapport.mis_a_jour : 0;

  return (
    <>
      {erreur && <div className="error">{erreur}</div>}
      {succes && <div className="success">{succes}</div>}

      <div className="card">
        <h3>1. Que voulez-vous importer ?</h3>
        <div className="form-group">
          <label htmlFor="im-jeu">Type de données</label>
          <select id="im-jeu" value={cle} onChange={(e) => { setCle(e.target.value); choisirFichier(null); }}>
            {modeles.map((m) => <option key={m.cle} value={m.cle}>{m.libelle}</option>)}
          </select>
        </div>
        {modele && (
          <>
            <p>{modele.resume}</p>
            <ul className="colonnes-modele" aria-label="Colonnes attendues">
              {modele.colonnes.map((c) => (
                <li key={c.titre} className={c.obligatoire ? 'obligatoire' : ''} title={c.aide}>
                  {c.titre}{c.obligatoire ? ' *' : ''}
                </li>
              ))}
            </ul>
            <p className="muted" style={{ marginTop: 8 }}>* colonne obligatoire. Les titres peuvent s'écrire avec ou sans accents.</p>
            {modele.notes.map((n) => <p key={n} className="muted">• {n}</p>)}
            <button type="button" className="btn-secondary" onClick={telechargerModele}>
              <Icon nom="telecharger" taille={16} /> Télécharger le modèle Excel à remplir
            </button>
          </>
        )}
      </div>

      <div className="card">
        <h3>2. Choisissez votre fichier Excel</h3>
        <input ref={entree} type="file" accept=".xlsx" hidden aria-label="Fichier Excel à importer"
          onChange={(e) => { choisirFichier(e.target.files[0]); e.target.value = ''; }} />
        <div className={`zone-depot ${survol ? 'survol' : ''}`} role="button" tabIndex={0}
          onClick={() => entree.current.click()}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); entree.current.click(); } }}
          onDragOver={(e) => { e.preventDefault(); setSurvol(true); }}
          onDragLeave={() => setSurvol(false)}
          onDrop={(e) => { e.preventDefault(); setSurvol(false); choisirFichier(e.dataTransfer.files[0]); }}>
          <Icon nom="televerser" taille={30} />
          {fichier ? (
            <>
              <strong>{fichier.name}</strong>
              <span>{formatTaille(fichier.size)} · cliquez pour choisir un autre fichier</span>
            </>
          ) : (
            <>
              <strong>Déposez le fichier ici ou cliquez pour le choisir</strong>
              <span>Format .xlsx · 5 Mo maximum · première feuille du classeur</span>
            </>
          )}
        </div>
      </div>

      <div className="card">
        <h3>3. Vérifiez, puis importez</h3>
        <p className="muted">La vérification n'enregistre rien : elle montre exactement ce qui se passera.</p>
        <button type="button" className="btn-primary" disabled={!fichier || !!occupe} onClick={() => envoyer(true)}>
          <Icon nom="oeil" taille={16} /> {occupe === 'verif' ? 'Vérification…' : 'Vérifier le fichier'}
        </button>

        {rapport && (
          <div className="rapport" aria-live="polite">
            <div className="rapport-chiffres">
              <div><strong>{rapport.total}</strong><span>lignes lues</span></div>
              <div className="ok"><strong>{rapport.crees}</strong><span>à créer</span></div>
              <div className="maj"><strong>{rapport.mis_a_jour}</strong><span>à mettre à jour</span></div>
              <div><strong>{rapport.ignores}</strong><span>déjà présentes</span></div>
              <div className="err"><strong>{rapport.nb_erreurs}</strong><span>erreur{rapport.nb_erreurs > 1 ? 's' : ''}</span></div>
            </div>
            {rapport.infos.map((i) => <div key={i} className="info">{i}</div>)}
            {rapport.colonnes_ignorees.length > 0 && (
              <div className="alerte">Colonnes non reconnues, donc ignorées : {rapport.colonnes_ignorees.join(', ')}.</div>
            )}

            {rapport.nb_erreurs > 0 && (
              <div className="table-wrap liste-erreurs">
                <table className="data-table">
                  <thead><tr><th>Ligne</th><th>Problème</th></tr></thead>
                  <tbody>
                    {rapport.erreurs.map((e) => <tr key={`${e.ligne}-${e.message}`}><td>{e.ligne}</td><td>{e.message}</td></tr>)}
                  </tbody>
                </table>
                {rapport.nb_erreurs > rapport.erreurs.length && (
                  <p className="muted">… et {rapport.nb_erreurs - rapport.erreurs.length} autre(s) erreur(s).</p>
                )}
              </div>
            )}

            {rapport.nb_erreurs === 0 && aImporter === 0 && rapport.total > 0 && (
              <div className="info">Tout est déjà à jour : il n'y a rien à importer.</div>
            )}
            {rapport.nb_erreurs === 0 && rapport.total === 0 && (
              <div className="alerte">Le fichier ne contient aucune ligne de données (les titres sont en ligne 1, les données dès la ligne 2).</div>
            )}

            {aImporter > 0 && (
              <div className="actions-ligne" style={{ marginTop: 14 }}>
                {rapport.nb_erreurs > 0 && (
                  <label className="interrupteur">
                    <input type="checkbox" checked={ignorer} onChange={(e) => setIgnorer(e.target.checked)} />
                    <span className="interrupteur-piste" aria-hidden="true" />
                    Importer quand même les lignes valides
                  </label>
                )}
                <button type="button" className="btn-primary btn-grand"
                  disabled={!!occupe || (rapport.nb_erreurs > 0 && !ignorer)} onClick={() => envoyer(false)}>
                  <Icon nom="valider" taille={17} /> {occupe === 'import' ? 'Import en cours…' : `Importer ${aImporter} ligne${aImporter > 1 ? 's' : ''}`}
                </button>
              </div>
            )}
          </div>
        )}
        {!rapport && !fichier && modeles.length > 0 && (
          <EmptyState icone="tableur" titre="Aucun fichier choisi">Choisissez un fichier Excel à l'étape 2 pour le vérifier.</EmptyState>
        )}
      </div>
    </>
  );
};

// ---------------------------------------------------------------------------
const ImportExport = () => {
  const [onglet, setOnglet] = useState('export');
  return (
    <div className="page">
      <PageHeader titre="Import / Export Excel"
        sousTitre="Récupérez vos données dans un classeur Excel, ou ajoutez-en d'un seul coup depuis un fichier Excel." />
      <div className="onglets" role="tablist">
        <button type="button" role="tab" aria-selected={onglet === 'export'} className={`onglet ${onglet === 'export' ? 'actif' : ''}`}
          onClick={() => setOnglet('export')}><Icon nom="telecharger" taille={16} /> Exporter vers Excel</button>
        <button type="button" role="tab" aria-selected={onglet === 'import'} className={`onglet ${onglet === 'import' ? 'actif' : ''}`}
          onClick={() => setOnglet('import')}><Icon nom="televerser" taille={16} /> Importer depuis Excel</button>
      </div>
      {onglet === 'export' ? <Export /> : <Import />}
    </div>
  );
};

export default ImportExport;

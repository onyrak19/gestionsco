import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import api from '../../api/axios';
import { formatApiError } from '../../utils/errors';
import { ouvrirPdf } from '../../utils/pdf';
import { formatNote } from '../../utils/notes';
import { classeNote, TRIMESTRES } from '../../utils/labels';
import {
  EXTENSIONS_ACCEPTEES, NB_MAX_PIECES, TYPES_DOCUMENTS, formatTaille, ouvrirPiece, verifierPiece,
} from '../../utils/fichiers';
import DecisionBadge from '../ui/DecisionBadge';
import Icon from '../ui/Icon';
import Avatar from '../ui/Avatar';
import PhotoPicker from '../ui/PhotoPicker';
import EmptyState from '../ui/EmptyState';

const dateFr = (iso) => (iso ? iso.split('-').reverse().join('/') : '—');
const dateHeureFr = (iso) => new Date(iso).toLocaleDateString('fr-FR');

// Pièces jointes d'une inscription : liste, ouverture, ajout et suppression
const PiecesInscription = ({ parcours, onChange, onError }) => {
  const entree = useRef(null);
  const [libelle, setLibelle] = useState('');
  const [envoi, setEnvoi] = useState(false);
  const pieces = parcours.pieces || [];

  const ajouter = async (e) => {
    const choisis = Array.from(e.target.files || []);
    e.target.value = '';
    if (!choisis.length) return;
    if (choisis.length > NB_MAX_PIECES) { onError(`Maximum ${NB_MAX_PIECES} fichiers à la fois.`); return; }
    const probleme = choisis.map(verifierPiece).find(Boolean);
    if (probleme) { onError(probleme); return; }
    const corps = new FormData();
    choisis.forEach((f) => { corps.append('fichiers', f); corps.append('libelles', libelle); });
    setEnvoi(true);
    try {
      await api.post(`/school/inscriptions/${parcours.inscription}/pieces/`, corps,
        { headers: { 'Content-Type': 'multipart/form-data' } });
      setLibelle('');
      onChange(`${choisis.length} pièce${choisis.length > 1 ? 's' : ''} jointe${choisis.length > 1 ? 's' : ''} ajoutée${choisis.length > 1 ? 's' : ''}.`);
    } catch (err) { onError(formatApiError(err)); }
    setEnvoi(false);
  };

  const ouvrir = async (p) => { try { await ouvrirPiece(p); } catch (err) { onError(err.message); } };

  const retirer = async (p) => {
    if (!window.confirm(`Supprimer la pièce jointe « ${p.libelle || p.nom_original} » ?`)) return;
    try {
      await api.delete(`/school/pieces-jointes/${p.id}/`);
      onChange('Pièce jointe supprimée.');
    } catch (err) { onError(formatApiError(err)); }
  };

  return (
    <div className="bloc-pieces">
      <div className="bloc-pieces-entete">
        <span><strong>{parcours.annee}</strong> — {parcours.classe}</span>
        {!parcours.annee_cloturee && (
          <div className="actions-ligne">
            <select value={libelle} onChange={(e) => setLibelle(e.target.value)} aria-label={`Type de document à ajouter (${parcours.annee})`}>
              <option value="">Type de document…</option>
              {TYPES_DOCUMENTS.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
            <input ref={entree} type="file" multiple accept={EXTENSIONS_ACCEPTEES} hidden onChange={ajouter}
              aria-label={`Ajouter des pièces jointes (${parcours.annee})`} />
            <button type="button" className="btn-secondary btn-compact" disabled={envoi} onClick={() => entree.current.click()}>
              <Icon nom="trombone" taille={15} /> {envoi ? 'Envoi…' : 'Ajouter'}
            </button>
          </div>
        )}
      </div>
      {pieces.length === 0 ? (
        <p className="muted">Aucune pièce jointe pour cette inscription.</p>
      ) : (
        <ul className="liste-pieces">
          {pieces.map((p) => (
            <li key={p.id}>
              <Icon nom="fichier" taille={18} />
              <button type="button" className="lien-bouton piece-nom" title={p.nom_original} onClick={() => ouvrir(p)}>
                {p.libelle || p.nom_original}
              </button>
              {p.libelle && <small className="muted piece-original">{p.nom_original}</small>}
              <small className="muted">{formatTaille(p.taille)} · {dateHeureFr(p.date_ajout)}{p.ajoute_par_nom ? ` · ${p.ajoute_par_nom}` : ''}</small>
              <button type="button" className="btn-small btn-secondary" onClick={() => ouvrir(p)} aria-label={`Ouvrir ${p.nom_original}`}>
                <Icon nom="oeil" taille={14} />
              </button>
              {!parcours.annee_cloturee && (
                <button type="button" className="btn-small btn-danger" onClick={() => retirer(p)} aria-label={`Supprimer ${p.nom_original}`}>
                  <Icon nom="corbeille" taille={14} />
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

const EleveDetail = () => {
  const { id } = useParams();
  const [dossier, setDossier] = useState(null);
  const [erreur, setErreur] = useState('');
  const [message, setMessage] = useState('');
  const [edition, setEdition] = useState(null);
  const [nouvellePhoto, setNouvellePhoto] = useState(null);
  const [retirerPhoto, setRetirerPhoto] = useState(false);
  const [trimestres, setTrimestres] = useState({});   // trimestre choisi par inscription

  const charger = useCallback(() => {
    return api.get(`/school/eleves/${id}/dossier/`).then((r) => setDossier(r.data))
      .catch((err) => setErreur(formatApiError(err)));
  }, [id]);
  useEffect(() => { charger(); }, [charger]);

  const imprimer = async (chemin, corps) => {
    setErreur('');
    try { await ouvrirPdf(chemin, corps); } catch (e) { setErreur(e.message); }
  };

  const changerDecision = async (inscription, decision) => {
    setErreur(''); setMessage('');
    try {
      await api.patch(`/school/inscriptions/${inscription}/decision/`, { decision });
      setMessage('Décision mise à jour.');
      charger();
    } catch (err) { setErreur(formatApiError(err)); }
  };

  const commencerEdition = () => {
    const { eleve } = dossier;
    setNouvellePhoto(null); setRetirerPhoto(false);
    setEdition({
      nom: eleve.nom, prenom: eleve.prenom, date_naissance: eleve.date_naissance || '', sexe: eleve.sexe,
      parent_nom: eleve.parent_nom || '', parent_mobile: eleve.parent_mobile || '',
      parent2_nom: eleve.parent2_nom || '', parent2_mobile: eleve.parent2_mobile || '',
    });
  };

  const enregistrer = async (e) => {
    e.preventDefault();
    setErreur(''); setMessage('');
    try {
      if (nouvellePhoto || retirerPhoto) {
        const corps = new FormData();
        corps.append('nom', edition.nom);
        corps.append('prenom', edition.prenom);
        corps.append('sexe', edition.sexe);
        corps.append('date_naissance', edition.date_naissance || '');
        ['parent_nom', 'parent_mobile', 'parent2_nom', 'parent2_mobile'].forEach((c) => corps.append(c, edition[c] || ''));
        if (nouvellePhoto) corps.append('photo', nouvellePhoto);
        else corps.append('retirer_photo', 'true');
        await api.patch(`/school/eleves/${id}/`, corps, { headers: { 'Content-Type': 'multipart/form-data' } });
      } else {
        await api.patch(`/school/eleves/${id}/`, { ...edition, date_naissance: edition.date_naissance || null });
      }
      setEdition(null);
      setMessage('Informations enregistrées.');
      charger();
    } catch (err) { setErreur(formatApiError(err)); }
  };

  const apresPieces = (texte) => { setErreur(''); setMessage(texte); charger(); };

  if (!dossier) {
    return <div className="page"><h1>Élève</h1>{erreur ? <div className="error">{erreur}</div> : <p className="loading">Chargement…</p>}</div>;
  }
  const { eleve, parcours, statut } = dossier;
  const aUnePhoto = !!eleve.photo_token && !retirerPhoto;

  return (
    <div className="page">
      <p><Link to="/admin/eleves" className="lien-retour"><Icon nom="gauche" taille={15} /> Élèves</Link></p>
      {erreur && <div className="error">{erreur}</div>}
      {message && <div className="success">{message}</div>}

      <div className="card">
        {!edition ? (
          <div className="carte-identite">
            <Avatar eleve={eleve} taille="xl" />
            <div className="identite-infos">
              <div><small>Nom et prénom</small><strong className="identite-nom">{eleve.nom.toUpperCase()} {eleve.prenom}</strong></div>
              <div><small>Matricule</small>{eleve.matricule || <span className="muted">Attribué à l'inscription</span>}</div>
              <div><small>Né(e) le</small>{dateFr(eleve.date_naissance)}</div>
              <div><small>Sexe</small>{eleve.sexe === 'F' ? 'Féminin' : 'Masculin'}</div>
              <div><small>Situation</small><DecisionBadge decision={statut} /></div>
              <div><small>Parent / tuteur</small>{eleve.parent_nom ? <>{eleve.parent_nom}{eleve.parent_mobile && <> · {eleve.parent_mobile}</>}</> : <span className="muted">Non renseigné</span>}</div>
              {(eleve.parent2_nom || eleve.parent2_mobile) && (
                <div><small>Second parent</small>{eleve.parent2_nom}{eleve.parent2_mobile && <> · {eleve.parent2_mobile}</>}</div>
              )}
            </div>
            <button className="btn-small btn-secondary" onClick={commencerEdition}>
              <Icon nom="crayonEdit" taille={14} /> Modifier
            </button>
          </div>
        ) : (
          <form onSubmit={enregistrer}>
            <div className="form-row">
              <div className="form-group"><label htmlFor="ed-nom">Nom</label>
                <input id="ed-nom" value={edition.nom} required onChange={(e) => setEdition({ ...edition, nom: e.target.value })} /></div>
              <div className="form-group"><label htmlFor="ed-prenom">Prénom</label>
                <input id="ed-prenom" value={edition.prenom} required onChange={(e) => setEdition({ ...edition, prenom: e.target.value })} /></div>
              <div className="form-group"><label htmlFor="ed-naiss">Date de naissance</label>
                <input id="ed-naiss" type="date" value={edition.date_naissance} onChange={(e) => setEdition({ ...edition, date_naissance: e.target.value })} /></div>
              <div className="form-group"><label htmlFor="ed-sexe">Sexe</label>
                <select id="ed-sexe" value={edition.sexe} onChange={(e) => setEdition({ ...edition, sexe: e.target.value })}>
                  <option value="M">Masculin</option><option value="F">Féminin</option>
                </select></div>
            </div>
            <div className="form-row">
              <div className="form-group"><label htmlFor="ed-p1">Parent / tuteur</label>
                <input id="ed-p1" value={edition.parent_nom} maxLength={150} onChange={(e) => setEdition({ ...edition, parent_nom: e.target.value })} /></div>
              <div className="form-group"><label htmlFor="ed-m1">Mobile du parent</label>
                <input id="ed-m1" type="tel" value={edition.parent_mobile} maxLength={30} onChange={(e) => setEdition({ ...edition, parent_mobile: e.target.value })} /></div>
              <div className="form-group"><label htmlFor="ed-p2">Second parent</label>
                <input id="ed-p2" value={edition.parent2_nom} maxLength={150} onChange={(e) => setEdition({ ...edition, parent2_nom: e.target.value })} /></div>
              <div className="form-group"><label htmlFor="ed-m2">Mobile du second parent</label>
                <input id="ed-m2" type="tel" value={edition.parent2_mobile} maxLength={30} onChange={(e) => setEdition({ ...edition, parent2_mobile: e.target.value })} /></div>
            </div>
            <div className="form-group">
              <label htmlFor="photo-modif">Photo</label>
              <PhotoPicker id="photo-modif" fichier={nouvellePhoto}
                onChange={(f) => { setNouvellePhoto(f); setRetirerPhoto(false); }}
                actuelle={aUnePhoto ? <Avatar eleve={eleve} taille="l" /> : null}
                onRetirer={() => setRetirerPhoto(true)} />
              {retirerPhoto && <small className="muted">La photo sera retirée à l’enregistrement.</small>}
            </div>
            <div className="actions-ligne">
              <button className="btn-primary" type="submit">Enregistrer</button>
              <button type="button" className="btn-secondary" onClick={() => setEdition(null)}>Annuler</button>
            </div>
          </form>
        )}
      </div>

      <div className="card">
        <h3>Parcours scolaire</h3>
        {parcours.length === 0 && <p className="muted">Cet élève n'est inscrit dans aucune classe.</p>}
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Année</th><th>Classe</th><th className="centre">N°</th>
                <th className="centre">T1</th><th className="centre">T2</th><th className="centre">T3</th>
                <th className="centre">Annuelle</th><th className="centre">Rang</th><th>Décision</th><th>Documents</th>
              </tr>
            </thead>
            <tbody>
              {parcours.map((p) => {
                const t = trimestres[p.inscription] || 1;
                return (
                  <tr key={p.inscription}>
                    <td className="cellule-annee"><strong>{p.annee}</strong>{p.annee_cloturee && <> <span className="badge badge-cloturee">clôturée</span></>}</td>
                    <td><Link to={`/admin/classes/${p.classe_id}`}>{p.classe}</Link></td>
                    <td className="centre">{p.numero}</td>
                    {['T1', 'T2', 'T3'].map((k) => (
                      <td key={k} className={`centre ${classeNote(p.moyennes[k])}`}>{formatNote(p.moyennes[k])}</td>
                    ))}
                    <td className={`centre ${classeNote(p.moyenne_annuelle)}`}><strong>{formatNote(p.moyenne_annuelle)}</strong></td>
                    <td className="centre">{p.rang_annuel ? `${p.rang_annuel}/${p.effectif}` : '-'}</td>
                    <td>
                      <DecisionBadge decision={p.decision} />
                      {p.annee_cloturee && (
                        <select aria-label="Corriger la décision" value="" className="select-compact"
                          onChange={(e) => e.target.value && changerDecision(p.inscription, e.target.value)}>
                          <option value="">Modifier…</option>
                          <option value="passant">Passant</option>
                          <option value="redoublant">Redoublant</option>
                        </select>
                      )}
                    </td>
                    <td className="cellule-docs">
                      <select value={t} aria-label="Trimestre du bulletin" className="select-compact"
                        onChange={(e) => setTrimestres({ ...trimestres, [p.inscription]: Number(e.target.value) })}>
                        {TRIMESTRES.map((x) => <option key={x.value} value={x.value}>{x.label}</option>)}
                      </select>
                      <button className="btn-small btn-secondary" onClick={() => imprimer('/school/pdf/bulletins/', { inscriptions: [p.inscription], trimestre: t })}>Bulletin</button>
                      <button className="btn-small btn-secondary" onClick={() => imprimer('/school/pdf/certificats/', { inscriptions: [p.inscription] })}>Certificat</button>
                      <button className="btn-small btn-secondary" onClick={() => imprimer('/school/pdf/cartes/', { inscriptions: [p.inscription] })}>Carte</button>
                      <Link className="btn-small btn-secondary" to={`/admin/finances/eleves/${p.inscription}`}>Écolage</Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <h3>Pièces jointes du dossier</h3>
        {parcours.length === 0 ? (
          <EmptyState icone="trombone" titre="Pas encore de dossier">
            Les pièces jointes se rattachent à une inscription : inscrivez d’abord l’élève dans une classe.
          </EmptyState>
        ) : parcours.map((p) => (
          <PiecesInscription key={p.inscription} parcours={p} onChange={apresPieces} onError={(m) => { setMessage(''); setErreur(m); }} />
        ))}
      </div>
    </div>
  );
};

export default EleveDetail;

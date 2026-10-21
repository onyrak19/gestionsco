import React, { useEffect, useMemo, useRef, useState } from 'react';
import { calculerMoyennes, formatNote } from '../../utils/notes';
import { classeNote } from '../../utils/labels';
import Icon from '../ui/Icon';
import Avatar from '../ui/Avatar';

const CHAMPS = [
  { cle: 'j1', libelle: 'J1' },
  { cle: 'j2', libelle: 'J2' },
  { cle: 'j3', libelle: 'J3' },
  { cle: 'examen', libelle: 'Examen' },
];

const estVide = (v) => v === '' || v === null || v === undefined;

// Première erreur de saisie (hors plage 0–20), ou ''
export const erreurDeSaisie = (note = {}) => {
  for (const { cle, libelle } of CHAMPS) {
    const v = note[cle];
    if (estVide(v)) continue;
    const n = Number(v);
    if (Number.isNaN(n) || n < 0 || n > 20) return `${libelle} : la note doit être comprise entre 0 et 20.`;
  }
  return '';
};

const aUneNote = (note = {}) => CHAMPS.some(({ cle }) => !estVide(note[cle]));

// Saisie élève par élève : un seul élève à l'écran, « Suivant » enregistre puis passe au numéro suivant.
const SaisiePasAPas = ({ eleves, notes, statuts, contexte, onChange, onSave, onTerminer, onQuitter }) => {
  const [index, setIndex] = useState(0);
  const [erreur, setErreur] = useState('');
  const [occupe, setOccupe] = useState(false);
  const champs = useRef([]);

  const total = eleves.length;
  const ins = eleves[index];
  const note = (ins && notes[ins.id]) || {};
  const statut = ins ? statuts[ins.id] : null;
  const { moyenneJournaliere, moyenneMatiere } = calculerMoyennes(note);
  const nbSaisis = useMemo(
    () => eleves.filter((e) => aUneNote(notes[e.id])).length,
    [eleves, notes],
  );

  // Le curseur se place sur J1 à chaque nouvel élève : on peut taper sans toucher la souris
  useEffect(() => {
    if (champs.current[0]) champs.current[0].focus();
    setErreur('');
  }, [index]);

  // Enregistre l'élève affiché s'il a été modifié. Retourne false s'il faut rester sur cet élève.
  const enregistrerCourant = async () => {
    if (!ins) return true;
    const st = statuts[ins.id];
    if (!st || (st.type !== 'modifie' && st.type !== 'erreur')) return true;   // rien à enregistrer
    const probleme = erreurDeSaisie(note);
    if (probleme) { setErreur(probleme); return false; }
    return onSave(ins.id);
  };

  const aller = async (cible) => {
    if (occupe || cible < 0 || cible >= total || cible === index) return;
    setOccupe(true);
    const ok = await enregistrerCourant();
    setOccupe(false);
    if (ok) setIndex(cible);
  };

  const suivant = async () => {
    if (occupe) return;
    if (index < total - 1) { aller(index + 1); return; }
    setOccupe(true);
    const ok = await enregistrerCourant();
    setOccupe(false);
    if (ok) onTerminer({ saisis: nbSaisis, total });
  };

  const quitter = async () => {
    if (occupe) return;
    setOccupe(true);
    const ok = await enregistrerCourant();
    setOccupe(false);
    if (ok) onQuitter();
  };

  const touche = (e, i) => {
    if (e.key !== 'Enter') return;
    e.preventDefault();
    if (i < CHAMPS.length - 1) champs.current[i + 1].focus();   // Entrée : champ suivant
    else suivant();                                            // dernier champ : élève suivant
  };

  if (!ins) return <div className="card"><p className="muted">Aucun élève inscrit dans cette classe.</p></div>;
  const eleve = ins.eleve_details || {};
  const dernier = index === total - 1;

  return (
    <div className="pas-a-pas">
      <div className="pas-contexte">
        <div>
          <strong>{contexte.classe}</strong> · {contexte.matiere} · {contexte.trimestre}
        </div>
        <button type="button" className="btn-secondary btn-compact" onClick={quitter} disabled={occupe}>
          <Icon nom="fermer" taille={15} /> Quitter la saisie
        </button>
      </div>

      <div className="pas-rail" role="group" aria-label="Élèves de la classe">
        {eleves.map((e, i) => {
          const st = statuts[e.id];
          const classes = ['rail-pastille'];
          if (i === index) classes.push('courant');
          else if (st?.type === 'erreur') classes.push('erreur');
          else if (aUneNote(notes[e.id])) classes.push('rempli');
          return (
            <button key={e.id} type="button" className={classes.join(' ')} onClick={() => aller(i)}
              aria-label={`Élève n° ${e.numero}`} aria-current={i === index ? 'step' : undefined}
              title={`${e.eleve_details?.nom || ''} ${e.eleve_details?.prenom || ''}`}>
              {e.numero}
            </button>
          );
        })}
      </div>

      <section key={ins.id} className="fiche" aria-live="polite">
        <div className="fiche-marge" aria-hidden="true" />
        <div className="fiche-corps">
          <div className="fiche-entete">
            <Avatar eleve={eleve} taille="xl" />
            <div>
              <div className="fiche-numero">Élève n° {ins.numero} <span>sur {total}</span></div>
              <h2 className="fiche-nom">{(eleve.nom || '').toUpperCase()} <span>{eleve.prenom}</span></h2>
              <div className="muted">{eleve.matricule}</div>
            </div>
          </div>

          <div className="fiche-notes">
            {CHAMPS.map(({ cle, libelle }, i) => (
              <label key={cle} className="fiche-note">
                <span>{libelle}</span>
                <input
                  ref={(el) => { champs.current[i] = el; }}
                  type="number" inputMode="decimal" step="0.01" min="0" max="20"
                  value={note[cle] ?? ''}
                  onChange={(e) => onChange(ins.id, cle, e.target.value)}
                  onKeyDown={(e) => touche(e, i)}
                  placeholder="—"
                />
              </label>
            ))}
          </div>

          <div className="fiche-moyennes">
            <div><small>Moyenne journalière</small><strong>{formatNote(moyenneJournaliere)}</strong></div>
            <div><small>Moyenne de la matière</small>
              <strong className={classeNote(moyenneMatiere)}>{formatNote(moyenneMatiere)}</strong></div>
          </div>

          <div className="fiche-etat" role="status">
            {erreur && <span className="statut-erreur">{erreur}</span>}
            {!erreur && statut?.type === 'ok' && <span className="statut-ok">✓ Enregistré</span>}
            {!erreur && statut?.type === 'modifie' && <span className="statut-modifie">Enregistrement en passant au suivant</span>}
            {!erreur && statut?.type === 'attente' && <span className="statut-attente">Enregistrement…</span>}
            {!erreur && statut?.type === 'erreur' && <span className="statut-erreur">{statut.message}</span>}
          </div>
        </div>
      </section>

      <div className="pas-actions">
        <button type="button" className="btn-secondary" onClick={() => aller(index - 1)} disabled={index === 0 || occupe}>
          <Icon nom="gauche" taille={16} /> Précédent
        </button>
        <div className="pas-progression" aria-label={`${nbSaisis} élèves avec note sur ${total}`}>
          <span>{nbSaisis} / {total} avec note</span>
          <div className="barre"><div style={{ width: `${total ? (nbSaisis / total) * 100 : 0}%` }} /></div>
        </div>
        <button type="button" className="btn-primary btn-grand" onClick={suivant} disabled={occupe}
          aria-label={dernier ? 'Enregistrer et terminer' : 'Enregistrer et suivant'}>
          <span className="texte-long">{dernier ? 'Enregistrer et terminer' : 'Enregistrer et suivant'}</span>
          <span className="texte-court">{dernier ? 'Terminer' : 'Suivant'}</span>
          <Icon nom={dernier ? 'valider' : 'droite'} taille={16} />
        </button>
      </div>
    </div>
  );
};

export default SaisiePasAPas;

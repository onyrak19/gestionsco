import React, { useCallback, useEffect, useState } from 'react';
import api from '../../api/axios';
import { formatApiError } from '../../utils/errors';
import { lireMontant } from '../../utils/argent';
import useAnnees from '../../hooks/useAnnees';
import useFinance from '../../hooks/useFinance';
import PageHeader from '../ui/PageHeader';
import SelectAnnee from '../ui/SelectAnnee';
import EmptyState from '../ui/EmptyState';
import Modal from '../ui/Modal';
import Icon from '../ui/Icon';

const nomNiveau = (n) => `${n.niveau}${n.serie ? ` ${n.serie}` : ''}`;
const texte = (v) => (v === null || v === undefined ? '' : String(v));

// Tarifs par niveau : droit d'inscription, écolage mensuel, autres frais
const Tarifs = () => {
  const { argent } = useFinance();
  const { annees, annee, setAnnee, pret } = useAnnees();
  const [data, setData] = useState(null);
  const [edition, setEdition] = useState(null);     // { niveau, serie, droit, ecolage, autres, toutes, avecSerie }
  const [copie, setCopie] = useState(null);          // { de, ecraser }
  const [erreur, setErreur] = useState('');
  const [erreurModal, setErreurModal] = useState('');
  const [message, setMessage] = useState('');

  const charger = useCallback(() => {
    if (!annee) return Promise.resolve();
    return api.get('/finance/tarifs/', { params: { annee } })
      .then((r) => { setData(r.data); setErreur(''); })
      .catch((err) => { setData(null); setErreur(formatApiError(err)); });
  }, [annee]);
  useEffect(() => { charger(); }, [charger]);

  const corpsDe = (e) => ({
    annee: Number(annee), niveau: e.niveau, serie: e.serie,
    droit_inscription: lireMontant(e.droit), ecolage_mensuel: lireMontant(e.ecolage),
    autres: e.autres.filter((a) => a.libelle.trim() || a.montant !== '')
      .map((a) => ({ libelle: a.libelle.trim(), montant: lireMontant(a.montant) ?? 0 })),
    appliquer_a_toutes_series: !!e.toutes,
  });

  const ouvrir = (n) => {
    setErreurModal('');
    setEdition({
      niveau: n.niveau, serie: n.serie, droit: texte(n.droit_inscription), ecolage: texte(n.ecolage_mensuel),
      autres: n.autres.map((a) => ({ libelle: a.libelle, montant: texte(a.montant) })),
      toutes: false, avecSerie: (data.niveaux_avec_serie || []).includes(n.niveau),
    });
  };

  const enregistrer = async (e, brut) => {
    if (e) e.preventDefault();
    setErreurModal(''); setErreur('');
    try {
      const r = await api.put('/finance/tarifs/', corpsDe(brut || edition));
      setData(r.data);
      setEdition(null);
      setMessage('Tarifs enregistrés.');
    } catch (err) {
      const m = formatApiError(err);
      if (brut) setErreur(m); else setErreurModal(m);
    }
  };

  const valider = (n) => enregistrer(null, {
    niveau: n.niveau, serie: n.serie, droit: texte(n.droit_inscription), ecolage: texte(n.ecolage_mensuel),
    autres: n.autres.map((a) => ({ libelle: a.libelle, montant: texte(a.montant) })), toutes: false,
  });

  const copier = async (e) => {
    e.preventDefault();
    setErreurModal('');
    try {
      const r = await api.post('/finance/tarifs/copier/', { de: Number(copie.de), vers: Number(annee), ecraser: copie.ecraser });
      const ign = r.data.niveaux_ignores;
      setMessage(`${r.data.copies} tarif(s) copié(s)${ign.length ? ` — niveaux déjà configurés, ignorés : ${ign.join(', ')}` : ''}.`);
      setCopie(null);
      charger();
    } catch (err) { setErreurModal(formatApiError(err)); }
  };

  const majAutre = (i, champ, valeur) => setEdition((ed) => ({
    ...ed, autres: ed.autres.map((a, j) => (j === i ? { ...a, [champ]: valeur } : a)),
  }));
  const cloturee = data?.annee?.cloturee;

  return (
    <div className="page">
      <PageHeader titre="Tarifs"
        sousTitre="Définissez une fois par niveau le droit d'inscription, l'écolage mensuel et les autres frais : les encaissements en découlent.">
        <button type="button" className="btn-secondary" disabled={cloturee || annees.length < 2}
          onClick={() => { setErreurModal(''); setCopie({ de: String(annees.find((a) => String(a.id) !== String(annee))?.id || ''), ecraser: false }); }}>
          Copier depuis une autre année
        </button>
      </PageHeader>
      {erreur && <div className="error">{erreur}</div>}
      {message && <div className="success">{message}</div>}
      {cloturee && <div className="info alerte">Cette année est clôturée : ses tarifs sont figés.</div>}

      <div className="card">
        {pret && <SelectAnnee id="ta-annee" annees={annees} valeur={annee} onChange={setAnnee} />}
      </div>

      {data && data.niveaux.length === 0 && (
        <EmptyState icone="etiquette" titre="Aucun niveau">Créez d'abord les classes de cette année (avec leur niveau).</EmptyState>
      )}

      {data && data.niveaux.map((n) => (
        <section className="card" key={`${n.niveau}|${n.serie}`}>
          <div className="card-titre">
            <div>
              <h3>{nomNiveau(n)}</h3>
              <small className="muted">{n.classes.map((c) => c.nom).join(', ') || 'Aucune classe'} · {n.effectif} élève{n.effectif > 1 ? 's' : ''}</small>
            </div>
            <div className="actions-ligne">
              {n.propose && <button type="button" className="btn-primary btn-compact" disabled={cloturee} onClick={() => valider(n)}>Valider cette proposition</button>}
              <button type="button" className="btn-secondary btn-compact" disabled={cloturee} onClick={() => ouvrir(n)}
                aria-label={`Modifier les tarifs ${nomNiveau(n)}`}><Icon nom="crayonEdit" taille={14} /> Modifier</button>
            </div>
          </div>
          {n.propose && <p className="info alerte">Proposition reprise de l'année précédente : elle n'est pas encore enregistrée.</p>}
          {n.droit_inscription === null && n.ecolage_mensuel === null ? (
            <p className="muted">Aucun tarif défini : les élèves de ce niveau ne peuvent pas encore payer.</p>
          ) : (
            <div className="tarif-lignes">
              <div><small>Droit d'inscription</small><strong>{argent(n.droit_inscription)}</strong></div>
              <div><small>Écolage mensuel</small><strong>{argent(n.ecolage_mensuel)}</strong></div>
              {n.autres.map((a) => <div key={a.libelle}><small>{a.libelle}</small><strong>{argent(a.montant)}</strong></div>)}
            </div>
          )}
        </section>
      ))}

      {edition && (
        <Modal titre={`Tarifs — ${nomNiveau(edition)}`} onClose={() => setEdition(null)}>
          <form onSubmit={enregistrer}>
            {erreurModal && <div className="error">{erreurModal}</div>}
            <div className="form-row">
              <div className="form-group"><label htmlFor="ta-droit">Droit d'inscription</label>
                <input id="ta-droit" inputMode="decimal" value={edition.droit} onChange={(e) => setEdition({ ...edition, droit: e.target.value })} /></div>
              <div className="form-group"><label htmlFor="ta-ecolage">Écolage mensuel</label>
                <input id="ta-ecolage" inputMode="decimal" value={edition.ecolage} onChange={(e) => setEdition({ ...edition, ecolage: e.target.value })} /></div>
            </div>
            <h4>Autres frais</h4>
            {edition.autres.map((a, i) => (
              <div className="form-row" key={i}>
                <div className="form-group"><label htmlFor={`ta-lib-${i}`}>Libellé</label>
                  <input id={`ta-lib-${i}`} value={a.libelle} maxLength={100} onChange={(e) => majAutre(i, 'libelle', e.target.value)} /></div>
                <div className="form-group"><label htmlFor={`ta-mt-${i}`}>Montant</label>
                  <input id={`ta-mt-${i}`} inputMode="decimal" value={a.montant} onChange={(e) => majAutre(i, 'montant', e.target.value)} /></div>
                <button type="button" className="btn-small btn-danger" aria-label="Retirer ce frais"
                  onClick={() => setEdition({ ...edition, autres: edition.autres.filter((_, j) => j !== i) })}>✕</button>
              </div>
            ))}
            <button type="button" className="btn-secondary btn-compact"
              onClick={() => setEdition({ ...edition, autres: [...edition.autres, { libelle: '', montant: '' }] })}>
              <Icon nom="plus" taille={14} /> Ajouter un frais (uniforme, examen…)
            </button>
            {edition.avecSerie && (
              <label className="case-ligne" style={{ marginTop: 12 }}>
                <input type="checkbox" checked={edition.toutes} onChange={(e) => setEdition({ ...edition, toutes: e.target.checked })} />
                Appliquer à toutes les séries de ce niveau
              </label>
            )}
            <div className="actions-ligne" style={{ marginTop: 16 }}>
              <button className="btn-primary" type="submit">Enregistrer</button>
              <button type="button" className="btn-secondary" onClick={() => setEdition(null)}>Annuler</button>
            </div>
          </form>
        </Modal>
      )}

      {copie && (
        <Modal titre="Copier les tarifs" onClose={() => setCopie(null)}>
          <form onSubmit={copier}>
            {erreurModal && <div className="error">{erreurModal}</div>}
            <div className="form-group"><label htmlFor="co-de">Copier depuis l'année</label>
              <select id="co-de" value={copie.de} onChange={(e) => setCopie({ ...copie, de: e.target.value })}>
                {annees.filter((a) => String(a.id) !== String(annee)).map((a) => <option key={a.id} value={a.id}>{a.libelle}</option>)}
              </select></div>
            <label className="case-ligne">
              <input type="checkbox" checked={copie.ecraser} onChange={(e) => setCopie({ ...copie, ecraser: e.target.checked })} />
              Remplacer les niveaux déjà configurés
            </label>
            <div className="actions-ligne" style={{ marginTop: 16 }}>
              <button className="btn-primary" type="submit" disabled={!copie.de}>Copier</button>
              <button type="button" className="btn-secondary" onClick={() => setCopie(null)}>Annuler</button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
};

export default Tarifs;

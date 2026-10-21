import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../../api/axios';
import { formatApiError } from '../../utils/errors';
import { ouvrirPdf, lundiCourant } from '../../utils/pdf';
import { TRIMESTRES } from '../../utils/labels';
import { moisCourant } from '../../utils/argent';
import PageHeader from '../ui/PageHeader';
import Segmented from '../ui/Segmented';
import Icon from '../ui/Icon';
import EmptyState from '../ui/EmptyState';

// Documents imprimables. `mode` : 'classes' (défaut, un PDF réunit les classes choisies),
// 'classes_facultatives' (toutes les classes si aucune n'est cochée), 'periode' (année ou dates), 'mois'.
export const DOCUMENTS = {
  bulletins: {
    titre: 'Bulletins', icone: 'imprimante', chemin: '/school/pdf/bulletins/', unite: 'bulletin',
    aide: 'Moyennes, rangs et appréciation par trimestre',
  },
  cartes: {
    titre: "Cartes d'élève", icone: 'carte', chemin: '/school/pdf/cartes/', unite: 'carte',
    aide: 'Carte avec photo et QR code',
  },
  certificats: {
    titre: 'Certificats de scolarité', icone: 'certificat', chemin: '/school/pdf/certificats/', unite: 'certificat',
    aide: 'Attestation d’inscription pour chaque élève',
  },
  fiches: {
    titre: "Fiches d'appel", icone: 'appel', chemin: '/school/pdf/fiches-appel/', unite: 'fiche',
    aide: 'Feuille de présence hebdomadaire par classe',
  },
  cartes_ecolage: {
    titre: "Cartes d'écolage", icone: 'carte', chemin: '/finance/pdf/cartes-ecolage/', unite: 'carte',
    aide: 'Suivi mensuel des paiements, 2 cartes par page',
  },
  impayes: {
    titre: 'Liste des impayés', icone: 'alerte', chemin: '/finance/pdf/impayes/', unite: 'élève', mode: 'classes_facultatives',
    aide: 'Élèves qui doivent des écolages ou des droits',
  },
  rapport: {
    titre: 'Rapport financier', icone: 'graphique', chemin: '/finance/pdf/rapport/', mode: 'periode',
    aide: 'Bilan et journal de caisse d’une période',
  },
  etat_salaires: {
    titre: 'État des salaires', icone: 'portefeuille', chemin: '/finance/pdf/etat-salaires/', mode: 'mois',
    aide: 'Salaires payés pour un mois',
  },
};

const Impressions = ({ documentInitial = 'bulletins' }) => {
  const [doc, setDoc] = useState(documentInitial);
  const [annees, setAnnees] = useState([]);
  const [annee, setAnnee] = useState('');
  const [classes, setClasses] = useState([]);
  const [choisies, setChoisies] = useState([]);
  const [trimestre, setTrimestre] = useState(1);
  const [semaine, setSemaine] = useState(lundiCourant());
  const [ordre, setOrdre] = useState('alpha');
  const [au, setAu] = useState('');
  const [periode, setPeriode] = useState('annee');
  const [dates, setDates] = useState({ debut: '', fin: '' });
  const [mois, setMois] = useState(moisCourant());
  const [erreur, setErreur] = useState('');
  const [chargement, setChargement] = useState(true);
  const [envoi, setEnvoi] = useState(false);

  useEffect(() => {
    api.get('/school/annees/').then((r) => {
      setAnnees(r.data);
      const active = r.data.find((a) => a.active) || r.data[0];
      if (active) setAnnee(String(active.id)); else setChargement(false);
    }).catch((err) => { setErreur(formatApiError(err)); setChargement(false); });
  }, []);

  useEffect(() => {
    if (!annee) return;
    setChargement(true);
    api.get('/school/classes/', { params: { annee } }).then((r) => {
      setClasses(r.data);
      setChoisies([]);
    }).catch((err) => setErreur(formatApiError(err))).finally(() => setChargement(false));
  }, [annee]);

  const config = DOCUMENTS[doc];
  const mode = config.mode || 'classes';
  const avecClasses = mode === 'classes' || mode === 'classes_facultatives';
  const avecEleves = useMemo(() => classes.filter((c) => (c.effectif || 0) > 0), [classes]);
  const basculer = (id) => setChoisies((c) => (c.includes(id) ? c.filter((x) => x !== id) : [...c, id]));
  const toutes = avecEleves.length > 0 && choisies.length === avecEleves.length;
  const selection = classes.filter((c) => choisies.includes(c.id));
  const nbEleves = selection.reduce((t, c) => t + (c.effectif || 0), 0);
  const quantite = doc === 'fiches' ? selection.length : nbEleves;

  const imprimer = async () => {
    setErreur('');
    setEnvoi(true);
    let corps = { classes: choisies, ordre };
    if (doc === 'bulletins') corps.trimestre = trimestre;
    if (doc === 'fiches') corps.semaine = semaine;
    if (mode === 'classes_facultatives') {
      corps = { annee: Number(annee) };
      if (choisies.length) corps.classes = choisies;
      if (au) corps.au = au;
    } else if (mode === 'periode') {
      corps = periode === 'annee' ? { annee: Number(annee) } : { date_debut: dates.debut, date_fin: dates.fin };
    } else if (mode === 'mois') {
      corps = { mois };
    }
    try {
      await ouvrirPdf(config.chemin, corps);
    } catch (e) { setErreur(e.message); }
    setEnvoi(false);
  };

  return (
    <div className="page">
      <PageHeader titre="Impressions"
        sousTitre="Choisissez le document, puis une, plusieurs ou toutes les classes : un seul PDF réunit tout, prêt à imprimer." />
      {erreur && <div className="error">{erreur}</div>}

      <div className="docs-choix" role="group" aria-label="Document à imprimer">
        {Object.entries(DOCUMENTS).map(([cle, d]) => (
          <button key={cle} type="button" className={`doc-tuile ${doc === cle ? 'actif' : ''}`}
            aria-pressed={doc === cle} onClick={() => setDoc(cle)}>
            <span className="icone-doc"><Icon nom={d.icone} taille={22} /></span>
            <strong>{d.titre}</strong>
            <span className="aide">{d.aide}</span>
          </button>
        ))}
      </div>

      <div className="card">
        <div className="form-row">
          {mode !== 'mois' && (
          <div className="form-group">
            <label htmlFor="im-annee">Année scolaire</label>
            <select id="im-annee" value={annee} onChange={(e) => setAnnee(e.target.value)}>
              {annees.map((a) => <option key={a.id} value={a.id}>{a.libelle}{a.active ? ' (en cours)' : ''}</option>)}
            </select>
          </div>
          )}
          {doc === 'bulletins' && (
            <div className="form-group">
              <label>Période</label>
              <Segmented label="Période du bulletin" valeur={trimestre} onChange={setTrimestre}
                options={TRIMESTRES.map((t) => ({ value: t.value, label: t.label }))} />
            </div>
          )}
          {doc === 'fiches' && (
            <div className="form-group">
              <label htmlFor="im-semaine">Semaine du</label>
              <input id="im-semaine" type="date" value={semaine} onChange={(e) => setSemaine(e.target.value)} />
            </div>
          )}
          {avecClasses && mode === 'classes' && (
            <div className="form-group">
              <label htmlFor="im-ordre">Ordre des élèves</label>
              <select id="im-ordre" value={ordre} onChange={(e) => setOrdre(e.target.value)}>
                <option value="alpha">Alphabétique</option>
                <option value="numero">Par numéro</option>
              </select>
            </div>
          )}
          {doc === 'impayes' && (
            <div className="form-group">
              <label htmlFor="im-au">Situation jusqu'au mois</label>
              <input id="im-au" type="month" value={au} onChange={(e) => setAu(e.target.value)} />
              <small className="muted">Vide : jusqu'au mois en cours.</small>
            </div>
          )}
          {mode === 'periode' && (
            <>
              <div className="form-group">
                <label>Période</label>
                <Segmented label="Type de période" valeur={periode} onChange={setPeriode}
                  options={[{ value: 'annee', label: 'Année scolaire' }, { value: 'dates', label: 'Entre deux dates' }]} />
              </div>
              {periode === 'dates' && (
                <>
                  <div className="form-group"><label htmlFor="im-debut">Du</label>
                    <input id="im-debut" type="date" value={dates.debut} onChange={(e) => setDates({ ...dates, debut: e.target.value })} /></div>
                  <div className="form-group"><label htmlFor="im-fin">Au</label>
                    <input id="im-fin" type="date" value={dates.fin} onChange={(e) => setDates({ ...dates, fin: e.target.value })} /></div>
                </>
              )}
            </>
          )}
          {mode === 'mois' && (
            <div className="form-group">
              <label htmlFor="im-mois">Mois payé</label>
              <input id="im-mois" type="month" value={mois} onChange={(e) => setMois(e.target.value)} />
            </div>
          )}
        </div>
      </div>

      {avecClasses && (
      <div className="card">
        <div className="card-titre">
          <h3>Classes ({choisies.length} sélectionnée{choisies.length > 1 ? 's' : ''})</h3>
          <div className="actions-ligne">
            <button type="button" className="btn-secondary btn-compact"
              onClick={() => setChoisies(toutes ? [] : avecEleves.map((c) => c.id))}>
              {toutes ? 'Tout désélectionner' : 'Toutes les classes'}
            </button>
          </div>
        </div>

        {!chargement && classes.length === 0 ? (
          <EmptyState icone="classe" titre="Aucune classe pour cette année">
            <Link to="/admin/classes">Créez d'abord les classes</Link> et inscrivez les élèves.
          </EmptyState>
        ) : (
          <div className="grille-classes" role="group" aria-label="Classes à imprimer">
            {classes.map((c) => {
              const vide = (c.effectif || 0) === 0;
              const coche = choisies.includes(c.id);
              return (
                <label key={c.id} className={`tuile-classe ${coche ? 'cochee' : ''} ${vide ? 'desactivee' : ''}`}>
                  <input type="checkbox" checked={coche} disabled={vide} onChange={() => basculer(c.id)} />
                  <span className="tuile-nom">{c.nom}</span>
                  <span className="tuile-effectif">{vide ? 'Aucun élève' : `${c.effectif} élève${c.effectif > 1 ? 's' : ''}`}</span>
                </label>
              );
            })}
          </div>
        )}
      </div>
      )}

      <div className="barre-action-fixe">
        <div>
          {!avecClasses
            ? <span className="muted">Un seul PDF, prêt à imprimer.</span>
            : mode === 'classes_facultatives' && choisies.length === 0
            ? <span className="muted">Toutes les classes (ou cochez celles à inclure).</span>
            : choisies.length === 0
            ? <span className="muted">Sélectionnez au moins une classe.</span>
            : <><strong>{quantite}</strong> {config.unite}{quantite > 1 ? 's' : ''} · {choisies.length} classe{choisies.length > 1 ? 's' : ''}
              {doc === 'bulletins' && <> · {TRIMESTRES.find((t) => t.value === trimestre).label}</>}</>}
        </div>
        <button type="button" className="btn-primary btn-grand" disabled={(mode === 'classes' && choisies.length === 0) || (mode === 'periode' && periode === 'dates' && !(dates.debut && dates.fin)) || (mode === 'mois' && !mois) || envoi} onClick={imprimer}>
          <Icon nom="imprimante" taille={17} /> {envoi ? 'Préparation du PDF…' : `Imprimer : ${config.titre.toLowerCase()}`}
        </button>
      </div>
    </div>
  );
};

export default Impressions;

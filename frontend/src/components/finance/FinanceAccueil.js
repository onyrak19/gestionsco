import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../../api/axios';
import { formatApiError } from '../../utils/errors';
import { ouvrirPdf } from '../../utils/pdf';
import { dateFr } from '../../utils/argent';
import useAnnees from '../../hooks/useAnnees';
import useFinance from '../../hooks/useFinance';
import PageHeader from '../ui/PageHeader';
import SelectAnnee from '../ui/SelectAnnee';
import Segmented from '../ui/Segmented';
import Icon from '../ui/Icon';
import EmptyState from '../ui/EmptyState';

const TYPES = { droit: "Droits d'inscription", ecolage: 'Écolages', autre: 'Autres frais' };

// Bilan : entrées, dépenses (imprévus, salaires, avances) et solde d'une année ou d'une période
const FinanceAccueil = () => {
  const { argent } = useFinance();
  const { annees, annee, setAnnee, pret } = useAnnees();
  const [mode, setMode] = useState('annee');
  const [debut, setDebut] = useState('');
  const [fin, setFin] = useState('');
  const [bilan, setBilan] = useState(null);
  const [erreur, setErreur] = useState('');
  const [envoi, setEnvoi] = useState(false);

  const params = useCallback(() => (mode === 'annee' ? { annee } : { date_debut: debut, date_fin: fin }), [mode, annee, debut, fin]);
  const pretACharger = mode === 'annee' ? !!annee : !!(debut && fin);

  useEffect(() => {
    if (!pretACharger) return;
    setErreur('');
    api.get('/finance/bilan/', { params: params() }).then((r) => setBilan(r.data))
      .catch((err) => { setBilan(null); setErreur(formatApiError(err)); });
  }, [params, pretACharger]);

  const imprimer = async () => {
    setErreur(''); setEnvoi(true);
    try { await ouvrirPdf('/finance/pdf/rapport/', params()); } catch (e) { setErreur(e.message); }
    setEnvoi(false);
  };

  const maxMois = bilan ? Math.max(1, ...bilan.par_mois.map((m) => Math.max(m.entrees, m.depenses))) : 1;

  return (
    <div className="page">
      <PageHeader titre="Bilan financier"
        sousTitre="Entrées, dépenses et solde de l'établissement. Les montants des élèves et des salaires viennent des tarifs : jamais saisis à la main.">
        <button type="button" className="btn-secondary" disabled={!bilan || envoi} onClick={imprimer}>
          <Icon nom="imprimante" taille={16} /> {envoi ? 'Préparation…' : 'Rapport financier (PDF)'}
        </button>
        <Link className="btn-primary" to="/admin/finances/encaissements"><Icon nom="argent" taille={16} /> Encaisser un élève</Link>
      </PageHeader>
      {erreur && <div className="error">{erreur}</div>}

      <div className="raccourcis" style={{ marginBottom: 18 }}>
        <Link className="btn-secondary" to="/admin/finances/depenses"><Icon nom="montee" taille={16} /> Saisir une dépense</Link>
        <Link className="btn-secondary" to="/admin/finances/salaires"><Icon nom="portefeuille" taille={16} /> Payer les salaires</Link>
        <Link className="btn-secondary" to="/admin/finances/tarifs"><Icon nom="etiquette" taille={16} /> Tarifs</Link>
      </div>

      <div className="card">
        <div className="form-row">
          <div className="form-group">
            <label>Période du bilan</label>
            <Segmented label="Type de période" valeur={mode} onChange={setMode}
              options={[{ value: 'annee', label: 'Année scolaire' }, { value: 'dates', label: 'Entre deux dates' }]} />
          </div>
          {mode === 'annee' ? (
            pret && <SelectAnnee id="bi-annee" annees={annees} valeur={annee} onChange={setAnnee} />
          ) : (
            <>
              <div className="form-group"><label htmlFor="bi-debut">Du</label>
                <input id="bi-debut" type="date" value={debut} onChange={(e) => setDebut(e.target.value)} /></div>
              <div className="form-group"><label htmlFor="bi-fin">Au</label>
                <input id="bi-fin" type="date" value={fin} onChange={(e) => setFin(e.target.value)} /></div>
            </>
          )}
        </div>
      </div>

      {!bilan ? (
        !erreur && <EmptyState icone="argent" titre="Aucun bilan à afficher">Choisissez une année scolaire ou une période.</EmptyState>
      ) : (
        <>
          <p className="muted">Du {dateFr(bilan.periode.debut)} au {dateFr(bilan.periode.fin)}</p>
          <div className="chiffres">
            <div className="chiffre"><strong className="montant-grand">{argent(bilan.entrees.total)}</strong><span>Total des entrées</span></div>
            <div className="chiffre"><strong className="montant-grand">{argent(bilan.depenses.total)}</strong><span>Total des dépenses</span></div>
            <div className="chiffre">
              <strong className={`montant-grand ${bilan.solde < 0 ? 'solde-neg' : 'solde-pos'}`}>{argent(bilan.solde)}</strong>
              <span>Solde de la période</span>
            </div>
          </div>

          <div className="grille-2">
            <section className="card">
              <h3>Entrées</h3>
              <table className="data-table"><tbody>
                {Object.entries(TYPES).map(([cle, nom]) => (
                  <tr key={cle}><td>{nom}</td><td className="montant">{argent(bilan.entrees.scolarite[cle])}</td></tr>
                ))}
                <tr className="ligne-total"><td>Payé par les élèves</td><td className="montant">{argent(bilan.entrees.scolarite.total)}</td></tr>
                {bilan.entrees.autres.map((c) => (
                  <tr key={c.categorie}><td>{c.categorie}</td><td className="montant">{argent(c.total)}</td></tr>
                ))}
                <tr className="ligne-total"><td>Autres entrées d'argent</td><td className="montant">{argent(bilan.entrees.total_autres)}</td></tr>
              </tbody></table>
            </section>

            <section className="card">
              <h3>Dépenses</h3>
              <table className="data-table"><tbody>
                {bilan.depenses.categories.map((c) => (
                  <tr key={c.categorie}><td>{c.categorie}</td><td className="montant">{argent(c.total)}</td></tr>
                ))}
                <tr className="ligne-total"><td>Fonctionnement</td><td className="montant">{argent(bilan.depenses.total_fonctionnement)}</td></tr>
                <tr><td>dont imprévus ({bilan.depenses.nb_imprevus})</td><td className="montant muted">{argent(bilan.depenses.imprevus)}</td></tr>
                <tr><td>Salaires payés (net)</td><td className="montant">{argent(bilan.depenses.salaires)}</td></tr>
                <tr><td>Avances sur salaire</td><td className="montant">{argent(bilan.depenses.avances)}</td></tr>
              </tbody></table>
            </section>
          </div>

          <section className="card">
            <h3>Mois par mois</h3>
            {bilan.par_mois.length === 0 ? <p className="muted">Aucune opération sur cette période.</p> : (
              <div className="table-wrap">
                <table className="data-table">
                  <thead><tr><th>Mois</th><th>Entrées</th><th>Dépenses</th><th></th><th>Solde</th></tr></thead>
                  <tbody>
                    {bilan.par_mois.map((m) => (
                      <tr key={m.mois}>
                        <td>{m.libelle}</td>
                        <td className="montant">{argent(m.entrees)}</td>
                        <td className="montant">{argent(m.depenses)}</td>
                        <td className="barres-mois" aria-hidden="true">
                          <span className="barre-entree" style={{ width: `${(m.entrees / maxMois) * 100}%` }} />
                          <span className="barre-depense" style={{ width: `${(m.depenses / maxMois) * 100}%` }} />
                        </td>
                        <td className={`montant ${m.solde < 0 ? 'solde-neg' : 'solde-pos'}`}>{argent(m.solde)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
};

export default FinanceAccueil;

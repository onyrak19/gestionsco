import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../../api/axios';
import { formatApiError } from '../../utils/errors';
import { ouvrirPdf } from '../../utils/pdf';
import { libelleMois } from '../../utils/argent';
import useAnnees from '../../hooks/useAnnees';
import useFinance from '../../hooks/useFinance';
import PageHeader from '../ui/PageHeader';
import SelectAnnee from '../ui/SelectAnnee';
import EmptyState from '../ui/EmptyState';
import Icon from '../ui/Icon';

// Situation de paiement de tous les élèves d'une année : qui doit quoi, à ce jour
const Encaissements = () => {
  const navigate = useNavigate();
  const { argent } = useFinance();
  const { annees, annee, setAnnee, pret, erreur: erreurAnnees } = useAnnees();
  const [classes, setClasses] = useState([]);
  const [classe, setClasse] = useState('');
  const [statut, setStatut] = useState('');
  const [q, setQ] = useState('');
  const [donnees, setDonnees] = useState({ eleves: [], total_du: 0 });
  const [erreur, setErreur] = useState('');
  const [chargement, setChargement] = useState(false);
  const [envoi, setEnvoi] = useState('');

  useEffect(() => {
    if (!annee) return;
    setClasse('');
    api.get('/school/classes/', { params: { annee } }).then((r) => setClasses(r.data)).catch(() => {});
  }, [annee]);

  const charger = useCallback(() => {
    if (!annee) return Promise.resolve();
    setChargement(true);
    const params = { annee };
    if (classe) params.classe = classe;
    if (statut) params.statut = statut;
    if (q.trim()) params.q = q.trim();
    return api.get('/finance/situations/', { params })
      .then((r) => { setDonnees(r.data); setErreur(''); })
      .catch((err) => setErreur(formatApiError(err)))
      .finally(() => setChargement(false));
  }, [annee, classe, statut, q]);

  useEffect(() => {
    const t = setTimeout(charger, q ? 300 : 0);
    return () => clearTimeout(t);
  }, [charger, q]);

  const imprimer = async (type) => {
    setErreur(''); setEnvoi(type);
    try {
      const inscriptions = donnees.eleves.map((e) => e.inscription);
      if (type === 'cartes') await ouvrirPdf('/finance/pdf/cartes-ecolage/', { inscriptions });
      else await ouvrirPdf('/finance/pdf/impayes/', { annee, classes: classe ? [Number(classe)] : undefined });
    } catch (e) { setErreur(e.message); }
    setEnvoi('');
  };

  return (
    <div className="page">
      <PageHeader titre="Encaissements"
        sousTitre="Cliquez sur un élève pour voir ses mois payés et non payés, puis encaisser. Le montant vient du tarif de son niveau.">
        <button type="button" className="btn-secondary" disabled={!donnees.eleves.length || !!envoi} onClick={() => imprimer('impayes')}>
          <Icon nom="imprimante" taille={16} /> {envoi === 'impayes' ? 'Préparation…' : 'Liste des impayés'}
        </button>
        <button type="button" className="btn-secondary" disabled={!donnees.eleves.length || !!envoi} onClick={() => imprimer('cartes')}>
          <Icon nom="carte" taille={16} /> {envoi === 'cartes' ? 'Préparation…' : "Cartes d'écolage"}
        </button>
      </PageHeader>
      {(erreur || erreurAnnees) && <div className="error">{erreur || erreurAnnees}</div>}

      <div className="card">
        <div className="form-row">
          {pret && <SelectAnnee id="en-annee" annees={annees} valeur={annee} onChange={setAnnee} />}
          <div className="form-group">
            <label htmlFor="en-classe">Classe</label>
            <select id="en-classe" value={classe} onChange={(e) => setClasse(e.target.value)}>
              <option value="">Toutes les classes</option>
              {classes.map((c) => <option key={c.id} value={c.id}>{c.nom}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label htmlFor="en-statut">Situation</label>
            <select id="en-statut" value={statut} onChange={(e) => setStatut(e.target.value)}>
              <option value="">Tous les élèves</option>
              <option value="impayes">Avec des impayés</option>
              <option value="a_jour">À jour</option>
            </select>
          </div>
          <div className="form-group">
            <label htmlFor="en-q">Recherche</label>
            <input id="en-q" type="search" placeholder="Nom, prénom ou matricule" value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-titre">
          <h3>{donnees.eleves.length} élève{donnees.eleves.length > 1 ? 's' : ''}</h3>
          <span>Total dû à ce jour : <strong className="solde-neg">{argent(donnees.total_du)}</strong></span>
        </div>
        {!chargement && donnees.eleves.length === 0 ? (
          <EmptyState icone="eleve" titre="Aucun élève">Aucun élève inscrit ne correspond à ces critères.</EmptyState>
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead><tr><th>Élève</th><th>Classe</th><th>Parent / tuteur</th><th>Écolage</th><th>Mois impayés</th><th>Dû à ce jour</th></tr></thead>
              <tbody>
                {donnees.eleves.map((e) => (
                  <tr key={e.inscription} className="cliquable" onClick={() => navigate(`/admin/finances/eleves/${e.inscription}`)}>
                    <td><strong>{e.nom}</strong> {e.prenom}<br /><small className="muted">{e.matricule}</small></td>
                    <td>{e.classe_nom}</td>
                    <td>{e.parent_nom || <span className="muted">—</span>}{e.parent_mobile && <><br /><small className="muted">{e.parent_mobile}</small></>}</td>
                    <td>{e.tarif_defini ? argent(e.ecolage_mensuel) : <span className="badge badge-pay-non_defini">Tarif non défini</span>}</td>
                    <td>
                      {e.nb_mois_impayes > 0
                        ? <span title={e.mois_impayes.map(libelleMois).join(', ')} className="badge badge-pay-impaye">{e.nb_mois_impayes} mois</span>
                        : e.tarif_defini ? <span className="badge badge-pay-paye">À jour</span> : null}
                    </td>
                    <td className={`montant ${e.du_a_ce_jour > 0 ? 'solde-neg' : ''}`}>{argent(e.du_a_ce_jour)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default Encaissements;

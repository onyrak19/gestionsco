import React, { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import api from '../../api/axios';
import { formatApiError } from '../../utils/errors';
import { ouvrirPdfGet } from '../../utils/pdf';
import { dateFr } from '../../utils/argent';
import useFinance from '../../hooks/useFinance';
import Icon from '../ui/Icon';
import PageHeader from '../ui/PageHeader';
import StatutPaiement from '../ui/StatutPaiement';
import EncaisserModal from './EncaisserModal';
import AnnulerModal from './AnnulerModal';

// Situation financière d'un élève : droit, écolage mois par mois, autres frais, historique
const SituationEleve = () => {
  const { id } = useParams();
  const { argent } = useFinance();
  const [sit, setSit] = useState(null);
  const [paiements, setPaiements] = useState([]);
  const [erreur, setErreur] = useState('');
  const [message, setMessage] = useState('');
  const [encaisser, setEncaisser] = useState(null);     // type initial ou '' ; null = fermé
  const [aAnnuler, setAAnnuler] = useState(null);

  const charger = useCallback(() => Promise.all([
    api.get(`/finance/inscriptions/${id}/situation/`),
    api.get('/finance/paiements/', { params: { inscription: id } }),
  ]).then(([s, p]) => { setSit(s.data); setPaiements(p.data.paiements); })
    .catch((err) => setErreur(formatApiError(err))), [id]);
  useEffect(() => { charger(); }, [charger]);

  const recu = async (p) => {
    setErreur('');
    try { await ouvrirPdfGet(`/finance/paiements/${p.id}/recu/`); } catch (e) { setErreur(e.message); }
  };

  if (!sit) {
    return <div className="page"><h1>Situation de l'élève</h1>{erreur ? <div className="error">{erreur}</div> : <p className="loading">Chargement…</p>}</div>;
  }
  const { eleve, classe, droit, ecolage, autres } = sit;
  const nomEleve = `${eleve.nom} ${eleve.prenom}`;

  return (
    <div className="page">
      <p><Link to="/admin/finances/encaissements" className="lien-retour"><Icon nom="gauche" taille={15} /> Encaissements</Link></p>
      <PageHeader titre={nomEleve}
        sousTitre={<>{classe.nom} · année {sit.annee} · matricule {eleve.matricule || '—'}
          {eleve.parent_nom && <> · parent : {eleve.parent_nom}{eleve.parent_mobile && ` (${eleve.parent_mobile})`}</>}</>}>
        <button type="button" className="btn-primary" disabled={!sit.tarif_defini} onClick={() => setEncaisser('')}>
          <Icon nom="argent" taille={16} /> Encaisser
        </button>
      </PageHeader>
      {erreur && <div className="error">{erreur}</div>}
      {message && <div className="success">{message}</div>}
      {!sit.tarif_defini && (
        <div className="info alerte">Aucun tarif n'est défini pour ce niveau. <Link to="/admin/finances/tarifs">Définir les tarifs</Link> pour pouvoir encaisser.</div>
      )}

      <div className="chiffres">
        <div className="chiffre"><strong className="montant-grand">{argent(sit.total_paye)}</strong><span>Déjà payé</span></div>
        <div className="chiffre"><strong className={`montant-grand ${sit.du_a_ce_jour > 0 ? 'solde-neg' : 'solde-pos'}`}>{argent(sit.du_a_ce_jour)}</strong><span>Dû à ce jour</span></div>
        <div className="chiffre"><strong className="montant-grand">{argent(sit.reste_annee)}</strong><span>Reste pour l'année</span></div>
      </div>

      <section className="card">
        <div className="card-titre">
          <h3>Droit d'inscription</h3>
          {droit.montant !== null && !droit.paye && (
            <button type="button" className="btn-small btn-secondary" onClick={() => setEncaisser('droit')}>Encaisser le droit</button>
          )}
        </div>
        {droit.montant === null ? <p className="muted">Tarif non défini.</p> : (
          <p><strong>{argent(droit.montant)}</strong> <StatutPaiement statut={droit.paye ? 'paye' : 'impaye'} />
            {droit.paye && <small className="muted"> · reçu {droit.numero_recu} du {dateFr(droit.date_paiement)}</small>}</p>
        )}
      </section>

      <section className="card">
        <div className="card-titre">
          <h3>Écolage {ecolage.mensuel !== null && <small className="muted">({argent(ecolage.mensuel)} par mois)</small>}</h3>
          <span className="muted">{ecolage.nb_payes} payé{ecolage.nb_payes > 1 ? 's' : ''} · {ecolage.nb_impayes} impayé{ecolage.nb_impayes > 1 ? 's' : ''}</span>
        </div>
        <div className="mois-statuts">
          {ecolage.mois.map((m) => (
            <div key={m.mois} className={`mois-carte mois-${m.statut}`}>
              <strong>{m.libelle}</strong>
              <StatutPaiement statut={m.statut} />
              <small>{m.statut === 'paye' ? `Reçu ${m.numero_recu}` : m.montant !== null ? argent(m.montant) : ''}</small>
            </div>
          ))}
        </div>
      </section>

      {autres.length > 0 && (
        <section className="card">
          <h3>Autres frais</h3>
          <table className="data-table"><tbody>
            {autres.map((a) => (
              <tr key={a.tarif}>
                <td>{a.libelle}</td><td className="montant">{argent(a.montant)}</td>
                <td><StatutPaiement statut={a.paye ? 'paye' : 'impaye'} /></td>
                <td>{!a.paye && <button type="button" className="btn-small btn-secondary" onClick={() => setEncaisser('autre')}>Encaisser</button>}</td>
              </tr>
            ))}
          </tbody></table>
        </section>
      )}

      <section className="card">
        <h3>Paiements enregistrés</h3>
        {paiements.length === 0 ? <p className="muted">Aucun paiement pour le moment.</p> : (
          <div className="table-wrap">
            <table className="data-table">
              <thead><tr><th>Reçu</th><th>Date</th><th>Détail</th><th>Montant</th><th></th></tr></thead>
              <tbody>
                {paiements.map((p) => (
                  <tr key={p.id} className={p.annule ? 'ligne-annulee' : ''}>
                    <td>{p.numero}{p.annule && <> <StatutPaiement statut="annule" /></>}</td>
                    <td>{dateFr(p.date)}</td>
                    <td>{p.lignes.map((l) => l.libelle).join(', ')}<br /><small className="muted">{p.mode_libelle}{p.annule && ` · ${p.motif_annulation}`}</small></td>
                    <td className="montant">{argent(p.montant_total)}</td>
                    <td>
                      <button type="button" className="btn-small btn-secondary" onClick={() => recu(p)}><Icon nom="recu" taille={14} /> Reçu</button>
                      {!p.annule && <button type="button" className="btn-small btn-danger" onClick={() => setAAnnuler(p)}>Annuler</button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {encaisser !== null && (
        <EncaisserModal inscription={Number(id)} situation={sit} typeInitial={encaisser || undefined}
          onClose={() => setEncaisser(null)}
          onDone={(p) => {
            setEncaisser(null);
            setMessage(`Paiement de ${argent(p.montant_total)} enregistré — reçu ${p.numero}.`);
            charger();
            recu(p);
          }} />
      )}
      {aAnnuler && (
        <AnnulerModal titre={`Annuler le paiement ${aAnnuler.numero}`}
          description={`Le paiement de ${argent(aAnnuler.montant_total)} restera visible, barré « annulé », et les mois redeviendront impayés.`}
          envoyer={(motif) => api.post(`/finance/paiements/${aAnnuler.id}/annuler/`, { motif })}
          onClose={() => setAAnnuler(null)}
          onDone={() => { setAAnnuler(null); setMessage('Paiement annulé.'); charger(); }} />
      )}
    </div>
  );
};

export default SituationEleve;

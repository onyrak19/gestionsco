import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../../api/axios';
import { formatApiError } from '../../utils/errors';
import { libelleJour, heure } from '../../utils/dates';
import Icon from '../ui/Icon';
import PageHeader from '../ui/PageHeader';
import Compteur from '../ui/Compteur';

// L'historique est masqué par défaut ; le choix de l'afficher est mémorisé sur cet appareil
const lireChoixHistorique = () => {
  try { return localStorage.getItem('accueil_historique') === '1'; } catch (e) { return false; }
};

const AdminDashboard = () => {
  const [erreur, setErreur] = useState('');
  const [chargement, setChargement] = useState(true);
  const [annee, setAnnee] = useState(null);
  const [classes, setClasses] = useState([]);
  const [affectations, setAffectations] = useState(0);
  const [activite, setActivite] = useState(null);   // null : pas encore chargé
  const [historique, setHistorique] = useState(lireChoixHistorique);
  const [stats, setStats] = useState({ annees: 0, eleves: 0, enseignants: 0, attente: 0 });

  useEffect(() => {
    api.get('/school/annees/').then(async (a) => {
      const active = a.data.find((x) => x.active) || null;
      setAnnee(active);
      const parAnnee = active ? { annee: active.id } : {};
      const [c, e, ens, att, aff] = await Promise.all([
        api.get('/school/classes/', { params: parAnnee }),
        api.get('/school/eleves/'),
        api.get('/auth/enseignants/', { params: { statut: 'valide' } }),
        api.get('/auth/enseignants/', { params: { statut: 'en_attente' } }),
        api.get('/school/affectations/', { params: parAnnee }),
      ]);
      setClasses(c.data);
      setAffectations(aff.data.length);
      setStats({ annees: a.data.length, eleves: e.data.length, enseignants: ens.data.length, attente: att.data.length });
    })
      .catch((err) => setErreur(formatApiError(err, 'Impossible de charger les statistiques.')))
      .finally(() => setChargement(false));
  }, []);

  // Le journal n'est interrogé que si on choisit de l'afficher
  useEffect(() => {
    if (!historique) return;
    api.get('/journal/', { params: { page_size: 6 } })
      .then((r) => setActivite(r.data.results || []))
      .catch(() => setActivite([]));
  }, [historique]);

  const basculerHistorique = () => {
    const suivant = !historique;
    setHistorique(suivant);
    try { localStorage.setItem('accueil_historique', suivant ? '1' : '0'); } catch (e) { /* ignoré */ }
  };

  const nonConfigurees = classes.filter((c) => c.niveau && !c.configuree);
  const sansNiveau = classes.filter((c) => !c.niveau);
  const inscrits = classes.reduce((t, c) => t + (c.effectif || 0), 0);

  const etapes = [
    { fait: !!annee, titre: 'Activer une année scolaire', lien: '/admin/annees', action: 'Ouvrir' },
    { fait: classes.length > 0, titre: 'Créer les classes', lien: '/admin/classes', action: 'Ouvrir' },
    {
      fait: classes.length > 0 && nonConfigurees.length === 0,
      titre: 'Choisir les matières et coefficients de chaque classe',
      lien: nonConfigurees[0] ? `/admin/classes/${nonConfigurees[0].id}/config` : '/admin/classes',
      action: 'Configurer',
    },
    { fait: inscrits > 0, titre: 'Inscrire les élèves', lien: '/admin/inscriptions', action: 'Inscrire' },
    {
      fait: stats.enseignants > 0 && affectations > 0,
      titre: 'Valider les enseignants et les affecter à leurs matières',
      lien: stats.enseignants > 0 ? '/admin/affectations' : '/admin/enseignants',
      action: 'Affecter',
    },
  ];
  const restantes = etapes.filter((e) => !e.fait);
  const prochaine = restantes[0];

  return (
    <div className="page">
      <PageHeader
        titre="Scolarité"
        sousTitre={annee
          ? <>Année scolaire en cours : <strong>{annee.libelle}</strong></>
          : <>Aucune année scolaire active. <Link to="/admin/annees">Créez ou activez une année</Link></>}
      >
        <Link className="btn-primary" to="/admin/inscriptions"><Icon nom="plus" taille={16} /> Inscrire un élève</Link>
      </PageHeader>
      {erreur && <div className="error">{erreur}</div>}

      {stats.attente > 0 && (
        <div className="info alerte">
          <strong>{stats.attente}</strong> demande{stats.attente > 1 ? 's' : ''} d'enseignant en attente de validation.{' '}
          <Link to="/admin/enseignants">Valider</Link>
        </div>
      )}
      {sansNiveau.length > 0 && (
        <div className="info alerte">
          {sansNiveau.length} classe{sansNiveau.length > 1 ? 's' : ''} sans niveau défini (anciennes classes) :{' '}
          <Link to="/admin/classes">modifiez-les</Link> pour activer les règles de passage et la configuration des matières.
        </div>
      )}

      <div className="chiffres">
        <Link to="/admin/classes" className="chiffre"><strong><Compteur valeur={classes.length} /></strong><span>classes cette année</span></Link>
        <Link to="/admin/inscriptions" className="chiffre"><strong><Compteur valeur={inscrits} /></strong><span>élèves inscrits</span></Link>
        <Link to="/admin/eleves" className="chiffre"><strong><Compteur valeur={stats.eleves} /></strong><span>élèves enregistrés</span></Link>
        <Link to="/admin/enseignants" className="chiffre"><strong><Compteur valeur={stats.enseignants} /></strong><span>enseignants validés</span></Link>
        <Link to="/admin/annees" className="chiffre"><strong><Compteur valeur={stats.annees} /></strong><span>années scolaires</span></Link>
      </div>

      <div className="grille-2">
        <section className="card">
          <h3>{restantes.length ? 'Pour démarrer' : 'Tout est en place'}</h3>
          {chargement ? <p className="muted">Chargement…</p> : (
            <>
              {!restantes.length && <p className="muted">L’année est prête : vous pouvez saisir les notes et imprimer les bulletins.</p>}
              <ol className="etapes">
                {etapes.map((e) => (
                  <li key={e.titre} className={e.fait ? 'fait' : (e === prochaine ? 'prochaine' : '')}>
                    <span className="etape-puce">{e.fait ? <Icon nom="valider" taille={14} /> : null}</span>
                    <span className="etape-texte">{e.titre}</span>
                    {!e.fait && e === prochaine && <Link className="btn-primary btn-compact" to={e.lien}>{e.action}</Link>}
                  </li>
                ))}
              </ol>
            </>
          )}
        </section>

        <section className="card">
          <h3>Accès rapides</h3>
          <div className="raccourcis">
            <Link className="btn-secondary" to="/admin/notes"><Icon nom="crayon" taille={16} /> Saisir des notes</Link>
            <Link className="btn-secondary" to="/admin/releves"><Icon nom="tableau" taille={16} /> Relevés de classe</Link>
            <Link className="btn-secondary" to="/admin/impressions"><Icon nom="imprimante" taille={16} /> Impressions</Link>
            <Link className="btn-secondary" to="/admin/eleves"><Icon nom="eleve" taille={16} /> Liste des élèves</Link>
            <Link className="btn-secondary" to="/admin/classes"><Icon nom="classe" taille={16} /> Classes</Link>
          </div>
        </section>
      </div>

      <section className={`card repliable ${historique ? 'ouvert' : ''}`}>
        <button type="button" className="repliable-entete" aria-expanded={historique} onClick={basculerHistorique}>
          <Icon nom="chevron" taille={18} className="chevron" />
          <strong>Dernières actions</strong>
          <span className="muted">{historique ? 'Masquer l’historique' : 'Afficher l’historique récent'}</span>
        </button>
        {historique && (
          <div className="repliable-corps">
            {activite === null ? <p className="muted">Chargement…</p> : activite.length === 0 ? (
              <p className="muted">Aucune action enregistrée pour le moment.</p>
            ) : (
              <ul className="fil-activite">
                {activite.map((a) => (
                  <li key={a.id}>
                    <time>{libelleJour(a.date)} · {heure(a.date)}</time>
                    <span>{a.description}</span>
                  </li>
                ))}
              </ul>
            )}
            <p><Link to="/admin/journal" className="lien-discret">Ouvrir le journal complet</Link></p>
          </div>
        )}
      </section>
    </div>
  );
};

export default AdminDashboard;

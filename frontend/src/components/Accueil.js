import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../api/axios';
import { useAuth } from '../context/AuthContext';
import { lirePagesRecentes } from '../utils/navigation';
import Icon from './ui/Icon';

const salut = () => (new Date().getHours() < 18 ? 'Bonjour' : 'Bonsoir');

const dateDuJour = () => {
  const d = new Date().toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
  return d.charAt(0).toUpperCase() + d.slice(1);
};

const ESPACES_ACCUEIL = [
  {
    cle: 'scolarite', titre: 'Scolarité', icone: 'eleve', to: '/admin/scolarite',
    texte: 'Élèves, inscriptions, classes, notes et bulletins.',
    liens: [
      ['/admin/inscriptions', 'Inscrire un élève', 'plus'],
      ['/admin/notes', 'Saisir des notes', 'crayon'],
      ['/admin/impressions', 'Imprimer des bulletins', 'imprimante'],
    ],
  },
  {
    cle: 'finances', titre: 'Finances', icone: 'argent', to: '/admin/finances',
    texte: 'Encaissements, reçus, dépenses et salaires.',
    liens: [
      ['/admin/finances/encaissements', 'Encaisser un élève', 'argent'],
      ['/admin/finances/depenses', 'Saisir une dépense', 'montee'],
      ['/admin/finances/salaires', 'Payer les salaires', 'portefeuille'],
    ],
  },
];

// Page d'accueil de l'administration : on choisit l'espace de travail (scolarité ou finances)
const Accueil = () => {
  const { user } = useAuth();
  const [attente, setAttente] = useState(0);
  const [recentes] = useState(lirePagesRecentes);

  useEffect(() => {
    api.get('/auth/enseignants/', { params: { statut: 'en_attente' } })
      .then((r) => setAttente(r.data.length))
      .catch(() => setAttente(0));
  }, []);

  return (
    <div className="page accueil">
      <header className="accueil-entete">
        <h1>{salut()}{user?.prenom ? `, ${user.prenom}` : ''}</h1>
        <p className="page-subtitle">{dateDuJour()}. Que souhaitez-vous faire ?</p>
      </header>

      {attente > 0 && (
        <div className="info alerte">
          <strong>{attente}</strong> demande{attente > 1 ? 's' : ''} d'enseignant en attente de validation.{' '}
          <Link to="/admin/enseignants">Valider</Link>
        </div>
      )}

      <div className="espaces-cartes">
        {ESPACES_ACCUEIL.map((e) => (
          <section key={e.cle} className={`espace-carte espace-${e.cle}`}>
            <Link to={e.to} className="espace-carte-tete">
              <span className="espace-carte-icone"><Icon nom={e.icone} taille={30} /></span>
              <span>
                <h2>{e.titre}</h2>
                <span className="espace-carte-texte">{e.texte}</span>
              </span>
              <Icon nom="droite" taille={20} className="espace-carte-fleche" />
            </Link>
            <ul className="espace-carte-liens">
              {e.liens.map(([to, label, icone]) => (
                <li key={to}><Link to={to}><Icon nom={icone} taille={16} /> {label}</Link></li>
              ))}
            </ul>
          </section>
        ))}
      </div>

      <section className="card accueil-outils">
        <h3>Outils</h3>
        <div className="raccourcis">
          <Link className="btn-secondary" to="/admin/donnees"><Icon nom="tableur" taille={16} /> Import / Export Excel</Link>
          <Link className="btn-secondary" to="/admin/journal"><Icon nom="journal" taille={16} /> Journal d'activité</Link>
          <Link className="btn-secondary" to="/admin/parametres"><Icon nom="reglages" taille={16} /> Établissement</Link>
        </div>
      </section>

      {recentes.length > 0 && (
        <section className="card accueil-recentes">
          <h3>Reprendre là où vous en étiez</h3>
          <ul className="recentes">
            {recentes.map((p) => (
              <li key={p.to}>
                <Link to={p.to}><Icon nom="horloge" taille={16} /> <strong>{p.label}</strong> <small>{p.espace}</small></Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
};

export default Accueil;

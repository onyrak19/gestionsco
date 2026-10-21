import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../../api/axios';
import { useAuth } from '../../context/AuthContext';
import { formatApiError } from '../../utils/errors';
import Icon from '../ui/Icon';
import PageHeader from '../ui/PageHeader';
import EmptyState from '../ui/EmptyState';
import Compteur from '../ui/Compteur';

const EnseignantDashboard = () => {
  const { user } = useAuth();
  const [affectations, setAffectations] = useState([]);
  const [erreur, setErreur] = useState('');

  useEffect(() => {
    api.get('/school/affectations/mes/').then(r => setAffectations(r.data))
      .catch(err => setErreur(formatApiError(err)));
  }, []);

  return (
    <div className="page">
      <PageHeader titre={`Bonjour ${user?.prenom || user?.nom || user?.username}`} sousTitre="Bienvenue dans votre espace enseignant.">
        <Link to="/enseignant/notes" className="btn-primary"><Icon nom="crayon" taille={16} /> Saisir des notes</Link>
      </PageHeader>
      {erreur && <div className="error">{erreur}</div>}

      <div className="chiffres">
        <div className="chiffre"><strong><Compteur valeur={affectations.length} /></strong><span>Mes affectations</span></div>
        <div className="chiffre"><strong><Compteur valeur={new Set(affectations.map(a => a.classe)).size} /></strong><span>Classes distinctes</span></div>
        <div className="chiffre"><strong><Compteur valeur={new Set(affectations.map(a => a.matiere)).size} /></strong><span>Matières enseignées</span></div>
      </div>

      <div className="card">
        <h3>Mes affectations</h3>
        {affectations.length === 0 ? (
          <EmptyState icone="lien" titre="Aucune affectation pour le moment">
            L'administration doit vous affecter à une classe et à une matière avant que vous puissiez saisir des notes.
          </EmptyState>
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead><tr><th>Classe</th><th>Matière</th></tr></thead>
              <tbody>
                {affectations.map(a => (
                  <tr key={a.id}>
                    <td>{a.classe_nom}</td>
                    <td>{a.matiere_nom}</td>
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

export default EnseignantDashboard;

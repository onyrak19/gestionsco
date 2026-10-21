import React, { useState } from 'react';
import { useNavigate, Link, Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { formatApiError } from '../utils/errors';
import Icon from './ui/Icon';

export const AuthPanneau = () => (
  <aside className="auth-panneau">
    <div className="auth-marque"><Icon nom="eleve" taille={26} /> Gestion Scolaire</div>
    <div className="auth-flottants" aria-hidden="true">
      <span className="flottant f1"><Icon nom="inscription" taille={16} /> Inscriptions</span>
      <span className="flottant f2"><Icon nom="crayon" taille={16} /> Notes et bulletins</span>
      <span className="flottant f3"><Icon nom="argent" taille={16} /> Encaissements</span>
    </div>
    <div className="auth-texte">
      <p className="auth-accroche">La scolarité et les finances, chacune à sa place.</p>
      <ul>
        <li>Saisie des notes élève par élève, enregistrée automatiquement</li>
        <li>Bulletins de toutes les classes en un seul PDF</li>
        <li>Encaissements, reçus et salaires dans un espace dédié</li>
      </ul>
    </div>
  </aside>
);

const Login = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [envoi, setEnvoi] = useState(false);
  const [voir, setVoir] = useState(false);
  const { login, user } = useAuth();
  const navigate = useNavigate();

  if (user) return <Navigate to={user.profile?.role === 'admin' ? '/admin' : '/enseignant'} />;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setEnvoi(true);
    try {
      const connecte = await login(username, password);
      navigate(connecte.profile?.role === 'admin' ? '/admin' : '/enseignant');
    } catch (err) {
      setError(err.response?.data?.error || formatApiError(err, 'Identifiants invalides'));
      setEnvoi(false);
    }
  };

  return (
    <div className="auth-page">
      <AuthPanneau />
      <main className="auth-formulaire">
        <div className="auth-carte">
          <h1>Connexion</h1>
          <p className="subtitle">Entrez vos identifiants pour accéder à votre espace.</p>
          {error && <div className="error" role="alert">{error}</div>}
          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label htmlFor="username">Nom d'utilisateur</label>
              <input id="username" autoComplete="username" value={username}
                onChange={(e) => setUsername(e.target.value)} required autoFocus />
            </div>
            <div className="form-group">
              <label htmlFor="password">Mot de passe</label>
              <div className="champ-mdp">
                <input id="password" autoComplete="current-password" type={voir ? 'text' : 'password'} value={password}
                  onChange={(e) => setPassword(e.target.value)} required />
                <button type="button" className="oeil-bouton" onClick={() => setVoir(!voir)} aria-pressed={voir}
                  aria-label={voir ? 'Masquer le mot de passe' : 'Afficher le mot de passe'}>
                  <Icon nom="oeil" taille={18} />
                </button>
              </div>
            </div>
            <button type="submit" className="btn-primary btn-bloc" disabled={envoi}>
              {envoi ? 'Connexion…' : 'Se connecter'}
            </button>
          </form>
          <p className="auth-lien">Enseignant ? <Link to="/inscription">Créer un compte</Link></p>
        </div>
      </main>
    </div>
  );
};

export default Login;

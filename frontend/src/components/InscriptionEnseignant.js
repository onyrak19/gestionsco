import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import api from '../api/axios';
import { formatApiError } from '../utils/errors';
import { AuthPanneau } from './Login';

const InscriptionEnseignant = () => {
  const [form, setForm] = useState({
    username: '', email: '', password: '', nom: '', prenom: '', telephone: ''
  });
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(''); setMessage('');
    try {
      await api.post('/auth/inscription-enseignant/', form);
      setMessage('Votre demande est enregistrée. Elle sera validée par l\'administration.');
      setTimeout(() => navigate('/login'), 3000);
    } catch (err) {
      setError(formatApiError(err));
    }
  };

  const ch = (e) => setForm({ ...form, [e.target.name]: e.target.value });

  return (
    <div className="auth-page">
      <AuthPanneau />
      <main className="auth-formulaire">
      <div className="auth-carte">
        <h1>Inscription enseignant</h1>
        <p className="subtitle">Votre compte sera activé après validation par l’administration.</p>
        {message && <div className="success">{message}</div>}
        {error && <div className="error">{error}</div>}
        <form onSubmit={handleSubmit}>
          <div className="form-group"><label htmlFor="nom">Nom *</label>
            <input id="nom" name="nom" value={form.nom} onChange={ch} required /></div>
          <div className="form-group"><label htmlFor="prenom">Prénom *</label>
            <input id="prenom" name="prenom" value={form.prenom} onChange={ch} required /></div>
          <div className="form-group"><label htmlFor="username">Nom d'utilisateur *</label>
            <input id="username" name="username" value={form.username} onChange={ch} required /></div>
          <div className="form-group"><label htmlFor="email">Email *</label>
            <input id="email" type="email" name="email" value={form.email} onChange={ch} required /></div>
          <div className="form-group"><label htmlFor="telephone">Téléphone</label>
            <input id="telephone" name="telephone" maxLength={30} value={form.telephone} onChange={ch} /></div>
          <div className="form-group"><label htmlFor="password">Mot de passe * (min. 8 caractères)</label>
            <input id="password" autoComplete="new-password" type="password" name="password" value={form.password} onChange={ch} required minLength={8} /></div>
          <button className="btn-primary btn-bloc" type="submit">Envoyer la demande</button>
        </form>
        <p className="auth-lien">Déjà inscrit ? <Link to="/login">Se connecter</Link></p>
      </div>
      </main>
    </div>
  );
};

export default InscriptionEnseignant;
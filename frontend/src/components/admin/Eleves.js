import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../../api/axios';
import { formatApiError } from '../../utils/errors';
import DecisionBadge from '../ui/DecisionBadge';
import Icon from '../ui/Icon';
import PageHeader from '../ui/PageHeader';
import EmptyState from '../ui/EmptyState';
import PhotoPicker from '../ui/PhotoPicker';
import Avatar from '../ui/Avatar';

const FORM_VIDE = {
  nom: '', prenom: '', date_naissance: '', sexe: 'M',
  parent_nom: '', parent_mobile: '', parent2_nom: '', parent2_mobile: '',
};
const CHAMPS_PARENTS = ['parent_nom', 'parent_mobile', 'parent2_nom', 'parent2_mobile'];

const Eleves = () => {
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [form, setForm] = useState(FORM_VIDE);
  const [photo, setPhoto] = useState(null);          // facultative
  const [search, setSearch] = useState('');
  const [ordre, setOrdre] = useState('alpha');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const load = useCallback(
    () => api.get('/school/eleves/', { params: { search, ordre } }).then(r => setItems(r.data))
      .catch(err => setError(formatApiError(err))),
    [search, ordre]
  );
  useEffect(() => { load(); }, [load]);

  const create = async (e) => {
    e.preventDefault();
    setError(''); setMessage('');
    try {
      let res;
      if (photo) {
        // avec photo : envoi en « multipart » (le fichier ne passe pas en JSON)
        const corps = new FormData();
        corps.append('nom', form.nom);
        corps.append('prenom', form.prenom);
        corps.append('sexe', form.sexe);
        CHAMPS_PARENTS.forEach((c) => { if (form[c]) corps.append(c, form[c]); });
        if (form.date_naissance) corps.append('date_naissance', form.date_naissance);
        corps.append('photo', photo);
        res = await api.post('/school/eleves/', corps, { headers: { 'Content-Type': 'multipart/form-data' } });
      } else {
        res = await api.post('/school/eleves/', { ...form, date_naissance: form.date_naissance || null });
      }
      setForm(FORM_VIDE);
      setPhoto(null);
      setMessage(`${res.data.nom} ${res.data.prenom} ajouté(e). Son matricule sera attribué à sa première inscription.`);
      load();
    } catch (err) { setError(formatApiError(err)); }
  };

  const supprimer = async (e, el) => {
    e.stopPropagation();
    if (!window.confirm(`Supprimer ${el.nom} ${el.prenom} ? Ses inscriptions et toutes ses notes seront aussi supprimées.`)) return;
    setError('');
    try { await api.delete(`/school/eleves/${el.id}/`); } catch (err) { setError(formatApiError(err)); }
    load();
  };

  return (
    <div className="page">
      <PageHeader titre="Élèves"
        sousTitre="Cliquez sur un élève pour voir son dossier : parcours, moyennes, décisions, bulletins et pièces jointes." />
      {error && <div className="error">{error}</div>}
      {message && <div className="success">{message}</div>}

      <div className="card">
        <h3>Nouvel élève</h3>
        <form onSubmit={create} className="crud-form">
          <div className="form-row">
            <div className="form-group"><label htmlFor="el-nom">Nom</label>
              <input id="el-nom" value={form.nom} required maxLength={100} onChange={(e) => setForm({ ...form, nom: e.target.value })} /></div>
            <div className="form-group"><label htmlFor="el-prenom">Prénom</label>
              <input id="el-prenom" value={form.prenom} required maxLength={100} onChange={(e) => setForm({ ...form, prenom: e.target.value })} /></div>
            <div className="form-group"><label htmlFor="el-naiss">Date de naissance</label>
              <input id="el-naiss" type="date" value={form.date_naissance} onChange={(e) => setForm({ ...form, date_naissance: e.target.value })} /></div>
            <div className="form-group"><label htmlFor="el-sexe">Sexe</label>
              <select id="el-sexe" value={form.sexe} onChange={(e) => setForm({ ...form, sexe: e.target.value })}>
                <option value="M">Masculin</option><option value="F">Féminin</option>
              </select></div>
          </div>
          <div className="form-row">
            <div className="form-group"><label htmlFor="el-p1">Parent / tuteur</label>
              <input id="el-p1" value={form.parent_nom} maxLength={150} onChange={(e) => setForm({ ...form, parent_nom: e.target.value })} /></div>
            <div className="form-group"><label htmlFor="el-m1">Mobile du parent</label>
              <input id="el-m1" type="tel" value={form.parent_mobile} maxLength={30} onChange={(e) => setForm({ ...form, parent_mobile: e.target.value })} /></div>
            <div className="form-group"><label htmlFor="el-p2">Second parent (facultatif)</label>
              <input id="el-p2" value={form.parent2_nom} maxLength={150} onChange={(e) => setForm({ ...form, parent2_nom: e.target.value })} /></div>
            <div className="form-group"><label htmlFor="el-m2">Mobile du second parent</label>
              <input id="el-m2" type="tel" value={form.parent2_mobile} maxLength={30} onChange={(e) => setForm({ ...form, parent2_mobile: e.target.value })} /></div>
          </div>
          <div className="form-group">
            <label htmlFor="photo-eleve">Photo de l’élève</label>
            <PhotoPicker fichier={photo} onChange={setPhoto} />
          </div>
          <button className="btn-primary" type="submit"><Icon nom="plus" taille={16} /> Ajouter l’élève</button>
        </form>
      </div>

      <div className="card">
        <div className="card-titre">
          <h3>Liste ({items.length})</h3>
          <div className="actions-ligne">
            <div className="champ-recherche">
              <Icon nom="recherche" taille={16} />
              <input placeholder="Rechercher (nom, prénom, matricule)" value={search}
                onChange={(e) => setSearch(e.target.value)} aria-label="Rechercher" />
            </div>
            <select value={ordre} onChange={(e) => setOrdre(e.target.value)} aria-label="Ordre" style={{ width: 'auto' }}>
              <option value="alpha">Ordre alphabétique</option>
              <option value="matricule">Par numéro (matricule)</option>
            </select>
          </div>
        </div>
        <div className="table-wrap">
          <table className="data-table">
            <thead><tr><th>Matricule</th><th>Élève</th><th>Dernière classe</th><th>Décision</th><th></th></tr></thead>
            <tbody>
              {items.map(el => (
                <tr key={el.id} className="cliquable" onClick={() => navigate(`/admin/eleves/${el.id}`)}>
                  <td>{el.matricule || <span className="muted">à l'inscription</span>}</td>
                  <td>
                    <div className="cellule-eleve">
                      <Avatar eleve={el} taille="s" />
                      <span><strong>{el.nom}</strong> {el.prenom}</span>
                    </div>
                  </td>
                  <td>{el.derniere_classe ? `${el.derniere_classe} (${el.derniere_annee})` : <span className="muted">Non inscrit</span>}</td>
                  <td><DecisionBadge decision={el.derniere_decision} /></td>
                  <td>
                    <button className="btn-small btn-secondary">Dossier</button>
                    <button className="btn-small btn-danger" onClick={(e) => supprimer(e, el)}>Supprimer</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {items.length === 0 && (
            <EmptyState icone="eleve" titre="Aucun élève">
              {search ? 'Aucun résultat pour cette recherche.' : 'Ajoutez un premier élève avec le formulaire ci-dessus.'}
            </EmptyState>
          )}
        </div>
      </div>
    </div>
  );
};

export default Eleves;

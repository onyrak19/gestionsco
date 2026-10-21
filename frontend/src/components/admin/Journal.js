import React, { useCallback, useEffect, useRef, useState } from 'react';
import api from '../../api/axios';
import { formatApiError } from '../../utils/errors';
import { cleJour, heure, libelleJour } from '../../utils/dates';
import PageHeader from '../ui/PageHeader';
import EmptyState from '../ui/EmptyState';
import Icon from '../ui/Icon';

const TAILLE_PAGE = 50;
const FILTRES_VIDES = {
  q: '', utilisateur: '', categorie: '', action: '', annee: '', date_debut: '', date_fin: '',
};

// Fenêtre de traçabilité : qui a fait quoi, quand (lecture seule, administrateur).
const Journal = () => {
  const [filtres, setFiltres] = useState(FILTRES_VIDES);
  const [options, setOptions] = useState({ utilisateurs: [], categories: [], actions: [], annees: [] });
  const [page, setPage] = useState(1);
  const [donnees, setDonnees] = useState({ count: 0, results: [] });
  const [erreur, setErreur] = useState('');
  const [chargement, setChargement] = useState(true);
  const [auto, setAuto] = useState(false);
  const [maj, setMaj] = useState(null);
  const delai = useRef(null);

  useEffect(() => {
    api.get('/journal/filtres/').then((r) => setOptions(r.data))
      .catch((err) => setErreur(formatApiError(err)));
  }, []);

  const charger = useCallback((silencieux = false) => {
    if (!silencieux) setChargement(true);
    const params = { page, page_size: TAILLE_PAGE };
    Object.entries(filtres).forEach(([k, v]) => { if (v) params[k] = v; });
    return api.get('/journal/', { params })
      .then((r) => { setDonnees(r.data); setErreur(''); setMaj(new Date()); })
      .catch((err) => setErreur(formatApiError(err)))
      .finally(() => setChargement(false));
  }, [filtres, page]);

  // La recherche texte attend la fin de la frappe ; les autres filtres agissent aussitôt
  useEffect(() => {
    clearTimeout(delai.current);
    delai.current = setTimeout(() => charger(), filtres.q ? 300 : 0);
    return () => clearTimeout(delai.current);
  }, [charger, filtres.q]);

  // Actualisation automatique toutes les 10 secondes (page 1 seulement)
  useEffect(() => {
    if (!auto || page !== 1) return undefined;
    const t = setInterval(() => charger(true), 10000);
    return () => clearInterval(t);
  }, [auto, page, charger]);

  const changer = (champ, valeur) => { setFiltres((f) => ({ ...f, [champ]: valeur })); setPage(1); };
  const nbPages = Math.max(1, Math.ceil(donnees.count / TAILLE_PAGE));
  const filtresActifs = Object.values(filtres).some(Boolean);

  // Regroupement par jour
  const lignes = [];
  let jourPrecedent = null;
  donnees.results.forEach((a) => {
    const jour = cleJour(a.date);
    if (jour !== jourPrecedent) { lignes.push({ type: 'jour', cle: `j-${jour}`, texte: libelleJour(a.date) }); jourPrecedent = jour; }
    lignes.push({ type: 'action', cle: a.id, a });
  });

  return (
    <div className="page">
      <PageHeader titre="Journal d'activité"
        sousTitre="Tout ce qui se passe dans l'application : connexions, inscriptions, notes, impressions… Le journal ne peut être ni modifié ni effacé.">
        <label className="interrupteur">
          <input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} />
          <span className="interrupteur-piste" aria-hidden="true" />
          Actualiser automatiquement
        </label>
        <button type="button" className="btn-secondary" onClick={() => charger()}>
          <Icon nom="actualiser" taille={16} /> Actualiser
        </button>
      </PageHeader>
      {erreur && <div className="error">{erreur}</div>}

      <div className="card">
        <div className="filtres-journal">
          <div className="champ-recherche champ-large">
            <Icon nom="recherche" taille={16} />
            <input type="search" placeholder="Rechercher : un élève, une classe, une matière, un nom…" value={filtres.q}
              onChange={(e) => changer('q', e.target.value)} aria-label="Rechercher dans le journal" />
          </div>
          <select value={filtres.utilisateur} onChange={(e) => changer('utilisateur', e.target.value)} aria-label="Utilisateur">
            <option value="">Tous les utilisateurs</option>
            {options.utilisateurs.map((u) => <option key={u.id} value={u.id}>{u.nom}</option>)}
          </select>
          <select value={filtres.categorie} onChange={(e) => changer('categorie', e.target.value)} aria-label="Catégorie">
            <option value="">Toutes les catégories</option>
            {options.categories.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
          </select>
          <select value={filtres.action} onChange={(e) => changer('action', e.target.value)} aria-label="Type d'action">
            <option value="">Toutes les actions</option>
            {options.actions.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
          </select>
          <select value={filtres.annee} onChange={(e) => changer('annee', e.target.value)} aria-label="Année scolaire">
            <option value="">Toutes les années</option>
            {options.annees.map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
          <label className="champ-date">Du
            <input type="date" value={filtres.date_debut} onChange={(e) => changer('date_debut', e.target.value)} />
          </label>
          <label className="champ-date">au
            <input type="date" value={filtres.date_fin} onChange={(e) => changer('date_fin', e.target.value)} />
          </label>
          {filtresActifs && (
            <button type="button" className="btn-secondary btn-compact"
              onClick={() => { setFiltres(FILTRES_VIDES); setPage(1); }}>
              Effacer les filtres
            </button>
          )}
        </div>
      </div>

      <div className="card">
        <div className="card-titre">
          <h3>{donnees.count} action{donnees.count > 1 ? 's' : ''}{filtresActifs ? ' correspondante' + (donnees.count > 1 ? 's' : '') : ''}</h3>
          {maj && <small className="muted">Mis à jour à {heure(maj.toISOString())}</small>}
        </div>

        {chargement && donnees.results.length === 0 ? <p className="loading">Chargement…</p> : donnees.results.length === 0 ? (
          <EmptyState icone="journal" titre="Aucune action trouvée">
            {filtresActifs ? 'Aucune action ne correspond à ces filtres.' : 'Les actions apparaîtront ici dès qu’elles auront lieu.'}
          </EmptyState>
        ) : (
          <div className="table-wrap">
            <table className="data-table table-journal">
              <thead><tr><th>Heure</th><th>Qui</th><th>Catégorie</th><th>Action</th></tr></thead>
              <tbody>
                {lignes.map((l) => (l.type === 'jour' ? (
                  <tr key={l.cle} className="ligne-jour"><td colSpan={4}>{l.texte}</td></tr>
                ) : (
                  <tr key={l.cle}>
                    <td className="col-heure">{heure(l.a.date)}</td>
                    <td className="col-qui">
                      <strong>{l.a.utilisateur_nom || 'Visiteur'}</strong>
                      {l.a.utilisateur_role && (
                        <span className={`badge badge-role-${l.a.utilisateur_role}`}>
                          {l.a.utilisateur_role === 'admin' ? 'admin' : 'enseignant'}
                        </span>
                      )}
                    </td>
                    <td><span className={`badge badge-cat badge-cat-${l.a.categorie}`}>{l.a.categorie_libelle}</span></td>
                    <td className="col-description">
                      {l.a.description}
                      {l.a.adresse_ip && <small className="muted ip"> · {l.a.adresse_ip}</small>}
                    </td>
                  </tr>
                )))}
              </tbody>
            </table>
          </div>
        )}

        {nbPages > 1 && (
          <div className="pagination">
            <button type="button" className="btn-secondary btn-compact" disabled={page <= 1} onClick={() => setPage(page - 1)}>
              <Icon nom="gauche" taille={14} /> Plus récentes
            </button>
            <span>Page {page} sur {nbPages}</span>
            <button type="button" className="btn-secondary btn-compact" disabled={page >= nbPages} onClick={() => setPage(page + 1)}>
              Plus anciennes <Icon nom="droite" taille={14} />
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default Journal;

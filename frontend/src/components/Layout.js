import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import Icon from './ui/Icon';
import PaletteRecherche from './ui/PaletteRecherche';
import useTheme from '../hooks/useTheme';
import useMenu from '../hooks/useMenu';
import usePleinEcran from '../hooks/usePleinEcran';
import {
  ESPACES, MENUS, espaceDeChemin, filAriane, libelleEspace, noterPageRecente, pagesRecherchables,
} from '../utils/navigation';

const Layout = ({ children }) => {
  const { user, logout, isAdmin } = useAuth();
  const navigate = useNavigate();
  const lieu = useLocation();
  const admin = isAdmin();
  const [ouvert, setOuvert] = useState(false);            // tiroir du menu sur téléphone
  const [palette, setPalette] = useState(false);
  const [menuUser, setMenuUser] = useState(false);
  const [theme, basculerTheme] = useTheme();
  const { mode, basculerMasque, basculerReduit } = useMenu();
  const [pleinEcran, basculerPleinEcran, pleinEcranPossible] = usePleinEcran();
  const refMenuUser = useRef(null);

  const espace = espaceDeChemin(lieu.pathname, admin);
  const menu = MENUS[espace];
  const fil = useMemo(() => filAriane(lieu.pathname, espace), [lieu.pathname, espace]);
  const pages = useMemo(() => pagesRecherchables(admin), [admin]);
  const reduit = mode === 'reduit';
  const nom = [user?.prenom, user?.nom].filter(Boolean).join(' ') || user?.username || '';

  // Sur téléphone, le tiroir se referme quand on change de page ; le menu utilisateur aussi
  useEffect(() => { setOuvert(false); setMenuUser(false); }, [lieu.pathname]);

  // Les dernières pages visitées alimentent « Reprendre » sur l'accueil
  useEffect(() => {
    const derniere = fil[fil.length - 1];
    if (admin && espace !== 'accueil' && derniere && !['Détail', 'Configuration'].includes(derniere.label)) {
      noterPageRecente({ to: lieu.pathname, label: derniere.label, espace: libelleEspace(espace) });
    }
  }, [lieu.pathname, fil, admin, espace]);

  // Raccourcis clavier : Ctrl/Cmd + K (rechercher une page), Ctrl/Cmd + B (cacher / montrer le menu)
  useEffect(() => {
    const surTouche = (e) => {
      if (!(e.ctrlKey || e.metaKey) || e.altKey) return;
      const k = e.key.toLowerCase();
      if (k === 'k') { e.preventDefault(); setPalette(true); }
      else if (k === 'b') { e.preventDefault(); basculerMasque(); }
    };
    window.addEventListener('keydown', surTouche);
    return () => window.removeEventListener('keydown', surTouche);
  }, [basculerMasque]);

  // Ferme le menu utilisateur au clic à l'extérieur ou avec Échap
  useEffect(() => {
    if (!menuUser) return undefined;
    const dehors = (e) => { if (refMenuUser.current && !refMenuUser.current.contains(e.target)) setMenuUser(false); };
    const echap = (e) => { if (e.key === 'Escape') setMenuUser(false); };
    document.addEventListener('mousedown', dehors);
    document.addEventListener('keydown', echap);
    return () => { document.removeEventListener('mousedown', dehors); document.removeEventListener('keydown', echap); };
  }, [menuUser]);

  const fermerPalette = useCallback(() => setPalette(false), []);
  const handleLogout = () => { logout(); navigate('/login'); };
  const accueilLien = admin ? '/admin' : '/enseignant';

  return (
    <div className={`layout ${pleinEcran ? 'plein-ecran' : ''}`} data-espace={espace} data-menu={mode}>
      <a className="lien-evitement" href="#contenu-principal">Aller au contenu</a>

      <aside className={`sidebar ${ouvert ? 'ouvert' : ''}`} aria-label="Navigation principale">
        <Link to={accueilLien} className="sidebar-logo" title="Retour à l'accueil">
          <span className="logo-icone"><Icon nom="eleve" taille={22} /></span>
          <span className="logo-texte masquable">
            <strong>Gestion Scolaire</strong>
            <small>{admin ? 'Espace administration' : 'Espace enseignant'}</small>
          </span>
        </Link>

        {admin && (
          <nav className="espaces" aria-label="Espaces">
            {ESPACES.map((e) => {
              const actif = e.cle === espace;
              return (
                <Link key={e.cle} to={e.to} title={reduit ? e.label : e.aide}
                  className={`espace-lien esp-${e.cle} ${actif ? 'actif' : ''}`} aria-current={actif ? 'page' : undefined}>
                  <span className="esp-tuile"><Icon nom={e.icone} taille={17} /></span>
                  <span className="esp-texte masquable">{e.label}</span>
                </Link>
              );
            })}
          </nav>
        )}

        <nav className="sidebar-nav" key={espace} aria-label={libelleEspace(espace)}>
          {menu.map((item, i) => (item.titre ? (
            <div key={`t${i}`} className="nav-titre"><span className="masquable">{item.titre}</span></div>
          ) : (
            <NavLink key={item.to} to={item.to} end={item.end} title={reduit ? item.label : undefined}
              className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}>
              <Icon nom={item.icone} taille={18} />
              <span className="masquable">{item.label}</span>
            </NavLink>
          )))}
        </nav>

        <div className="sidebar-pied">
          <button type="button" className="btn-replier" onClick={basculerReduit}
            aria-label={reduit ? 'Étendre le menu' : 'Réduire le menu'} title={reduit ? 'Étendre le menu' : 'Réduire le menu'}>
            <Icon nom="gauche" taille={16} className="fleche-replier" />
            <span className="masquable">Réduire le menu</span>
          </button>
        </div>
      </aside>

      {ouvert && <div className="voile" onClick={() => setOuvert(false)} aria-hidden="true" />}

      <div className="contenu">
        <div className="progression-route" key={lieu.pathname} aria-hidden="true" />

        <header className="topbar">
          <button type="button" className="btn-icone burger" aria-label="Ouvrir le menu" aria-expanded={ouvert}
            onClick={() => setOuvert(!ouvert)}>
            <Icon nom={ouvert ? 'fermer' : 'menu'} taille={20} />
          </button>
          <button type="button" className="btn-icone toggle-menu" onClick={basculerMasque}
            aria-label={mode === 'masque' ? 'Afficher le menu' : 'Masquer le menu'}
            title={`${mode === 'masque' ? 'Afficher' : 'Masquer'} le menu (Ctrl+B)`}>
            <Icon nom="panneau" taille={20} />
          </button>

          <nav className="fil" aria-label="Fil d'Ariane">
            <ol>
              {fil.map((p, i) => {
                const dernier = i === fil.length - 1;
                return (
                  <li key={`${p.label}-${i}`}>
                    {i > 0 && <Icon nom="chevron" taille={14} className="fil-sep" />}
                    {i === 0 && <span className="fil-point" aria-hidden="true" />}
                    {p.to && !dernier ? <Link to={p.to}>{p.label}</Link> : <span aria-current={dernier ? 'page' : undefined}>{p.label}</span>}
                  </li>
                );
              })}
            </ol>
          </nav>

          <div className="topbar-actions">
            <button type="button" className="recherche-rapide" onClick={() => setPalette(true)} aria-label="Rechercher une page">
              <Icon nom="recherche" taille={16} />
              <span>Aller à…</span>
              <kbd>Ctrl K</kbd>
            </button>
            {pleinEcranPossible && (
              <button type="button" className="btn-icone" onClick={basculerPleinEcran} aria-pressed={pleinEcran}
                aria-label={pleinEcran ? 'Quitter le plein écran' : 'Passer en plein écran'}
                title={pleinEcran ? 'Quitter le plein écran' : 'Plein écran'}>
                <Icon nom={pleinEcran ? 'reduire' : 'agrandir'} taille={18} />
              </button>
            )}
            <button type="button" className="btn-icone" onClick={basculerTheme}
              aria-label={theme === 'dark' ? 'Passer au thème clair' : 'Passer au thème sombre'}
              title={theme === 'dark' ? 'Thème clair' : 'Thème sombre'}>
              <Icon nom={theme === 'dark' ? 'soleil' : 'lune'} taille={18} />
            </button>

            <div className="menu-user" ref={refMenuUser}>
              <button type="button" className="user-bouton" onClick={() => setMenuUser(!menuUser)}
                aria-haspopup="menu" aria-expanded={menuUser}>
                <span className="user-avatar">{(nom || '?')[0].toUpperCase()}</span>
                <span className="user-nom">{nom}</span>
                <Icon nom="bas" taille={14} className="user-chevron" />
              </button>
              {menuUser && (
                <div className="user-menu" role="menu">
                  <div className="user-menu-id">
                    <strong>{nom}</strong>
                    <small>{admin ? 'Administrateur' : 'Enseignant'}</small>
                  </div>
                  <button type="button" role="menuitem" className="user-menu-item danger" onClick={handleLogout}>
                    <Icon nom="sortie" taille={16} /> Se déconnecter
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>

        <main className="main-content" id="contenu-principal" key={lieu.pathname}>{children}</main>
      </div>

      {palette && <PaletteRecherche pages={pages} onClose={fermerPalette} />}
    </div>
  );
};

export default Layout;

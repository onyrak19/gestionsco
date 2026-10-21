import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Icon from './Icon';

const normaliser = (s) => (s || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();

// « Aller à… » : on tape quelques lettres, on choisit une page au clavier (↑ ↓ Entrée) ou à la souris
const PaletteRecherche = ({ pages, onClose }) => {
  const [q, setQ] = useState('');
  const [courant, setCourant] = useState(0);
  const navigate = useNavigate();
  const champ = useRef(null);
  const liste = useRef(null);

  const resultats = useMemo(() => {
    const n = normaliser(q.trim());
    if (!n) return pages;
    return pages.filter((p) => normaliser(`${p.label} ${p.espace} ${p.mots || ''}`).includes(n));
  }, [q, pages]);

  useEffect(() => { setCourant(0); }, [q]);
  useEffect(() => { if (champ.current) champ.current.focus(); }, []);
  useEffect(() => {
    const el = liste.current && liste.current.children[courant];
    if (el && el.scrollIntoView) el.scrollIntoView({ block: 'nearest' });
  }, [courant]);

  const aller = (page) => { navigate(page.to); onClose(); };

  const touche = (e) => {
    if (e.key === 'Escape') { e.preventDefault(); onClose(); }
    else if (e.key === 'ArrowDown') { e.preventDefault(); setCourant((c) => Math.min(c + 1, resultats.length - 1)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setCourant((c) => Math.max(c - 1, 0)); }
    else if (e.key === 'Enter' && resultats[courant]) { e.preventDefault(); aller(resultats[courant]); }
  };

  return (
    <div className="palette-fond" onMouseDown={onClose} role="presentation">
      <div className="palette" role="dialog" aria-modal="true" aria-label="Aller à une page" onMouseDown={(e) => e.stopPropagation()}>
        <div className="palette-champ">
          <Icon nom="recherche" taille={18} />
          <input ref={champ} value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={touche}
            placeholder="Aller à… (élèves, encaisser, bulletins)" role="combobox" aria-expanded="true" aria-controls="palette-liste"
            aria-activedescendant={resultats[courant] ? `palette-${courant}` : undefined} autoComplete="off" />
          <kbd>Échap</kbd>
        </div>
        {resultats.length === 0 ? (
          <p className="palette-vide">Aucune page ne correspond à « {q} ».</p>
        ) : (
          <ul id="palette-liste" className="palette-liste" role="listbox" ref={liste}>
            {resultats.map((p, i) => (
              <li key={p.to} id={`palette-${i}`} role="option" aria-selected={i === courant}
                className={i === courant ? 'courant' : ''}
                onMouseEnter={() => setCourant(i)} onClick={() => aller(p)}>
                <Icon nom={p.icone} taille={18} />
                <span className="palette-nom">{p.label}</span>
                <small>{p.espace}</small>
              </li>
            ))}
          </ul>
        )}
        <div className="palette-pied"><span><kbd>↑</kbd><kbd>↓</kbd> naviguer</span><span><kbd>Entrée</kbd> ouvrir</span></div>
      </div>
    </div>
  );
};

export default PaletteRecherche;

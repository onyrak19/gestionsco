import React from 'react';
import Icon from './Icon';

// Un écran vide indique quoi faire ensuite
const EmptyState = ({ icone = 'fichier', titre, children }) => (
  <div className="etat-vide">
    <Icon nom={icone} taille={30} />
    <strong>{titre}</strong>
    {children && <p>{children}</p>}
  </div>
);

export default EmptyState;

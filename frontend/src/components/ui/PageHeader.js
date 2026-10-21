import React from 'react';

// En-tête de page : titre, phrase d'aide et actions principales à droite
const PageHeader = ({ titre, sousTitre, children }) => (
  <header className="page-entete">
    <div className="page-entete-texte">
      <h1>{titre}</h1>
      {sousTitre && <p className="page-subtitle">{sousTitre}</p>}
    </div>
    {children && <div className="page-actions">{children}</div>}
  </header>
);

export default PageHeader;

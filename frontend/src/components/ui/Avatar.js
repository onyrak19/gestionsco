import React from 'react';
import AuthImage from './AuthImage';

// Photo de l'élève, ou ses initiales s'il n'en a pas.
// `eleve` : { id, nom, prenom, photo_token }
const Avatar = ({ eleve, taille = 'm' }) => {
  const initiales = `${(eleve?.prenom || '')[0] || ''}${(eleve?.nom || '')[0] || ''}`.toUpperCase();
  return (
    <AuthImage
      eleveId={eleve?.id}
      jeton={eleve?.photo_token}
      alt={`Photo de ${eleve?.prenom || ''} ${eleve?.nom || ''}`.trim()}
      className={`avatar avatar-${taille}`}
    >
      {initiales || '?'}
    </AuthImage>
  );
};

export default Avatar;

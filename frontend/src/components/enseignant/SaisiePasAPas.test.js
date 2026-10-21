import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import SaisiePasAPas, { erreurDeSaisie } from './SaisiePasAPas';

jest.mock('../../api/axios', () => ({
  __esModule: true,
  default: { get: jest.fn(() => Promise.reject(new Error('pas de photo'))) },
}));

const eleve = (id, numero, nom) => ({
  id, numero, eleve_details: { id, nom, prenom: 'Test', matricule: `M${id}`, photo_token: '' },
});
const ELEVES = [eleve(1, 1, 'Rakoto'), eleve(2, 2, 'Rabe'), eleve(3, 3, 'Randria')];
const CONTEXTE = { classe: '6ème 1', matiere: 'SVT', trimestre: '1er trimestre' };

// Le composant est contrôlé : ce petit conteneur reproduit ce que fait SaisieNotes
const monter = (surcharge = {}) => {
  const props = {
    notes: {}, statuts: {}, onChange: jest.fn(), onSave: jest.fn(() => Promise.resolve(true)),
    onTerminer: jest.fn(), onQuitter: jest.fn(), ...surcharge,
  };
  render(<SaisiePasAPas eleves={ELEVES} contexte={CONTEXTE} {...props} />);
  return props;
};

test('affiche uniquement l’élève n° 1 au départ', () => {
  monter();
  expect(screen.getByText(/Élève n° 1/)).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: /RAKOTO/ })).toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: /RABE/ })).not.toBeInTheDocument();
});

test('« Suivant » enregistre l’élève modifié puis affiche le numéro 2', async () => {
  const props = monter({ statuts: { 1: { type: 'modifie' } }, notes: { 1: { j1: '12' } } });
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer et suivant' }));
  await waitFor(() => expect(screen.getByText(/Élève n° 2/)).toBeInTheDocument());
  expect(props.onSave).toHaveBeenCalledTimes(1);
  expect(props.onSave).toHaveBeenCalledWith(1);
});

test('sans modification, rien n’est envoyé au serveur', async () => {
  const props = monter();
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer et suivant' }));
  await waitFor(() => expect(screen.getByText(/Élève n° 2/)).toBeInTheDocument());
  expect(props.onSave).not.toHaveBeenCalled();
});

test('une note hors de 0–20 bloque le passage au suivant', async () => {
  const props = monter({ statuts: { 1: { type: 'modifie' } }, notes: { 1: { j1: '25' } } });
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer et suivant' }));
  expect(await screen.findByText(/comprise entre 0 et 20/)).toBeInTheDocument();
  expect(screen.getByText(/Élève n° 1/)).toBeInTheDocument();
  expect(props.onSave).not.toHaveBeenCalled();
});

test('si l’enregistrement échoue, on reste sur le même élève', async () => {
  const props = monter({ statuts: { 1: { type: 'modifie' } }, notes: { 1: { j1: '12' } }, onSave: jest.fn(() => Promise.resolve(false)) });
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer et suivant' }));
  await waitFor(() => expect(props.onSave).toHaveBeenCalled());
  expect(screen.getByText(/Élève n° 1/)).toBeInTheDocument();
});

test('le dernier élève propose de terminer', async () => {
  const props = monter();
  fireEvent.click(screen.getByRole('button', { name: 'Élève n° 3' }));
  await waitFor(() => expect(screen.getByText(/Élève n° 3/)).toBeInTheDocument());
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer et terminer' }));
  await waitFor(() => expect(props.onTerminer).toHaveBeenCalledWith({ saisis: 0, total: 3 }));
});

test('saisie : les modifications remontent au parent', () => {
  const props = monter();
  fireEvent.change(screen.getAllByRole('spinbutton')[0], { target: { value: '14' } });
  expect(props.onChange).toHaveBeenCalledWith(1, 'j1', '14');
});

test('validation des notes', () => {
  expect(erreurDeSaisie({ j1: '12', examen: '0' })).toBe('');
  expect(erreurDeSaisie({ j1: '', j2: null })).toBe('');
  expect(erreurDeSaisie({ j2: '-1' })).toMatch(/J2/);
  expect(erreurDeSaisie({ examen: '20.01' })).toMatch(/Examen/);
});

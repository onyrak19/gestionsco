import { render, screen, waitFor, fireEvent, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import api from '../../api/axios';
import { ouvrirPdf } from '../../utils/pdf';
import Matieres from './Matieres';
import Impressions from './Impressions';
import Affectations from './Affectations';

jest.mock('../../api/axios', () => ({
  __esModule: true,
  API_URL: 'http://test/api',
  default: { get: jest.fn(), post: jest.fn(), put: jest.fn(), patch: jest.fn(), delete: jest.fn() },
}));
jest.mock('../../utils/pdf', () => ({ ouvrirPdf: jest.fn(() => Promise.resolve()), lundiCourant: () => '2026-10-05' }));

beforeEach(() => jest.clearAllMocks());

describe('Matières', () => {
  const MATIERE = { id: 7, nom: 'SVT', code: 'SVT-01', coefficient: 2 };

  test('le coefficient par défaut se modifie, et le code automatique n’est pas affiché', async () => {
    api.get.mockResolvedValue({ data: [MATIERE] });
    api.patch.mockResolvedValue({ data: { ...MATIERE, coefficient: 4 } });
    render(<Matieres />);

    expect(await screen.findByText('SVT')).toBeInTheDocument();
    expect(screen.queryByText('SVT-01')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /modifier svt/i }));
    fireEvent.change(screen.getByLabelText(/coefficient par défaut/i), { target: { value: '4' } });
    fireEvent.click(screen.getByRole('button', { name: /^enregistrer$/i }));

    await waitFor(() => expect(api.patch).toHaveBeenCalledWith('/school/matieres/7/', { nom: 'SVT', coefficient: 4 }));
  });
});

describe('Impressions par classes', () => {
  const ANNEE = { id: 1, libelle: '2026-2027', active: true, cloturee: false };
  const CLASSES = [
    { id: 10, nom: '6ème 1', effectif: 30 },
    { id: 11, nom: '6ème 2', effectif: 28 },
    { id: 12, nom: '5ème 1', effectif: 0 },
  ];
  beforeEach(() => {
    api.get.mockImplementation((url) => Promise.resolve({ data: url.includes('annees') ? [ANNEE] : CLASSES }));
  });
  const monter = () => render(<MemoryRouter><Impressions /></MemoryRouter>);

  test('bulletins : sélection de classes puis impression en un seul PDF', async () => {
    monter();
    fireEvent.click(await screen.findByLabelText(/6ème 1/));
    fireEvent.click(screen.getByLabelText(/6ème 2/));
    expect(screen.getByText(/58/)).toBeInTheDocument();     // 30 + 28 bulletins
    fireEvent.click(screen.getByRole('button', { name: '2e trimestre' }));
    fireEvent.click(screen.getByRole('button', { name: /imprimer : bulletins/i }));

    await waitFor(() => expect(ouvrirPdf).toHaveBeenCalledWith(
      '/school/pdf/bulletins/', { classes: [10, 11], trimestre: 2, ordre: 'alpha' }));
  });

  test('« Toutes les classes » ignore les classes sans élèves', async () => {
    monter();
    fireEvent.click(await screen.findByRole('button', { name: /toutes les classes/i }));
    fireEvent.click(screen.getByRole('button', { name: /imprimer : bulletins/i }));
    await waitFor(() => expect(ouvrirPdf).toHaveBeenCalledWith(
      '/school/pdf/bulletins/', { classes: [10, 11], trimestre: 1, ordre: 'alpha' }));
    expect(screen.getByLabelText(/5ème 1/)).toBeDisabled();
  });

  test('cartes d’élève, certificats et fiches d’appel ont leur propre impression', async () => {
    monter();
    fireEvent.click(await screen.findByLabelText(/6ème 1/));

    fireEvent.click(screen.getByRole('button', { name: /cartes d'élève/i }));
    fireEvent.click(screen.getByRole('button', { name: /imprimer : cartes d'élève/i }));
    await waitFor(() => expect(ouvrirPdf).toHaveBeenLastCalledWith('/school/pdf/cartes/', { classes: [10], ordre: 'alpha' }));

    fireEvent.click(screen.getByRole('button', { name: /certificats de scolarité/i }));
    fireEvent.click(screen.getByRole('button', { name: /imprimer : certificats/i }));
    await waitFor(() => expect(ouvrirPdf).toHaveBeenLastCalledWith('/school/pdf/certificats/', { classes: [10], ordre: 'alpha' }));

    fireEvent.click(screen.getByRole('button', { name: /fiches d'appel/i }));
    fireEvent.change(screen.getByLabelText(/semaine du/i), { target: { value: '2026-10-05' } });
    fireEvent.click(screen.getByRole('button', { name: /imprimer : fiches/i }));
    await waitFor(() => expect(ouvrirPdf).toHaveBeenLastCalledWith(
      '/school/pdf/fiches-appel/', { classes: [10], ordre: 'alpha', semaine: '2026-10-05' }));
  });

  test('impression impossible sans classe choisie', async () => {
    monter();
    expect(await screen.findByRole('button', { name: /imprimer : bulletins/i })).toBeDisabled();
  });
});

describe('Affectations : une seule personne par matière et par classe', () => {
  const ANNEE = { id: 1, libelle: '2026-2027', active: true, cloturee: false };
  const ENSEIGNANTS = [
    { id: 11, nom: 'Martin', prenom: 'Jean', username: 'jmartin' },
    { id: 12, nom: 'Rabe', prenom: 'Nina', username: 'nrabe' },
  ];
  const simuler = (affectations) => api.get.mockImplementation((url) => {
    if (url.includes('enseignants')) return Promise.resolve({ data: ENSEIGNANTS });
    if (url.includes('config-matieres')) return Promise.resolve({ data: { configuree: false, matieres: [] } });
    if (url.includes('matieres')) return Promise.resolve({ data: [{ id: 3, nom: 'SVT' }] });
    if (url.includes('classes')) return Promise.resolve({ data: [{ id: 5, nom: '6ème 1', annee_scolaire: 1 }] });
    if (url.includes('annees')) return Promise.resolve({ data: [ANNEE] });
    return Promise.resolve({ data: affectations });
  });

  test('une nouvelle matière reçoit un seul enseignant', async () => {
    simuler([]);
    api.post.mockResolvedValue({ data: {} });
    render(<Affectations />);

    await screen.findByRole('option', { name: '6ème 1' });
    fireEvent.change(screen.getByLabelText('Classe'), { target: { value: '5' } });
    fireEvent.change(screen.getByLabelText('Matière'), { target: { value: '3' } });
    fireEvent.change(screen.getByLabelText('Enseignant'), { target: { value: '11' } });
    fireEvent.click(screen.getByRole('button', { name: /^affecter$/i }));

    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1));
    expect(api.post).toHaveBeenCalledWith('/school/affectations/', { enseignant: '11', classe: '5', matiere: '3' });
  });

  test('une matière déjà confiée se remplace : l’affectation existante est modifiée, pas dupliquée', async () => {
    simuler([{ id: 40, enseignant: 11, enseignant_nom: 'Jean Martin', matiere: 3, matiere_nom: 'SVT',
      classe: 5, classe_nom: '6ème 1', annee_scolaire: 1 }]);
    api.patch.mockResolvedValue({ data: {} });
    render(<Affectations />);

    await screen.findByRole('option', { name: '6ème 1' });
    fireEvent.change(screen.getByLabelText('Classe'), { target: { value: '5' } });
    fireEvent.change(screen.getByLabelText('Matière'), { target: { value: '3' } });
    expect(await screen.findByText(/déjà confiée à/i)).toBeInTheDocument();
    // l'enseignant actuel n'est plus proposé
    expect(within(screen.getByLabelText('Enseignant')).queryByText(/Martin/)).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Enseignant'), { target: { value: '12' } });
    fireEvent.click(screen.getByRole('button', { name: /remplacer jean martin/i }));

    await waitFor(() => expect(api.patch).toHaveBeenCalledWith('/school/affectations/40/', { enseignant: '12' }));
    expect(api.post).not.toHaveBeenCalled();
  });
});

import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import api from '../../api/axios';
import { ouvrirPdf } from '../../utils/pdf';
import AnneesScolaires from './AnneesScolaires';
import Classes from './Classes';
import ClasseConfig from './ClasseConfig';
import PrintBar from '../ui/PrintBar';

jest.mock('../../api/axios', () => ({
  __esModule: true,
  API_URL: 'http://test/api',
  default: { get: jest.fn(), post: jest.fn(), put: jest.fn(), patch: jest.fn(), delete: jest.fn() },
}));
jest.mock('../../utils/pdf', () => ({
  ouvrirPdf: jest.fn(() => Promise.resolve()),
  lundiCourant: () => '2026-10-05',
}));

const NIVEAUX = {
  niveaux: ['6ème', '5ème', 'Première', 'Terminale'],
  niveaux_avec_serie: ['Première', 'Terminale'],
  series: ['L', 'S', 'OSE'],
};
const ANNEE = { id: 1, libelle: '2026-2027', date_debut: '2026-09-01', date_fin: '2027-06-30', active: true, cloturee: false };

beforeEach(() => jest.clearAllMocks());

describe('Clôture d’une année', () => {
  test('exige le mot de passe administrateur puis affiche le résumé', async () => {
    api.get.mockResolvedValue({ data: [ANNEE] });
    api.post.mockResolvedValue({ data: { resume: { passant: 3, redoublant: 1, non_decide: 0 } } });
    render(<AnneesScolaires />);

    fireEvent.click(await screen.findByRole('button', { name: /clôturer/i }));
    const champ = await screen.findByLabelText(/mot de passe administrateur/i);
    const confirmer = screen.getByRole('button', { name: /confirmer la clôture/i });
    expect(confirmer).toBeDisabled();            // impossible sans mot de passe

    fireEvent.change(champ, { target: { value: 'Secret123!' } });
    fireEvent.click(confirmer);

    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/school/annees/1/cloturer/', { password: 'Secret123!' }));
    expect(await screen.findByText(/3 passant/)).toBeInTheDocument();
    expect(screen.getByText(/1 redoublant/)).toBeInTheDocument();
  });

  test('un mauvais mot de passe affiche l’erreur et garde la fenêtre ouverte', async () => {
    api.get.mockResolvedValue({ data: [ANNEE] });
    api.post.mockRejectedValue({ response: { status: 403, data: { detail: 'Mot de passe administrateur incorrect.' } } });
    render(<AnneesScolaires />);

    fireEvent.click(await screen.findByRole('button', { name: /clôturer/i }));
    fireEvent.change(await screen.findByLabelText(/mot de passe administrateur/i), { target: { value: 'faux' } });
    fireEvent.click(screen.getByRole('button', { name: /confirmer la clôture/i }));

    expect(await screen.findByText(/mot de passe administrateur incorrect/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/mot de passe administrateur/i)).toBeInTheDocument();
  });
});

describe('Création d’une classe', () => {
  beforeEach(() => {
    api.get.mockImplementation((url) => Promise.resolve({
      data: url.includes('niveaux') ? NIVEAUX : url.includes('annees') ? [ANNEE] : [],
    }));
  });

  test('la série n’apparaît qu’à partir de la Première et le nom est prévisualisé', async () => {
    render(<MemoryRouter><Classes /></MemoryRouter>);
    const niveau = await screen.findByLabelText('Niveau');
    await screen.findByRole('option', { name: 'Terminale' });

    fireEvent.change(niveau, { target: { value: '5ème' } });
    expect(screen.queryByLabelText('Série')).not.toBeInTheDocument();
    expect(screen.getByText('5ème 1')).toBeInTheDocument();

    fireEvent.change(niveau, { target: { value: 'Terminale' } });
    fireEvent.change(await screen.findByLabelText('Série'), { target: { value: 'L' } });
    fireEvent.change(screen.getByLabelText('N° de la classe'), { target: { value: '2' } });
    expect(screen.getByText('Terminale L 2')).toBeInTheDocument();
  });

  test('envoie niveau, série et numéro, puis propose de configurer la classe', async () => {
    api.post.mockResolvedValue({ data: { id: 7, nom: 'Terminale L 1' } });
    render(<MemoryRouter><Classes /></MemoryRouter>);
    fireEvent.change(await screen.findByLabelText('Niveau'), { target: { value: 'Terminale' } });
    fireEvent.change(await screen.findByLabelText('Série'), { target: { value: 'L' } });
    fireEvent.click(screen.getByRole('button', { name: /créer la classe/i }));

    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/school/classes/',
      { niveau: 'Terminale', serie: 'L', numero: 1, annee_scolaire: 1 }));
    const lien = await screen.findByRole('link', { name: /configurer ses matières/i });
    expect(lien).toHaveAttribute('href', '/admin/classes/7/config');
  });

  test('niveau saisi à la main', async () => {
    render(<MemoryRouter><Classes /></MemoryRouter>);
    fireEvent.change(await screen.findByLabelText('Niveau'), { target: { value: '__libre__' } });
    fireEvent.change(await screen.findByLabelText('Nom du niveau'), { target: { value: 'Maternelle' } });
    expect(screen.getByText('Maternelle 1')).toBeInTheDocument();
  });
});

describe('Configuration des matières d’un niveau', () => {
  const CONFIG = {
    classe: 5, annee: '2026-2027', annee_cloturee: false, niveau: '5ème', serie: '', configuree: true, propose: false,
    classes: [{ id: 5, nom: '5ème 1' }, { id: 6, nom: '5ème 2' }],
    matieres: [
      { matiere: 1, nom: 'Mathématiques', code: 'MAT', enseignee: true, coefficient: 4 },
      { matiere: 2, nom: 'Histoire', code: 'HIS', enseignee: true, coefficient: 2 },
      { matiere: 3, nom: 'Sport', code: 'SPO', enseignee: false, coefficient: 1 },
    ],
  };

  const afficher = () => render(
    <MemoryRouter initialEntries={['/admin/classes/5/config']}>
      <Routes><Route path="/admin/classes/:id/config" element={<ClasseConfig />} /></Routes>
    </MemoryRouter>
  );

  test('indique que la configuration vaut pour toutes les classes du niveau', async () => {
    api.get.mockResolvedValue({ data: CONFIG });
    afficher();
    expect(await screen.findByText(/toutes les classes de 5ème/i)).toBeInTheDocument();
    expect(screen.getByText(/5ème 1, 5ème 2/)).toBeInTheDocument();
  });

  test('n’enregistre que les matières cochées, avec leurs coefficients', async () => {
    api.get.mockResolvedValue({ data: CONFIG });
    api.put.mockResolvedValue({ data: CONFIG });
    afficher();

    fireEvent.change(await screen.findByLabelText('Coefficient Mathématiques'), { target: { value: '6' } });
    fireEvent.click(screen.getByLabelText('Enseigner Histoire'));      // décoché
    fireEvent.click(screen.getByLabelText('Enseigner Sport'));         // coché
    fireEvent.click(screen.getByRole('button', { name: /enregistrer pour toutes les classes/i }));

    await waitFor(() => expect(api.put).toHaveBeenCalledWith('/school/config-matieres/', {
      classe: 5,
      matieres: [{ matiere: 1, coefficient: 6 }, { matiere: 3, coefficient: 1 }],
    }));
    expect(await screen.findByText(/enregistrée pour 2 classe/i)).toBeInTheDocument();
  });

  test('une année clôturée est en lecture seule', async () => {
    api.get.mockResolvedValue({ data: { ...CONFIG, annee_cloturee: true } });
    afficher();
    expect(await screen.findByLabelText('Coefficient Mathématiques')).toBeDisabled();
    expect(screen.queryByRole('button', { name: /enregistrer pour toutes/i })).not.toBeInTheDocument();
  });

  test('une proposition de l’année précédente doit être validée', async () => {
    api.get.mockResolvedValue({ data: { ...CONFIG, configuree: false, propose: true } });
    afficher();
    expect(await screen.findByText(/année précédente est proposée/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /enregistrer pour toutes/i })).toBeEnabled();
  });
});

describe('Barre d’impression', () => {
  test('désactivée sans sélection', () => {
    render(<PrintBar ids={[]} />);
    expect(screen.getByRole('button', { name: /cartes/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /certificats/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /bulletins/i })).toBeDisabled();
  });

  test('demande les PDF pour les élèves sélectionnés', async () => {
    render(<PrintBar ids={[4, 9]} ordre="numero" />);
    expect(screen.getByText('2')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /cartes/i }));
    await waitFor(() => expect(ouvrirPdf).toHaveBeenCalledWith('/school/pdf/cartes/', { inscriptions: [4, 9], ordre: 'numero' }));

    fireEvent.change(screen.getByLabelText('Trimestre du bulletin'), { target: { value: '3' } });
    fireEvent.click(screen.getByRole('button', { name: /bulletins/i }));
    await waitFor(() => expect(ouvrirPdf).toHaveBeenCalledWith('/school/pdf/bulletins/',
      { inscriptions: [4, 9], ordre: 'numero', trimestre: 3 }));
  });

  test('affiche l’erreur renvoyée par le serveur', async () => {
    ouvrirPdf.mockRejectedValueOnce(new Error('Aucun élève à imprimer.'));
    const surErreur = jest.fn();
    render(<PrintBar ids={[1]} onError={surErreur} />);
    fireEvent.click(screen.getByRole('button', { name: /certificats/i }));
    await waitFor(() => expect(surErreur).toHaveBeenCalledWith('Aucun élève à imprimer.'));
  });
});

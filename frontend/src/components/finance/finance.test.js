import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import api from '../../api/axios';
import { ouvrirPdf } from '../../utils/pdf';
import EncaisserModal from './EncaisserModal';
import Impressions from '../admin/Impressions';

jest.mock('../../api/axios', () => ({
  __esModule: true,
  API_URL: 'http://test/api',
  default: { get: jest.fn(), post: jest.fn(), put: jest.fn(), patch: jest.fn(), delete: jest.fn() },
}));
jest.mock('../../utils/pdf', () => ({ ouvrirPdf: jest.fn(() => Promise.resolve()), ouvrirPdfGet: jest.fn(), lundiCourant: () => '2026-10-05' }));

beforeEach(() => jest.clearAllMocks());

const SITUATION = {
  tarif_defini: true,
  droit: { tarif: 1, montant: 50000, paye: false },
  ecolage: {
    mensuel: 25000, nb_payes: 1, nb_impayes: 1,
    mois: [
      { mois: '2026-09', libelle: 'Septembre 2026', montant: 25000, statut: 'impaye' },
      { mois: '2026-10', libelle: 'Octobre 2026', montant: 25000, statut: 'paye' },
    ],
  },
  autres: [],
};

describe('Encaissement', () => {
  beforeEach(() => {
    api.get.mockResolvedValue({ data: { devise: 'Ar', modes_paiement: [{ value: 'especes', label: 'Espèces' }] } });
  });

  test('le montant est calculé par le serveur, puis le paiement est enregistré sans saisir de montant', async () => {
    api.post.mockImplementation((url, corps) => Promise.resolve({
      data: corps.apercu
        ? { apercu: true, total: 25000, lignes: [{ libelle: 'Écolage Septembre 2026', mois: '2026-09', montant: 25000 }] }
        : { id: 9, numero: 'REC-2026-00001', montant_total: 25000 },
    }));
    const onDone = jest.fn();
    render(<EncaisserModal inscription={5} situation={SITUATION} onClose={jest.fn()} onDone={onDone} />);

    expect(screen.getByLabelText(/octobre 2026/i)).toBeDisabled();       // déjà payé
    fireEvent.click(screen.getByLabelText(/septembre 2026/i));

    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/finance/paiements/',
      expect.objectContaining({ inscription: 5, type: 'ecolage', mois: ['2026-09'], apercu: true })));
    const bouton = screen.getByRole('button', { name: 'Encaisser' });
    await waitFor(() => expect(bouton).not.toBeDisabled());
    fireEvent.click(bouton);

    await waitFor(() => expect(onDone).toHaveBeenCalledWith(expect.objectContaining({ numero: 'REC-2026-00001' })));
    const envoi = api.post.mock.calls.find(([, c]) => c.apercu === false)[1];
    expect(envoi).not.toHaveProperty('montant');
  });

  test('on ne peut pas encaisser tant qu’aucun mois n’est choisi', () => {
    render(<EncaisserModal inscription={5} situation={SITUATION} onClose={jest.fn()} onDone={jest.fn()} />);
    expect(screen.getByRole('button', { name: 'Encaisser' })).toBeDisabled();
    expect(api.post).not.toHaveBeenCalled();
  });
});

describe('Impressions financières', () => {
  beforeEach(() => {
    api.get.mockImplementation((url) => Promise.resolve({
      data: url.includes('annees') ? [{ id: 1, libelle: '2026-2027', active: true }] : [{ id: 10, nom: '6ème 1', effectif: 30 }],
    }));
  });
  const monter = () => render(<MemoryRouter><Impressions /></MemoryRouter>);

  test('la liste des impayés s’imprime pour toute l’année sans choisir de classe', async () => {
    monter();
    fireEvent.click(await screen.findByRole('button', { name: /liste des impayés/i }));
    fireEvent.click(screen.getByRole('button', { name: /imprimer : liste des impayés/i }));
    await waitFor(() => expect(ouvrirPdf).toHaveBeenCalledWith('/finance/pdf/impayes/', { annee: 1 }));
  });

  test('les cartes d’écolage suivent la sélection des classes', async () => {
    monter();
    fireEvent.click(await screen.findByLabelText(/6ème 1/));
    fireEvent.click(screen.getByRole('button', { name: /cartes d'écolage/i }));
    fireEvent.click(screen.getByRole('button', { name: /imprimer : cartes d'écolage/i }));
    await waitFor(() => expect(ouvrirPdf).toHaveBeenCalledWith('/finance/pdf/cartes-ecolage/', { classes: [10], ordre: 'alpha' }));
  });

  test('l’état des salaires se demande par mois', async () => {
    monter();
    fireEvent.click(await screen.findByRole('button', { name: /état des salaires/i }));
    fireEvent.change(screen.getByLabelText(/mois payé/i), { target: { value: '2026-10' } });
    fireEvent.click(screen.getByRole('button', { name: /imprimer : état des salaires/i }));
    await waitFor(() => expect(ouvrirPdf).toHaveBeenCalledWith('/finance/pdf/etat-salaires/', { mois: '2026-10' }));
  });
});

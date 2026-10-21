import { render, screen } from '@testing-library/react';
import App from './App';

beforeEach(() => localStorage.clear());

test("affiche la page de connexion quand l'utilisateur n'est pas connecté", () => {
  window.history.pushState({}, '', '/');
  render(<App />);
  expect(screen.getByRole('heading', { name: /connexion/i })).toBeInTheDocument();
  expect(screen.getByLabelText(/nom d'utilisateur/i)).toBeInTheDocument();
});

test("une route inconnue redirige vers la connexion", () => {
  window.history.pushState({}, '', '/page-inexistante');
  render(<App />);
  expect(screen.getByRole('heading', { name: /connexion/i })).toBeInTheDocument();
});

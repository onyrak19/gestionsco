import axios from 'axios';
import { calculerApiUrl } from './adresse';

export const API_URL = calculerApiUrl(process.env.REACT_APP_API_URL, window.location);

const api = axios.create({
  baseURL: API_URL,
  headers: { 'Content-Type': 'application/json' },
});

// Endpoints publics : jamais de token envoyé, jamais de tentative de refresh
const estPublic = (url = '') =>
  url.includes('/auth/login/') || url.includes('/auth/inscription-enseignant/')
  || url.includes('/token/refresh/');

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token && !estPublic(config.url)) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

const terminerSession = () => {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  if (window.location.pathname !== '/login') window.location.href = '/login';
};

// Un seul renouvellement à la fois, partagé par toutes les requêtes en échec
let refreshEnCours = null;
const renouvelerToken = () => {
  if (!refreshEnCours) {
    const refresh = localStorage.getItem('refresh_token');
    refreshEnCours = axios
      .post(`${API_URL}/token/refresh/`, { refresh })
      .then((res) => {
        localStorage.setItem('access_token', res.data.access);
        if (res.data.refresh) localStorage.setItem('refresh_token', res.data.refresh);
        return res.data.access;
      })
      .finally(() => { refreshEnCours = null; });
  }
  return refreshEnCours;
};

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (
      error.response?.status === 401
      && originalRequest
      && !originalRequest._retry
      && !estPublic(originalRequest.url)
    ) {
      originalRequest._retry = true;
      if (localStorage.getItem('refresh_token')) {
        try {
          const access = await renouvelerToken();
          originalRequest.headers.Authorization = `Bearer ${access}`;
          return api(originalRequest);
        } catch (e) {
          // refresh refusé (expiré, compte désactivé...) : on quitte la session
        }
      }
      terminerSession();
    }
    return Promise.reject(error);
  }
);

export default api;

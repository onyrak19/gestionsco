import React, { createContext, useState, useContext, useEffect, useCallback } from 'react';
import api from '../api/axios';

const AuthContext = createContext();

const viderSession = () => {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!localStorage.getItem('access_token')) {
      setLoading(false);
      return;
    }
    api.get('/auth/profile/')
      .then((res) => setUser(res.data))
      .catch(() => { viderSession(); setUser(null); })
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (username, password) => {
    const res = await api.post('/auth/login/', { username, password });
    localStorage.setItem('access_token', res.data.access);
    localStorage.setItem('refresh_token', res.data.refresh);
    setUser(res.data.user);
    return res.data.user;
  }, []);

  const logout = useCallback(() => { viderSession(); setUser(null); }, []);

  const isAdmin = () => user?.profile?.role === 'admin';
  const isEnseignant = () => user?.profile?.role === 'enseignant';

  return (
    <AuthContext.Provider value={{ user, login, logout, loading, isAdmin, isEnseignant }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);

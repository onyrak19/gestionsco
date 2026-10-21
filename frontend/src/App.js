import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Layout from './components/Layout';
import Login from './components/Login';
import Accueil from './components/Accueil';
import InscriptionEnseignant from './components/InscriptionEnseignant';
import AdminDashboard from './components/admin/AdminDashboard';
import AnneesScolaires from './components/admin/AnneesScolaires';
import Classes from './components/admin/Classes';
import ClasseDetail from './components/admin/ClasseDetail';
import ClasseConfig from './components/admin/ClasseConfig';
import Releves from './components/admin/Releves';
import Impressions from './components/admin/Impressions';
import ImportExport from './components/admin/ImportExport';
import Journal from './components/admin/Journal';
import Parametres from './components/admin/Parametres';
import EleveDetail from './components/admin/EleveDetail';
import Matieres from './components/admin/Matieres';
import Eleves from './components/admin/Eleves';
import Inscriptions from './components/admin/Inscriptions';
import Affectations from './components/admin/Affectations';
import Enseignants from './components/admin/Enseignants';
import FinanceAccueil from './components/finance/FinanceAccueil';
import Encaissements from './components/finance/Encaissements';
import SituationEleve from './components/finance/SituationEleve';
import Paiements from './components/finance/Paiements';
import Tarifs from './components/finance/Tarifs';
import Mouvements from './components/finance/Mouvements';
import Categories from './components/finance/Categories';
import Employes from './components/finance/Employes';
import Salaires from './components/finance/Salaires';
import EnseignantDashboard from './components/enseignant/EnseignantDashboard';
import MesClasses from './components/enseignant/MesClasses';
import SaisieNotes from './components/enseignant/SaisieNotes';
import Resultats from './components/enseignant/Resultats';

const PrivateRoute = ({ children, adminOnly, enseignantOnly }) => {
  const { user, loading, isAdmin, isEnseignant } = useAuth();
  if (loading) return <div className="loading plein">Chargement…</div>;
  if (!user) return <Navigate to="/login" />;
  if (adminOnly && !isAdmin()) return <Navigate to="/" />;
  if (enseignantOnly && !isEnseignant()) return <Navigate to="/" />;
  return <Layout>{children || <Outlet />}</Layout>;
};

const HomeRedirect = () => {
  const { user, loading, isAdmin } = useAuth();
  if (loading) return <div className="loading plein">Chargement…</div>;
  if (!user) return <Navigate to="/login" />;
  return <Navigate to={isAdmin() ? '/admin' : '/enseignant'} />;
};

const App = () => (
  <AuthProvider>
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/inscription" element={<InscriptionEnseignant />} />
        <Route path="/" element={<HomeRedirect />} />

        <Route element={<PrivateRoute adminOnly />}>
          <Route path="/admin" element={<Accueil />} />
          <Route path="/admin/scolarite" element={<AdminDashboard />} />
          <Route path="/admin/annees" element={<AnneesScolaires />} />
          <Route path="/admin/classes" element={<Classes />} />
          <Route path="/admin/classes/:id" element={<ClasseDetail />} />
          <Route path="/admin/classes/:id/config" element={<ClasseConfig />} />
          <Route path="/admin/matieres" element={<Matieres />} />
          <Route path="/admin/eleves" element={<Eleves />} />
          <Route path="/admin/eleves/:id" element={<EleveDetail />} />
          <Route path="/admin/inscriptions" element={<Inscriptions />} />
          <Route path="/admin/affectations" element={<Affectations />} />
          <Route path="/admin/enseignants" element={<Enseignants />} />

          <Route path="/admin/finances" element={<FinanceAccueil />} />
          <Route path="/admin/finances/encaissements" element={<Encaissements />} />
          <Route path="/admin/finances/eleves/:id" element={<SituationEleve />} />
          <Route path="/admin/finances/paiements" element={<Paiements />} />
          <Route path="/admin/finances/tarifs" element={<Tarifs />} />
          <Route path="/admin/finances/depenses" element={<Mouvements sens="depense" />} />
          <Route path="/admin/finances/entrees" element={<Mouvements sens="entree" />} />
          <Route path="/admin/finances/categories" element={<Categories />} />
          <Route path="/admin/finances/employes" element={<Employes />} />
          <Route path="/admin/finances/salaires" element={<Salaires />} />

          <Route path="/admin/notes" element={<SaisieNotes />} />
          <Route path="/admin/releves" element={<Releves />} />
          <Route path="/admin/impressions" element={<Impressions />} />
          <Route path="/admin/bulletins" element={<Impressions documentInitial="bulletins" />} />
          <Route path="/admin/donnees" element={<ImportExport />} />
          <Route path="/admin/journal" element={<Journal />} />
          <Route path="/admin/parametres" element={<Parametres />} />
        </Route>

        <Route element={<PrivateRoute enseignantOnly />}>
          <Route path="/enseignant" element={<EnseignantDashboard />} />
          <Route path="/enseignant/classes" element={<MesClasses />} />
          <Route path="/enseignant/notes" element={<SaisieNotes />} />
          <Route path="/enseignant/resultats" element={<Resultats />} />
        </Route>

        <Route path="*" element={<Navigate to="/login" />} />
      </Routes>
    </BrowserRouter>
  </AuthProvider>
);

export default App;
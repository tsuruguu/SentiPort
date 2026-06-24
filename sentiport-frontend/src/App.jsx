import { BrowserRouter, Routes, Route } from 'react-router-dom';
import AppLayout from './components/AppLayout';
import DashboardPage from './pages/DashboardPage';
import InboxPage from './pages/InboxPage';
import NominationDetailPage from './pages/NominationDetailPage';
import BerthsPage from './pages/BerthsPage';
import ProvidersPage from './pages/ProvidersPage';
import { useApiData } from './hooks/useApiData';
import { nominationsApi } from './api/nominations';

export default function App() {
  // Liczba nominacji wymagających przeglądu - zasila badge "Skrzynka 13" w nawigacji.
  const { data } = useApiData(
    () => nominationsApi.list({ status: 'parsed_pending_review', limit: 1 }),
    []
  );
  const inboxCount = data?.total ?? 0;

  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout inboxCount={inboxCount} />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/panel/:nominationId" element={<DashboardPage />} />
          <Route path="/skrzynka" element={<InboxPage />} />
          <Route path="/skrzynka/:nominationId" element={<NominationDetailPage />} />
          <Route path="/dostawcy" element={<ProvidersPage />} />
          <Route path="/nadbrzeza" element={<BerthsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
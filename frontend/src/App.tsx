import { Navigate, Outlet, Route, BrowserRouter, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { TopBar } from "./components/TopBar";
import { LoginPage } from "./routes/LoginPage";
import { WorkbenchPage } from "./routes/WorkbenchPage";
import { DocumentsPage } from "./routes/DocumentsPage";
import { ConsolePage } from "./routes/ConsolePage";

function AppShell() {
  return (
    <>
      <a href="#main" className="skip-link">
        Skip to main content
      </a>
      <TopBar />
      <main id="main">
        <Outlet />
      </main>
    </>
  );
}

function RequireAuth() {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;
  return <AppShell />;
}

function RequireAdmin() {
  const { user } = useAuth();
  if (user?.role !== "admin") return <Navigate to="/" replace />;
  return <Outlet />;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<RequireAuth />}>
        <Route path="/" element={<WorkbenchPage />} />
        <Route path="/documents" element={<DocumentsPage />} />
        <Route element={<RequireAdmin />}>
          <Route path="/console" element={<ConsolePage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}

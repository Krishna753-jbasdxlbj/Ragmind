import { useAuth } from "./auth/AuthProvider";
import Login from "./pages/Login";
import Workspace from "./pages/Workspace";

export default function App() {
  const { session, loading } = useAuth();
  if (loading) return <div className="auth-wrap muted">Loading…</div>;
  return session ? <Workspace /> : <Login />;
}

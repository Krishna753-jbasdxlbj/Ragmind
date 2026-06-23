import { useState } from "react";
import { supabase } from "../lib/supabase";

export default function Login() {
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setNotice(null);
    setBusy(true);
    const fn =
      mode === "signin"
        ? supabase.auth.signInWithPassword({ email, password })
        : supabase.auth.signUp({ email, password });
    const { error } = await fn;
    setBusy(false);
    if (error) setError(error.message);
    else if (mode === "signup") setNotice("Account created. You can sign in now.");
  };

  return (
    <div className="auth-wrap">
      <div className="card auth-card">
        <div className="brand" style={{ marginBottom: 8 }}>
          <span className="dot" /> RAGmind
        </div>
        <h1>{mode === "signin" ? "Welcome back" : "Create account"}</h1>
        <p className="sub muted">Chat with your documents, grounded in the source.</p>
        <form onSubmit={submit}>
          <input
            type="email"
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={6}
            required
          />
          {error && <div className="error">{error}</div>}
          {notice && <div className="muted">{notice}</div>}
          <button className="btn-primary" type="submit" disabled={busy}>
            {busy ? "…" : mode === "signin" ? "Sign in" : "Sign up"}
          </button>
        </form>
        <div className="auth-toggle muted">
          {mode === "signin" ? "No account? " : "Have an account? "}
          <button onClick={() => setMode(mode === "signin" ? "signup" : "signin")}>
            {mode === "signin" ? "Sign up" : "Sign in"}
          </button>
        </div>
      </div>
    </div>
  );
}

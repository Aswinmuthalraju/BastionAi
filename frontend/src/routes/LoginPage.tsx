import { useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import styles from "./LoginPage.module.css";

export function LoginPage() {
  const { user, login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (user) return <Navigate to="/" replace />;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(username, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-in failed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className={styles.screen}>
      <div className={styles.card}>
        <svg className={styles.mark} viewBox="0 0 32 32" aria-hidden="true">
          <path
            d="M16 5 L26 9 V16 C26 22 21.5 26.5 16 28 C10.5 26.5 6 22 6 16 V9 Z"
            fill="none"
            stroke="var(--nominal)"
            strokeWidth="2"
          />
          <circle cx="16" cy="16" r="3.2" fill="var(--nominal)" />
        </svg>
        <h1 className={styles.title}>BastionAI</h1>
        <p className={styles.subtitle}>Sign in with your operator credentials</p>

        {error && (
          <div className={styles.error} role="alert">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate>
          <div className={styles.field}>
            <label className={styles.label} htmlFor="username">
              Username
            </label>
            <input
              id="username"
              className={styles.input}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              autoFocus
              required
            />
          </div>
          <div className={styles.field}>
            <label className={styles.label} htmlFor="password">
              Password
            </label>
            <input
              id="password"
              type="password"
              className={styles.input}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </div>
          <button type="submit" className={styles.submit} disabled={submitting}>
            {submitting ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <div className={styles.hint}>
          FIRST-RUN ACCOUNTS: operator · engineer · admin
          <br />
          Passwords are set in SETUP.md — rotate them before deployment.
        </div>
      </div>
    </div>
  );
}

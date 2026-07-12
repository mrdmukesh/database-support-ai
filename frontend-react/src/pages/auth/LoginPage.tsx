import { useState, type FormEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../../hooks/use-auth";
import type { LoginLocationState } from "../../routes/protected-route";

export function LoginPage() {
  const { login } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const destination = (location.state as LoginLocationState | null)?.from ?? "/app/dashboard";

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsLoading(true);
    try {
      await login({ email: email.trim(), password });
      navigate(destination, { replace: true });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Login failed.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-card" aria-labelledby="login-title">
        <p className="eyebrow">LegacyDB Support Copilot</p>
        <h1 id="login-title">Login</h1>
        <p>Sign in with the email and password supported by the current application.</p>
        <form onSubmit={handleSubmit}>
          <label htmlFor="login-email">Email</label>
          <input
            id="login-email"
            name="email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            disabled={isLoading}
            required
            aria-invalid={Boolean(error)}
            aria-describedby={error ? "login-error" : undefined}
          />
          <label htmlFor="login-password">Password</label>
          <input
            id="login-password"
            name="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            disabled={isLoading}
            required
            aria-invalid={Boolean(error)}
            aria-describedby={error ? "login-error" : undefined}
          />
          {error ? <div id="login-error" className="form-message error" role="alert">{error}</div> : null}
          <button type="submit" disabled={isLoading}>
            {isLoading ? "Logging in..." : "Login"}
          </button>
        </form>
      </section>
    </main>
  );
}

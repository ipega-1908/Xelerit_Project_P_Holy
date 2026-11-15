import { useState } from "react";

interface AdminAuthBarProps {
  adminUsername: string | null;
  onLogin: (username: string, password: string) => Promise<void>;
  onLogout: () => void;
}

export function AdminAuthBar({ adminUsername, onLogin, onLogout }: AdminAuthBarProps) {
  const [showForm, setShowForm] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (adminUsername !== null) {
    return (
      <div className="admin-auth-status">
        <span className="admin-badge">Admin: {adminUsername}</span>
        <button type="button" className="btn btn-secondary btn-sm" onClick={onLogout}>
          Wyloguj
        </button>
      </div>
    );
  }

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await onLogin(username.trim(), password);
      setUsername("");
      setPassword("");
      setShowForm(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się zalogować.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="admin-auth-wrapper">
      <button
        type="button"
        className="btn btn-secondary btn-sm"
        onClick={() => {
          setShowForm((prev) => !prev);
          setError(null);
        }}
      >
        {showForm ? "Zamknij logowanie" : "Logowanie admina"}
      </button>

      {showForm && (
        <form className="card admin-login-card" onSubmit={handleSubmit}>
          <div className="admin-login-fields">
            <input
              type="text"
              placeholder="Login admina"
              aria-label="Login admina"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              disabled={isSubmitting}
              required
            />
            <input
              type="password"
              placeholder="Hasło"
              aria-label="Hasło admina"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={isSubmitting}
              required
            />
            <button type="submit" className="btn btn-primary btn-sm" disabled={isSubmitting}>
              {isSubmitting ? "Logowanie..." : "Zaloguj"}
            </button>
          </div>
          {error && <p className="field-error">{error}</p>}
        </form>
      )}
    </div>
  );
}

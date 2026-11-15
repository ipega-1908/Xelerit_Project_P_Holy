import { useState } from "react";
import type { AuthSession } from "../types/api";

interface UserAuthBarProps {
  currentUser: AuthSession | null;
  onLogin: (username: string, password: string) => Promise<void>;
  onRegister: (username: string, password: string) => Promise<void>;
  onLogout: () => void;
}

export function UserAuthBar({
  currentUser,
  onLogin,
  onRegister,
  onLogout,
}: UserAuthBarProps) {
  const [showForm, setShowForm] = useState(false);
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (currentUser !== null) {
    return (
      <div className="admin-auth-status">
        <span className="user-badge">Kierowca: {currentUser.username}</span>
        <button type="button" className="btn btn-secondary btn-sm" onClick={onLogout}>
          Wyloguj
        </button>
      </div>
    );
  }

  const submitCredentials = async (targetMode: "login" | "register", user: string, pass: string) => {
    setError(null);
    setIsSubmitting(true);
    try {
      if (targetMode === "login") {
        await onLogin(user, pass);
      } else {
        await onRegister(user, pass);
      }
      setUsername("");
      setPassword("");
      setShowForm(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się uwierzytelnić.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await submitCredentials(mode, username.trim(), password);
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
        {showForm ? "Zamknij konto" : "Konto / Zaloguj"}
      </button>

      {showForm && (
        <form className="card admin-login-card user-auth-card" onSubmit={handleSubmit}>
          <div className="auth-mode-tabs">
            <button
              type="button"
              className={`btn btn-xs ${mode === "login" ? "btn-primary" : "btn-secondary"}`}
              onClick={() => {
                setMode("login");
                setError(null);
              }}
              disabled={isSubmitting}
            >
              Logowanie
            </button>
            <button
              type="button"
              className={`btn btn-xs ${mode === "register" ? "btn-primary" : "btn-secondary"}`}
              onClick={() => {
                setMode("register");
                setError(null);
              }}
              disabled={isSubmitting}
            >
              Rejestracja
            </button>
            <button
              type="button"
              className="btn btn-secondary btn-xs"
              onClick={() => void submitCredentials("login", "demo", "demo")}
              disabled={isSubmitting}
              title="Zaloguj się na konto testowe demo / demo"
            >
              Użyj demo (demo/demo)
            </button>
          </div>

          <div className="admin-login-fields">
            <input
              type="text"
              placeholder="Login (min. 3 znaki)"
              aria-label="Login użytkownika"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              disabled={isSubmitting}
              minLength={mode === "register" ? 3 : 1}
              required
            />
            <input
              type="password"
              placeholder="Hasło (min. 4 znaki)"
              aria-label="Hasło użytkownika"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={isSubmitting}
              minLength={mode === "register" ? 4 : 1}
              required
            />
            <button type="submit" className="btn btn-primary btn-sm" disabled={isSubmitting}>
              {isSubmitting
                ? "Przetwarzanie..."
                : mode === "login"
                  ? "Zaloguj"
                  : "Utwórz konto"}
            </button>
          </div>
          {error && <p className="field-error">{error}</p>}
        </form>
      )}
    </div>
  );
}

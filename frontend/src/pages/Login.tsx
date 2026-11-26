import { useState } from "react";
import { api, setToken } from "../api";

export default function Login({ onLogin }: { onLogin: (t: string) => void }) {
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const res = await api.login(email, name);
      setToken(res.token);
      onLogin(res.token);
    } catch (err) {
      setError(String(err));
    }
  }

  return (
    <div style={{ maxWidth: 380, margin: "80px auto", fontFamily: "sans-serif" }}>
      <h1>Appli web multiphysique</h1>
      <p>Connexion (mode développement : indique ton e-mail).</p>
      <form onSubmit={submit}>
        <p>
          <input
            type="email"
            required
            placeholder="e-mail"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            style={{ width: "100%", padding: 8 }}
          />
        </p>
        <p>
          <input
            placeholder="nom (optionnel)"
            value={name}
            onChange={(e) => setName(e.target.value)}
            style={{ width: "100%", padding: 8 }}
          />
        </p>
        <button type="submit" style={{ padding: "8px 16px" }}>
          Se connecter
        </button>
      </form>
      {error && <p style={{ color: "red" }}>{error}</p>}
    </div>
  );
}

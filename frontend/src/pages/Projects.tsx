import { useEffect, useState } from "react";
import { api, logout } from "../api";
import type { Project } from "../App";

export default function Projects({ onOpen }: { onOpen: (p: Project) => void }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");

  async function refresh() {
    try {
      setProjects(await api.projects());
    } catch (err) {
      setError(String(err));
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api.createProject(name, description);
      setName("");
      setDescription("");
      refresh();
    } catch (err) {
      setError(String(err));
    }
  }

  return (
    <div style={{ maxWidth: 720, margin: "40px auto", fontFamily: "sans-serif" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1>Mes projets</h1>
        <button
          onClick={() => {
            logout();
            location.reload();
          }}
        >
          Déconnexion
        </button>
      </div>
      <form onSubmit={create} style={{ display: "flex", gap: 8, marginBottom: 24 }}>
        <input
          required
          placeholder="nom du projet"
          value={name}
          onChange={(e) => setName(e.target.value)}
          style={{ flex: 1, padding: 8 }}
        />
        <input
          placeholder="description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          style={{ flex: 2, padding: 8 }}
        />
        <button type="submit" style={{ padding: "8px 16px" }}>
          Créer
        </button>
      </form>
      {error && <p style={{ color: "red" }}>{error}</p>}
      <ul style={{ listStyle: "none", padding: 0 }}>
        {projects.map((p) => (
          <li
            key={p.id}
            onClick={() => onOpen(p)}
            style={{ border: "1px solid #ddd", borderRadius: 6, padding: 12, marginBottom: 8, cursor: "pointer" }}
          >
            <strong>{p.name}</strong>
            <div style={{ color: "#555" }}>{p.description}</div>
          </li>
        ))}
        {projects.length === 0 && <p>Aucun projet pour le moment.</p>}
      </ul>
    </div>
  );
}

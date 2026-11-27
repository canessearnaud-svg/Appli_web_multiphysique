import { useState } from "react";
import { getToken } from "./api";
import Login from "./pages/Login";
import Projects from "./pages/Projects";
import ProjectPage from "./pages/Project";

export type Project = {
  id: number;
  name: string;
  description: string;
  created_at: string;
};

export default function App() {
  const [token, setTok] = useState<string | null>(getToken());
  const [selected, setSelected] = useState<Project | null>(null);

  if (!token) return <Login onLogin={(t) => setTok(t)} />;
  if (selected) return <ProjectPage project={selected} onBack={() => setSelected(null)} />;
  return <Projects onOpen={setSelected} />;
}

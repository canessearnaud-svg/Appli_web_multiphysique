import type { Project } from "../App";
import KinematicsEditor from "./KinematicsEditor";

export default function ProjectPage({ project, onBack }: { project: Project; onBack: () => void }) {
  return <KinematicsEditor project={project} onBack={onBack} />;
}

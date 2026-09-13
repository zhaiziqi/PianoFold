import { midiUrl, musicxmlUrl } from "../lib/api";
import type { Difficulty } from "../lib/project";

export function DownloadActions({ projectId, difficulty }: { projectId: string; difficulty: Difficulty }) {
  return (
    <nav className="download-actions" aria-label="Arrangement downloads">
      <a className="button" href={midiUrl(projectId, difficulty)} download>Download MIDI <span aria-hidden="true">↓</span></a>
      <a className="button" href={musicxmlUrl(projectId, difficulty)} download>Download MusicXML <span aria-hidden="true">↓</span></a>
    </nav>
  );
}

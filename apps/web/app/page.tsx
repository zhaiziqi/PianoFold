"use client";

import { useEffect, useRef, useState } from "react";
import { DifficultySelector } from "../components/difficulty-selector";
import { DownloadActions } from "../components/download-actions";
import { ProcessingStatus } from "../components/processing-status";
import { UploadDropzone } from "../components/upload-dropzone";
import { ScoreViewer } from "../components/score-viewer";
import { AudioPlayer } from "../components/audio-player";
import { MidiPlayer } from "../components/midi-player";
import { getProject, regenerateProject, uploadProject } from "../lib/api";
import type { Difficulty, ProjectMetadata } from "../lib/project";

function message(error: unknown) {
  return error instanceof Error ? error.message : "Something went wrong. Please try again.";
}

export default function Home() {
  const [fileName, setFileName] = useState<string | null>(null);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [project, setProject] = useState<ProjectMetadata | null>(null);
  const [difficulty, setDifficulty] = useState<Difficulty>("standard");
  const [uploading, setUploading] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [generation, setGeneration] = useState(0);
  const requestVersion = useRef(0);
  const terminal = project?.status === "done" || project?.status === "failed";

  useEffect(() => () => { requestVersion.current += 1; }, []);

  useEffect(() => {
    if (!projectId || terminal) return;
    let active = true;
    let inFlight = false;
    const version = requestVersion.current;

    async function poll() {
      if (!active || inFlight || version !== requestVersion.current) return;
      inFlight = true;
      try {
        const next = await getProject(projectId!);
        if (!active || version !== requestVersion.current) return;
        setProject(next);
        setError(null);
        if (next.status === "done" || next.status === "failed") {
          active = false;
          window.clearInterval(timer);
        }
      } catch (cause) {
        if (active && version === requestVersion.current) setError(message(cause));
      } finally {
        inFlight = false;
      }
    }

    const timer = window.setInterval(() => { void poll(); }, 1000);
    void poll();
    return () => { active = false; window.clearInterval(timer); };
  }, [projectId, terminal, generation]);

  async function selectFile(file: File) {
    // A selection invalidates both pending uploads and pending status responses.
    const version = ++requestVersion.current;
    setGeneration(version);
    setFileName(file.name);
    setProjectId(null);
    setProject(null);
    setDifficulty("standard");
    setError(null);
    setUploading(true);
    try {
      const submission = await uploadProject(file);
      if (version !== requestVersion.current) return;
      setProjectId(submission.project_id);
    } catch (cause) {
      if (version === requestVersion.current) setError(message(cause));
    } finally {
      if (version === requestVersion.current) setUploading(false);
    }
  }

  async function regenerate() {
    if (!project || regenerating) return;
    setRegenerating(true);
    setError(null);
    try {
      await regenerateProject(project.project_id);
      setProject({ ...project, status: "processing", stage: "transcribing", progress: 0, error: null, duration: null, melody_mode: null, notice: null, generation: project.generation + 1 });
      setGeneration((value) => value + 1);
    } catch (cause) {
      setError(message(cause));
    } finally {
      setRegenerating(false);
    }
  }

  return (
    <main className="workspace mx-auto w-full max-w-5xl">
      <header className="masthead">
        <div><p className="eyebrow">A song. A piano. Your arrangement.</p><h1>PianoFold</h1></div>
        <span className="edition">THE LOCAL WORKSPACE <span aria-hidden="true"> / </span> 01</span>
      </header>

      {!fileName && <section className="introduction"><h2>Make room for<br /><em>your next song.</em></h2><p>Bring a recording. Find a piano arrangement that feels right in your hands.</p></section>}

      {fileName && (
        <section className="song-heading" aria-label="Current song">
          <p className="eyebrow">On the music stand</p>
          <h2>{fileName}</h2>
        </section>
      )}

      {uploading && <p role="status" className="pending-message">Uploading your song…</p>}
      {projectId && !project && <p role="status" className="pending-message">Checking your arrangement…</p>}
      {error && <p className="error-message" role="alert">{error}</p>}
      {project && project.status !== "done" && <ProcessingStatus project={project} />}

      {project?.status === "done" && (
        <section className="arrangement" aria-labelledby="arrangement-heading">
          <div className="section-heading"><h2 id="arrangement-heading">Your piano arrangement</h2><span className="ready-label">Ready to play</span></div>
          <p className="project-id">Project ID <code>{project.project_id}</code></p>
          {project.notice && <p className="muted" role="status">{project.notice}</p>}
          <button type="button" className="button mb-6" disabled={regenerating} onClick={() => { void regenerate(); }}>
            {regenerating ? "Starting improved arrangement…" : "Regenerate with improved melody"}
          </button>
          <DifficultySelector value={difficulty} onChange={setDifficulty} />
          <DownloadActions projectId={project.project_id} difficulty={difficulty} />
          <ScoreViewer projectId={project.project_id} difficulty={difficulty} />
          <div className="mt-8 grid gap-8 border-t border-[var(--rule)] pt-6 sm:grid-cols-2">
            <AudioPlayer projectId={project.project_id} />
            <MidiPlayer projectId={project.project_id} difficulty={difficulty} />
          </div>
        </section>
      )}

      <UploadDropzone onFile={(file) => { void selectFile(file); }} compact={!!fileName} />
      <footer className="workspace-footer"><span>Made for the music stand.</span><span>Three versions. Your own pace.</span></footer>
    </main>
  );
}

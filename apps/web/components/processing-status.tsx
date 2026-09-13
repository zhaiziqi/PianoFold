import { PROJECT_STAGES, type ProjectMetadata } from "../lib/project";

export function ProcessingStatus({ project }: { project: ProjectMetadata }) {
  const percentage = Math.round(Math.max(0, Math.min(1, project.progress)) * 100);
  const failed = project.status === "failed";

  return (
    <section className="processing-panel" aria-label="Arrangement progress">
      <div className="section-heading" role="status" aria-live="polite">
        <h2>{PROJECT_STAGES[project.stage]}</h2>
        {!failed && <span className="progress-number">{percentage}%</span>}
      </div>
      {!failed && (
        <div className="progress-track" role="progressbar" aria-label="Arrangement progress" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percentage}>
          <div className="progress-fill" style={{ width: `${percentage}%` }} />
        </div>
      )}
      {failed
        ? <p className="error-message" role="alert">{project.error || "This song could not be processed. Please try another audio file."}</p>
        : <p className="muted">Your piano versions are taking shape. You can leave this page open while they finish.</p>}
    </section>
  );
}

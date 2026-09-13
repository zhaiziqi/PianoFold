import { DIFFICULTIES } from "./project";
import type { Difficulty, ProjectMetadata, ProjectSubmission } from "./project";

export class ApiError extends Error {
  constructor(message: string, public readonly status: number) {
    super(message);
    this.name = "ApiError";
  }
}

function errorDetail(payload: unknown): string | undefined {
  if (!payload || typeof payload !== "object" || !("detail" in payload)) return;
  const detail: unknown = payload.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const messages = detail.flatMap((entry: unknown) => {
      if (entry && typeof entry === "object" && "msg" in entry &&
          typeof entry.msg === "string" && entry.msg.trim()) {
        return [entry.msg];
      }
      return [];
    });
    return messages.join("; ") || undefined;
  }
}

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(url, options);
  } catch {
    throw new ApiError("Unable to reach the local API. Check that it is running.", 0);
  }

  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    if (response.ok) {
      throw new ApiError("The API returned an invalid JSON response.", response.status);
    }
  }

  if (!response.ok) {
    throw new ApiError(
      errorDetail(payload) ?? `Request failed (HTTP ${response.status}).`,
      response.status,
    );
  }
  return payload as T;
}

function projectUrl(projectId: string): string {
  // Dot segments survive encodeURIComponent and are normalized by browsers.
  if (!projectId || projectId === "." || projectId === "..") {
    throw new TypeError("Invalid project ID");
  }
  return `/api/projects/${encodeURIComponent(projectId)}`;
}

function arrangementUrl(projectId: string, difficulty: Difficulty): string {
  if (!DIFFICULTIES.includes(difficulty)) {
    throw new TypeError("Invalid difficulty");
  }
  return `${projectUrl(projectId)}/arrangements/${difficulty}`;
}

export async function uploadProject(file: File): Promise<ProjectSubmission> {
  const data = new FormData();
  data.append("audio", file);
  // Do not set Content-Type: the browser supplies the multipart boundary.
  return request("/api/projects", { method: "POST", body: data });
}

export async function getProject(projectId: string): Promise<ProjectMetadata> {
  return request(projectUrl(projectId), { cache: "no-store" });
}

export async function regenerateProject(projectId: string): Promise<ProjectSubmission> {
  return request(`${projectUrl(projectId)}/regenerate`, { method: "POST" });
}

export function audioUrl(projectId: string): string {
  return `${projectUrl(projectId)}/audio`;
}

export function midiUrl(projectId: string, difficulty: Difficulty): string {
  return `${arrangementUrl(projectId, difficulty)}/midi`;
}

export function musicxmlUrl(projectId: string, difficulty: Difficulty): string {
  return `${arrangementUrl(projectId, difficulty)}/musicxml`;
}

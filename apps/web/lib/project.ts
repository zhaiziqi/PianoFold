export const DIFFICULTIES = ["simple", "standard", "rich"] as const;
export type Difficulty = (typeof DIFFICULTIES)[number];

export type ProjectStatus = "uploaded" | "processing" | "done" | "failed";

export const PROJECT_STAGES = {
  uploaded: "Uploaded",
  transcribing: "Finding the vocal melody",
  analyzing: "Analyzing the music",
  arranging: "Creating piano arrangements",
  exporting: "Preparing scores and downloads",
  done: "Ready to play",
  failed: "Processing failed",
} as const;
export type ProjectStage = keyof typeof PROJECT_STAGES;

export interface ProjectSubmission {
  project_id: string;
  status: "processing";
}

/** JSON fields returned by the persisted local project API. */
export interface ProjectMetadata {
  project_id: string;
  status: ProjectStatus;
  stage: ProjectStage;
  progress: number;
  error: string | null;
  duration: number | null;
  model: string;
  device: string;
  profiles: string[];
  melody_mode: "vocal" | "instrumental" | null;
  notice: string | null;
  generation: number;
}

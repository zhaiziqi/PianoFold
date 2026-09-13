"use client";

import { audioUrl } from "../lib/api";

export function AudioPlayer({ projectId }: { projectId: string }) {
  return (
    <section aria-label="Original recording">
      <h3 className="eyebrow mb-3">Original recording</h3>
      <audio key={projectId} controls preload="none" aria-label="Original audio" src={audioUrl(projectId)} className="w-full" />
    </section>
  );
}

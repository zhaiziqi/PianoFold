"use client";

import { useEffect, useRef, useState } from "react";
import { musicxmlUrl } from "../lib/api";
import type { Difficulty } from "../lib/project";
import type { OpenSheetMusicDisplay } from "opensheetmusicdisplay";

export function ScoreViewer({ projectId, difficulty }: { projectId: string; difficulty: Difficulty }) {
  const container = useRef<HTMLDivElement>(null);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const target = container.current!;
    const controller = new AbortController();
    let active = true;
    let renderer: OpenSheetMusicDisplay | undefined;
    let observer: ResizeObserver | undefined;
    target.replaceChildren();
    setError(false);
    setLoading(true);

    function fail() {
      if (!active) return;
      observer?.disconnect();
      target.replaceChildren();
      setError(true);
      setLoading(false);
    }

    async function load() {
      try {
        const response = await fetch(musicxmlUrl(projectId, difficulty), { signal: controller.signal });
        if (!response.ok) throw new Error("Score request failed");
        const xml = await response.text();
        if (!active) return;
        const { OpenSheetMusicDisplay } = await import("opensheetmusicdisplay");
        if (!active) return;
        // Each load owns a detached-able host, so late library work cannot draw over a new score.
        const host = document.createElement("div");
        target.replaceChildren(host);
        renderer = new OpenSheetMusicDisplay(host, { backend: "svg", autoResize: false });
        await renderer.load(xml);
        if (!active) return;
        renderer.render();
        setLoading(false);
        if (typeof ResizeObserver !== "undefined") {
          let width = target.clientWidth;
          observer = new ResizeObserver(() => {
            if (!active || target.clientWidth === width) return;
            width = target.clientWidth;
            try { renderer?.render(); } catch { fail(); }
          });
          observer.observe(target);
        }
      } catch { fail(); }
    }

    void load();
    return () => {
      active = false;
      controller.abort();
      observer?.disconnect();
      renderer?.clear();
      target.replaceChildren();
    };
  }, [projectId, difficulty]);

  return (
    <section className="mt-8 border-t border-[var(--rule)] pt-6" aria-label="Selected sheet music">
      <h3 className="eyebrow mb-4">The piano score</h3>
      {loading && <p role="status" className="muted">Opening your score…</p>}
      {error && <p role="alert" className="error-message">The score could not be displayed. You can still download the MusicXML above.</p>}
      <div ref={container} aria-label="Piano score" aria-busy={loading} className="min-w-0 overflow-x-auto bg-[#fffdf7]" />
    </section>
  );
}

"use client";

import { useEffect, useRef, useState } from "react";
import { midiUrl } from "../lib/api";
import type { Difficulty } from "../lib/project";

type PlaybackState = "idle" | "loading" | "playing" | "stopped";

const SALAMANDER_SAMPLES = {
  A0: "A0.mp3", C1: "C1.mp3", "D#1": "Ds1.mp3", "F#1": "Fs1.mp3",
  A1: "A1.mp3", C2: "C2.mp3", "D#2": "Ds2.mp3", "F#2": "Fs2.mp3",
  A2: "A2.mp3", C3: "C3.mp3", "D#3": "Ds3.mp3", "F#3": "Fs3.mp3",
  A3: "A3.mp3", C4: "C4.mp3", "D#4": "Ds4.mp3", "F#4": "Fs4.mp3",
  A4: "A4.mp3", C5: "C5.mp3", "D#5": "Ds5.mp3", "F#5": "Fs5.mp3",
  A5: "A5.mp3", C6: "C6.mp3", "D#6": "Ds6.mp3", "F#6": "Fs6.mp3",
  A6: "A6.mp3", C7: "C7.mp3",
} as const;

export function MidiPlayer({ projectId, difficulty }: { projectId: string; difficulty: Difficulty }) {
  const [state, setState] = useState<PlaybackState>("idle");
  const [error, setError] = useState(false);
  const version = useRef(0);
  const cleanup = useRef<() => void>(() => {});

  useEffect(() => {
    setState("idle");
    setError(false);
    return () => { version.current += 1; cleanup.current(); };
  }, [projectId, difficulty]);

  function stop() {
    version.current += 1;
    cleanup.current();
    setState("stopped");
  }

  async function play() {
    const current = ++version.current;
    cleanup.current();
    const controller = new AbortController();
    let release = () => {};
    cleanup.current = () => { controller.abort(); release(); };
    setError(false);
    setState("loading");

    try {
      // Importing Tone can create an audio context: keep the entire import behind the gesture.
      const [Tone, { Midi }] = await Promise.all([import("tone"), import("@tonejs/midi")]);
      if (current !== version.current) return;
      await Tone.start();
      if (current !== version.current) return;
      const response = await fetch(midiUrl(projectId, difficulty), { signal: controller.signal });
      if (!response.ok) throw new Error("MIDI request failed");
      const bytes = await response.arrayBuffer();
      if (current !== version.current) return;
      const midi = new Midi(bytes);
      const transport = Tone.getTransport();
      const piano = new Tone.Sampler({
        urls: SALAMANDER_SAMPLES,
        baseUrl: "/piano/salamander/",
        release: 1.4,
      }).toDestination();
      await Tone.loaded();
      if (current !== version.current) {
        piano.dispose();
        return;
      }
      const events: number[] = [];
      let finishTimer: number | undefined;
      let disposed = false;
      release = () => {
        if (disposed) return;
        disposed = true;
        window.clearTimeout(finishTimer);
        transport.stop();
        events.forEach((id) => transport.clear(id));
        transport.cancel();
        transport.seconds = 0;
        piano.releaseAll();
        piano.dispose();
      };
      transport.stop();
      transport.cancel();
      transport.seconds = 0;
      for (const track of midi.tracks) {
        for (const note of track.notes) {
          events.push(transport.schedule((time) => {
            if (current === version.current) piano.triggerAttackRelease(note.name, note.duration, time, note.velocity);
          }, note.time));
        }
      }
      events.push(transport.schedule((time) => {
        // Transport looks ahead. Wait for actual audio time, even when animation frames are suspended.
        finishTimer = window.setTimeout(() => {
          if (current !== version.current) return;
          release();
          setState("stopped");
        }, Math.max(0, (time - Tone.immediate()) * 1000));
      }, midi.duration));
      transport.start();
      setState("playing");
    } catch {
      if (current !== version.current) return;
      cleanup.current();
      setError(true);
      setState("idle");
    }
  }

  return (
    <section aria-label="Piano playback">
      <h3 className="eyebrow mb-3">Piano arrangement</h3>
      <div className="flex flex-wrap gap-2">
        <button type="button" className="button button--solid disabled:cursor-wait disabled:opacity-50" disabled={state === "loading"} onClick={() => { void play(); }}>
          {state === "loading" ? "Loading piano…" : state === "idle" ? "Play piano" : "Restart piano"}
        </button>
        <button type="button" className="button disabled:cursor-default disabled:opacity-40" disabled={state === "idle" || state === "stopped"} onClick={stop}>Stop piano</button>
      </div>
      <p className="muted" role="status">{state === "playing" ? "Playing the selected arrangement." : "A sampled acoustic piano preview. Play each recording independently."}</p>
      {error && <p role="alert" className="error-message">Piano playback could not start. Please try again.</p>}
    </section>
  );
}

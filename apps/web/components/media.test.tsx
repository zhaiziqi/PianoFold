import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ScoreViewer } from "./score-viewer";
import { AudioPlayer } from "./audio-player";
import { MidiPlayer } from "./midi-player";

const mocks = vi.hoisted(() => ({
  load: vi.fn(), render: vi.fn(), clear: vi.fn(), score: vi.fn(),
  start: vi.fn(), synth: vi.fn(), attack: vi.fn(), dispose: vi.fn(), release: vi.fn(),
  midi: vi.fn(), transportStart: vi.fn(), stop: vi.fn(), cancel: vi.fn(), schedule: vi.fn(), clearEvent: vi.fn(),
  immediate: vi.fn(),
}));
vi.mock("opensheetmusicdisplay", () => ({ OpenSheetMusicDisplay: class {
  constructor(container: HTMLElement, options: unknown) { mocks.score(container, options); }
  load = mocks.load; render = mocks.render; clear = mocks.clear;
} }));
vi.mock("tone", () => ({
  start: mocks.start, Synth: class {}, PolySynth: class {
    constructor() { mocks.synth(); }
    toDestination() { return this; }
    triggerAttackRelease = mocks.attack; releaseAll = mocks.release; dispose = mocks.dispose;
  },
  getTransport: () => ({ start: mocks.transportStart, stop: mocks.stop, cancel: mocks.cancel,
    schedule: mocks.schedule, clear: mocks.clearEvent, seconds: 0 }),
  immediate: mocks.immediate,
  // Browser animation callbacks may be suspended in a background tab.
  getDraw: () => ({ schedule: vi.fn() }),
}));
vi.mock("@tonejs/midi", () => ({ Midi: class {
  constructor(bytes: ArrayBuffer) { mocks.midi(bytes); }
  duration = 2;
  tracks = [{ notes: [{ name: "C4", time: 0, duration: 0.5, velocity: 0.8 }, { name: "E4", time: 1, duration: 1, velocity: 0.6 }] }];
} }));

const PROJECT = "11111111-1111-4111-8111-111111111111";
const bytes = new ArrayBuffer(8);
const deferred = <T,>() => {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((res) => { resolve = res; });
  return { promise, resolve };
};
beforeEach(() => {
  vi.clearAllMocks();
  mocks.load.mockReset().mockResolvedValue(undefined);
  mocks.render.mockReset();
  mocks.start.mockReset().mockResolvedValue(undefined);
  mocks.immediate.mockReturnValue(0);
  mocks.schedule.mockImplementation((_callback, time) => time + 10);
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, text: async () => "<score-partwise/>", arrayBuffer: async () => bytes }));
});
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

describe("score viewer", () => {
  it("fetches the selected score, clears old notation, and loads the new selection", async () => {
    const { rerender, unmount } = render(<ScoreViewer projectId={PROJECT} difficulty="simple" />);
    await waitFor(() => expect(mocks.render).toHaveBeenCalledOnce());
    expect(fetch).toHaveBeenCalledWith(`/api/projects/${PROJECT}/arrangements/simple/musicxml`, expect.objectContaining({ signal: expect.any(AbortSignal) }));
    expect(mocks.load).toHaveBeenCalledWith("<score-partwise/>");
    const container = screen.getByLabelText("Piano score");
    container.append(document.createElement("svg"));
    rerender(<ScoreViewer projectId={PROJECT} difficulty="rich" />);
    expect(container).toBeEmptyDOMElement();
    await waitFor(() => expect(mocks.render).toHaveBeenCalledTimes(2));
    expect(fetch).toHaveBeenLastCalledWith(`/api/projects/${PROJECT}/arrangements/rich/musicxml`, expect.objectContaining({ signal: expect.any(AbortSignal) }));
    expect(mocks.clear).toHaveBeenCalledOnce();
    unmount();
    expect(mocks.clear).toHaveBeenCalledTimes(2);
  });

  it("shows a fallback for load failure and clears it when another version loads", async () => {
    mocks.load.mockRejectedValueOnce(new Error("invalid XML"));
    const { rerender } = render(<ScoreViewer projectId={PROJECT} difficulty="simple" />);
    expect(await screen.findByRole("alert")).toHaveTextContent(/score could not be displayed/i);
    expect(screen.getByLabelText("Piano score")).toBeEmptyDOMElement();
    rerender(<ScoreViewer projectId={PROJECT} difficulty="rich" />);
    await waitFor(() => expect(mocks.render).toHaveBeenCalledOnce());
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("does not render stale scores after selection changes or unmount", async () => {
    const pending = deferred<void>();
    mocks.load.mockReturnValueOnce(pending.promise);
    const { rerender, unmount } = render(<ScoreViewer projectId={PROJECT} difficulty="simple" />);
    await waitFor(() => expect(mocks.load).toHaveBeenCalledOnce());
    const signal = vi.mocked(fetch).mock.calls[0][1]?.signal;
    rerender(<ScoreViewer projectId={PROJECT} difficulty="rich" />);
    await waitFor(() => expect(mocks.render).toHaveBeenCalledOnce());
    expect(signal?.aborted).toBe(true);
    unmount();
    await act(async () => { pending.resolve(); });
    expect(mocks.render).toHaveBeenCalledOnce();
  });

  it("does not pass an HTTP error page to the renderer", async () => {
    vi.mocked(fetch).mockResolvedValueOnce({ ok: false } as Response);
    render(<ScoreViewer projectId={PROJECT} difficulty="simple" />);
    expect(await screen.findByRole("alert")).toHaveTextContent(/score could not be displayed/i);
    expect(mocks.load).not.toHaveBeenCalled();
  });
});

describe("independent players", () => {
  it("points native original controls at the audio route without starting playback", () => {
    render(<AudioPlayer projectId={PROJECT} />);
    expect(screen.getByLabelText("Original audio")).toHaveAttribute("src", `/api/projects/${PROJECT}/audio`);
    expect(screen.getByLabelText("Original audio")).toHaveAttribute("controls");
    expect(screen.getByLabelText("Original audio")).not.toHaveAttribute("autoplay");
  });

  it("initializes only after a click, parses selected bytes, and schedules audible notes", async () => {
    render(<><AudioPlayer projectId={PROJECT} /><MidiPlayer projectId={PROJECT} difficulty="standard" /></>);
    expect(mocks.start).not.toHaveBeenCalled();
    expect(mocks.synth).not.toHaveBeenCalled();
    expect(fetch).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: /play piano/i }));
    await waitFor(() => expect(mocks.transportStart).toHaveBeenCalledOnce());
    expect(mocks.start).toHaveBeenCalledOnce();
    expect(fetch).toHaveBeenCalledWith(`/api/projects/${PROJECT}/arrangements/standard/midi`, expect.objectContaining({ signal: expect.any(AbortSignal) }));
    expect(mocks.midi).toHaveBeenCalledWith(bytes);
    expect(mocks.schedule.mock.calls.map((call) => call[1])).toEqual([0, 1, 2]);
    act(() => { mocks.schedule.mock.calls[0][0](0.125); });
    expect(mocks.attack).toHaveBeenCalledWith("C4", 0.5, 0.125, 0.8);
    expect(screen.getByLabelText("Original audio")).toHaveAttribute("src", `/api/projects/${PROJECT}/audio`);
    expect(screen.getByRole("button", { name: /stop piano/i })).toBeEnabled();
  });

  it("stops and restarts from the beginning without retaining synths or events", async () => {
    render(<MidiPlayer projectId={PROJECT} difficulty="simple" />);
    fireEvent.click(screen.getByRole("button", { name: /play piano/i }));
    await waitFor(() => expect(mocks.transportStart).toHaveBeenCalledOnce());
    fireEvent.click(screen.getByRole("button", { name: /stop piano/i }));
    expect(mocks.dispose).toHaveBeenCalledOnce();
    expect(mocks.release).toHaveBeenCalledOnce();
    expect(mocks.stop).toHaveBeenCalled();
    expect(mocks.cancel).toHaveBeenCalled();
    expect(mocks.clearEvent).toHaveBeenCalledTimes(3);
    fireEvent.click(screen.getByRole("button", { name: /restart piano/i }));
    await waitFor(() => expect(mocks.transportStart).toHaveBeenCalledTimes(2));
    expect(mocks.synth).toHaveBeenCalledTimes(2);
  });

  it("disposes playing resources on difficulty change and unmount", async () => {
    const { rerender, unmount } = render(<MidiPlayer projectId={PROJECT} difficulty="simple" />);
    fireEvent.click(screen.getByRole("button", { name: /play piano/i }));
    await waitFor(() => expect(mocks.transportStart).toHaveBeenCalledOnce());
    rerender(<MidiPlayer projectId={PROJECT} difficulty="rich" />);
    expect(mocks.dispose).toHaveBeenCalledOnce();
    expect(screen.getByRole("button", { name: /play piano/i })).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: /play piano/i }));
    await waitFor(() => expect(mocks.transportStart).toHaveBeenCalledTimes(2));
    expect(fetch).toHaveBeenLastCalledWith(`/api/projects/${PROJECT}/arrangements/rich/midi`, expect.objectContaining({ signal: expect.any(AbortSignal) }));
    unmount();
    expect(mocks.dispose).toHaveBeenCalledTimes(2);
  });

  it("ignores a MIDI response completing after a version change", async () => {
    const pending = deferred<Response>();
    vi.mocked(fetch).mockReturnValueOnce(pending.promise);
    const { rerender } = render(<MidiPlayer projectId={PROJECT} difficulty="simple" />);
    fireEvent.click(screen.getByRole("button", { name: /play piano/i }));
    await waitFor(() => expect(fetch).toHaveBeenCalledOnce());
    const signal = vi.mocked(fetch).mock.calls[0][1]?.signal;
    rerender(<MidiPlayer projectId={PROJECT} difficulty="rich" />);
    await act(async () => { pending.resolve({ ok: true, arrayBuffer: async () => bytes } as Response); });
    expect(signal?.aborted).toBe(true);
    expect(mocks.synth).not.toHaveBeenCalled();
    expect(mocks.transportStart).not.toHaveBeenCalled();
  });

  it("offers retry after MIDI fetch failure without starting transport", async () => {
    vi.mocked(fetch).mockResolvedValueOnce({ ok: false } as Response);
    render(<MidiPlayer projectId={PROJECT} difficulty="simple" />);
    fireEvent.click(screen.getByRole("button", { name: /play piano/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/piano playback could not start/i);
    expect(mocks.transportStart).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: /play piano/i }));
    await waitFor(() => expect(mocks.transportStart).toHaveBeenCalledOnce());
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("waits until audio time ends then resets controls without requiring animation frames", async () => {
    render(<MidiPlayer projectId={PROJECT} difficulty="standard" />);
    fireEvent.click(screen.getByRole("button", { name: /play piano/i }));
    await waitFor(() => expect(mocks.transportStart).toHaveBeenCalledOnce());
    vi.useFakeTimers();
    act(() => { mocks.schedule.mock.calls[2][0](2); });
    act(() => { vi.advanceTimersByTime(1999); });
    expect(screen.getByRole("button", { name: /stop piano/i })).toBeEnabled();
    act(() => { vi.advanceTimersByTime(1); });
    expect(screen.getByRole("button", { name: /stop piano/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /restart piano/i })).toBeEnabled();
    vi.useRealTimers();
  });
});

import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import Home from "../app/page";
import { getProject, uploadProject } from "../lib/api";
import { PROJECT_STAGES, type ProjectMetadata } from "../lib/project";
import { ProcessingStatus } from "./processing-status";

vi.mock("../lib/api", async (importOriginal) => ({
  ...await importOriginal<typeof import("../lib/api")>(),
  uploadProject: vi.fn(),
  getProject: vi.fn(),
}));

const PROJECT_ID = "11111111-1111-4111-8111-111111111111";
const OTHER_ID = "22222222-2222-4222-8222-222222222222";
const wav = new File(["audio"], "Evening song.wav", { type: "audio/wav" });
const metadata = (overrides: Partial<ProjectMetadata> = {}): ProjectMetadata => ({
  project_id: PROJECT_ID, status: "processing", stage: "transcribing", progress: 0.2,
  error: null, duration: null, model: "model", device: "cpu", profiles: [], ...overrides,
});
const done = metadata({ status: "done", stage: "done", progress: 1 });
const deferred = <T,>() => {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((res) => { resolve = res; });
  return { promise, resolve };
};
async function choose(file = wav) {
  await act(async () => { fireEvent.change(screen.getByLabelText(/choose a song/i), { target: { files: [file] } }); });
}
async function tick(ms = 1000) {
  await act(async () => { await vi.advanceTimersByTimeAsync(ms); });
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.mocked(uploadProject).mockReset().mockResolvedValue({ project_id: PROJECT_ID, status: "processing" });
  vi.mocked(getProject).mockReset().mockResolvedValue(metadata());
});
afterEach(() => { vi.useRealTimers(); });

describe("local workspace", () => {
  it("starts ready with an accessible supported-format file picker", () => {
    render(<Home />);
    expect(screen.getByRole("heading", { name: "PianoFold" })).toBeVisible();
    expect(screen.getByLabelText(/choose a song/i)).toHaveAttribute("accept", ".mp3,.wav,.m4a,.flac");
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /download/i })).not.toBeInTheDocument();
  });

  it("submits a dropped file and polls every second until done", async () => {
    vi.mocked(getProject).mockResolvedValueOnce(metadata()).mockResolvedValue(done);
    render(<Home />);
    await act(async () => { fireEvent.drop(screen.getByTestId("upload-dropzone"), { dataTransfer: { files: [wav] } }); });
    expect(uploadProject).toHaveBeenCalledWith(wav);
    expect(screen.getByText("Transcribing audio")).toBeVisible();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "20");
    await tick(999);
    expect(getProject).toHaveBeenCalledTimes(1);
    await tick(1);
    expect(screen.getByRole("heading", { name: /your piano arrangement/i })).toBeVisible();
    expect(screen.getByText(wav.name)).toBeVisible();
    await tick(5000);
    expect(getProject).toHaveBeenCalledTimes(2);
  });

  it("accepts case-insensitive supported extensions and rejects unsupported files locally", async () => {
    render(<Home />);
    await choose(new File(["text"], "song.txt"));
    expect(screen.getByRole("alert")).toHaveTextContent(/mp3.*wav.*m4a.*flac/i);
    expect(uploadProject).not.toHaveBeenCalled();
    await choose(new File(["audio"], "SONG.FLAC"));
    expect(uploadProject).toHaveBeenCalledOnce();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows an upload state before the submission finishes", async () => {
    const submission = deferred<never>();
    vi.mocked(uploadProject).mockReturnValue(submission.promise);
    render(<Home />);
    await choose();
    expect(screen.getByRole("status")).toHaveTextContent(/uploading/i);
    expect(getProject).not.toHaveBeenCalled();
  });

  it("surfaces upload failures and allows another upload", async () => {
    vi.mocked(uploadProject).mockRejectedValueOnce(new Error("Audio file is empty."));
    render(<Home />);
    await choose();
    expect(screen.getByRole("alert")).toHaveTextContent("Audio file is empty.");
    expect(getProject).not.toHaveBeenCalled();
    await choose();
    expect(screen.getByText("Transcribing audio")).toBeVisible();
  });

  it("switches semantic difficulty radios and both selected download routes", async () => {
    vi.mocked(getProject).mockResolvedValue(done);
    render(<Home />);
    await choose();
    expect(screen.getByRole("radio", { name: /standard/i })).toBeChecked();
    fireEvent.click(screen.getByRole("radio", { name: /rich/i }));
    expect(screen.getByRole("radio", { name: /rich/i })).toBeChecked();
    expect(screen.getByRole("link", { name: /download midi/i })).toHaveAttribute("href", `/api/projects/${PROJECT_ID}/arrangements/rich/midi`);
    expect(screen.getByRole("link", { name: /download musicxml/i })).toHaveAttribute("href", `/api/projects/${PROJECT_ID}/arrangements/rich/musicxml`);
    expect(uploadProject).toHaveBeenCalledOnce();
    expect(getProject).toHaveBeenCalledOnce();
  });

  it("supports keyboard focus on the file picker and arrow-key difficulty selection", async () => {
    vi.useRealTimers();
    const user = userEvent.setup();
    vi.mocked(getProject).mockResolvedValue(done);
    render(<Home />);
    await user.tab();
    expect(screen.getByLabelText(/choose a song/i)).toHaveFocus();
    await user.upload(screen.getByLabelText(/choose a song/i), wav);
    screen.getByRole("radio", { name: /standard/i }).focus();
    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("radio", { name: /rich/i })).toBeChecked();
    expect(screen.getByRole("radio", { name: /rich/i })).toHaveFocus();
  });

  it("keeps polling uploaded metadata until processing completes", async () => {
    vi.mocked(getProject).mockResolvedValueOnce(metadata({ status: "uploaded", stage: "uploaded", progress: 0 })).mockResolvedValue(done);
    render(<Home />);
    await choose();
    expect(screen.getByText("Uploaded")).toBeVisible();
    await tick();
    expect(screen.getByRole("heading", { name: /your piano arrangement/i })).toBeVisible();
  });

  it("shows durable API failure and stops polling without result regions", async () => {
    vi.mocked(getProject).mockResolvedValue(metadata({ status: "failed", stage: "failed", error: "Transcription could not finish." }));
    render(<Home />);
    await choose();
    expect(screen.getByRole("alert")).toHaveTextContent("Transcription could not finish.");
    expect(screen.queryByRole("heading", { name: /your piano arrangement/i })).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/piano score|original audio/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /download/i })).not.toBeInTheDocument();
    await tick(3000);
    expect(getProject).toHaveBeenCalledOnce();
  });

  it("shows a polling error and keeps checking the active job until recovery", async () => {
    vi.mocked(getProject).mockRejectedValueOnce(new Error("Unable to reach the local API.")).mockResolvedValue(done);
    render(<Home />);
    await choose();
    expect(screen.getByRole("alert")).toHaveTextContent("Unable to reach the local API.");
    await tick();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /your piano arrangement/i })).toBeVisible();
  });

  it("does not overlap slow polls and ignores old results after replacement upload", async () => {
    const old = deferred<ProjectMetadata>();
    vi.mocked(getProject).mockReturnValueOnce(old.promise).mockResolvedValue(metadata({ project_id: OTHER_ID, stage: "arranging" }));
    vi.mocked(uploadProject).mockResolvedValueOnce({ project_id: PROJECT_ID, status: "processing" }).mockResolvedValueOnce({ project_id: OTHER_ID, status: "processing" });
    render(<Home />);
    await choose();
    await tick(3000);
    expect(getProject).toHaveBeenCalledTimes(1);
    await choose(new File(["new audio"], "New song.mp3"));
    expect(getProject).toHaveBeenLastCalledWith(OTHER_ID);
    await act(async () => { old.resolve(done); });
    expect(screen.getByText("Creating piano arrangements")).toBeVisible();
    expect(screen.queryByRole("link", { name: /download/i })).not.toBeInTheDocument();
    await tick();
    expect(getProject).toHaveBeenCalledTimes(3);
    expect(getProject).toHaveBeenLastCalledWith(OTHER_ID);
  });

  it("ignores an old upload response after a newer selection", async () => {
    const oldUpload = deferred<Awaited<ReturnType<typeof uploadProject>>>();
    vi.mocked(uploadProject).mockReturnValueOnce(oldUpload.promise).mockResolvedValueOnce({ project_id: OTHER_ID, status: "processing" });
    vi.mocked(getProject).mockResolvedValue({ ...done, project_id: OTHER_ID });
    render(<Home />);
    await choose();
    await choose(new File(["audio"], "New song.mp3"));
    await act(async () => { oldUpload.resolve({ project_id: PROJECT_ID, status: "processing" }); });
    expect(getProject).toHaveBeenCalledOnce();
    expect(screen.getByRole("link", { name: /download midi/i })).toHaveAttribute("href", expect.stringContaining(OTHER_ID));
    expect(screen.getByText("New song.mp3")).toBeVisible();
  });

  it("cleans up polling on unmount", async () => {
    const { unmount } = render(<Home />);
    await choose();
    unmount();
    await tick(3000);
    expect(getProject).toHaveBeenCalledOnce();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("does not begin polling when a pending upload completes after unmount", async () => {
    const pending = deferred<Awaited<ReturnType<typeof uploadProject>>>();
    vi.mocked(uploadProject).mockReturnValue(pending.promise);
    const { unmount } = render(<Home />);
    await choose();
    unmount();
    await act(async () => { pending.resolve({ project_id: PROJECT_ID, status: "processing" }); });
    await tick(3000);
    expect(getProject).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
  });
});

describe("processing status", () => {
  it.each(Object.entries(PROJECT_STAGES))("labels the %s stage", (stage, label) => {
    render(<ProcessingStatus project={metadata({ stage: stage as ProjectMetadata["stage"] })} />);
    expect(screen.getByText(label)).toBeVisible();
  });
});

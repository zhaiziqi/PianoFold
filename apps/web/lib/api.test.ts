import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ApiError,
  audioUrl,
  getProject,
  midiUrl,
  musicxmlUrl,
  uploadProject,
} from "./api";
import type { Difficulty, ProjectMetadata } from "./project";
import nextConfig from "../next.config";

const PROJECT_ID = "11111111-1111-4111-8111-111111111111";
const metadata: ProjectMetadata = {
  project_id: PROJECT_ID,
  status: "processing",
  stage: "transcribing",
  progress: 0.1,
  error: null,
  duration: null,
  model: "muscriptor-small",
  device: "mps",
  profiles: ["simple", "standard", "rich"],
};

function mockResponse(body: unknown, status = 200) {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("project requests", () => {
  it("uploads the actual file in browser-managed multipart form data", async () => {
    const submission = { project_id: PROJECT_ID, status: "processing" };
    const fetchMock = mockResponse(submission, 202);
    const file = new File(["audio"], "song.wav", { type: "audio/wav" });

    await expect(uploadProject(file)).resolves.toEqual(submission);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/projects");
    expect(options.method).toBe("POST");
    expect(options.body).toBeInstanceOf(FormData);
    expect([...options.body.keys()]).toEqual(["audio"]);
    expect(options.body.get("audio")).toBe(file);
    // The browser must provide the multipart boundary itself.
    expect(new Headers(options.headers).has("Content-Type")).toBe(false);
  });

  it("loads persisted metadata without caching processing status", async () => {
    const fetchMock = mockResponse(metadata);
    await expect(getProject(PROJECT_ID)).resolves.toEqual(metadata);
    expect(fetchMock).toHaveBeenCalledWith(`/api/projects/${PROJECT_ID}`, {
      cache: "no-store",
    });
  });

  it("preserves readable API failure details and HTTP status", async () => {
    mockResponse({ detail: "Audio file is empty" }, 400);
    await expect(uploadProject(new File([], "song.wav"))).rejects.toMatchObject({
      name: "ApiError",
      message: "Audio file is empty",
      status: 400,
    });
  });

  it("formats FastAPI validation failures without exposing object text", async () => {
    mockResponse({ detail: [{ loc: ["body", "audio"], msg: "Field required" }] }, 422);
    await expect(getProject(PROJECT_ID)).rejects.toMatchObject({
      message: "Field required",
      status: 422,
    });
  });

  it.each(["<html>Bad gateway</html>", "", "{invalid"])(
    "uses an HTTP-status fallback for non-JSON failure bodies: %s",
    async (body) => {
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(body, { status: 502 })));
      await expect(getProject(PROJECT_ID)).rejects.toMatchObject({
        name: "ApiError",
        message: "Request failed (HTTP 502).",
        status: 502,
      });
    },
  );

  it("falls back on status when JSON has no readable error detail", async () => {
    mockResponse({ detail: { internal: "not user-facing" } }, 500);
    await expect(getProject(PROJECT_ID)).rejects.toMatchObject({
      message: "Request failed (HTTP 500).",
      status: 500,
    });
  });

  it("reports unreachable API as a readable ApiError", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    await expect(getProject(PROJECT_ID)).rejects.toMatchObject({
      name: "ApiError",
      message: "Unable to reach the local API. Check that it is running.",
      status: 0,
    });
  });

  it("reports malformed successful JSON as an ApiError with the response status", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("not JSON")));
    await expect(getProject(PROJECT_ID)).rejects.toMatchObject({
      name: "ApiError",
      message: "The API returned an invalid JSON response.",
      status: 200,
    });
  });

  it("makes ApiError usable by ordinary Error handlers", () => {
    expect(new ApiError("Missing", 404)).toBeInstanceOf(Error);
  });
});

describe("fixed artifact routes", () => {
  it.each(["simple", "standard", "rich"] as const)("builds only the %s profile endpoints", (difficulty) => {
    expect(midiUrl(PROJECT_ID, difficulty)).toBe(`/api/projects/${PROJECT_ID}/arrangements/${difficulty}/midi`);
    expect(musicxmlUrl(PROJECT_ID, difficulty)).toBe(`/api/projects/${PROJECT_ID}/arrangements/${difficulty}/musicxml`);
    expect(audioUrl(PROJECT_ID)).toBe(`/api/projects/${PROJECT_ID}/audio`);
  });

  it("encodes project IDs as a single URL segment", async () => {
    const id = "a/b?query#fragment";
    expect(audioUrl(id)).toBe("/api/projects/a%2Fb%3Fquery%23fragment/audio");
    expect(midiUrl(id, "simple")).toBe("/api/projects/a%2Fb%3Fquery%23fragment/arrangements/simple/midi");
    const fetchMock = mockResponse(metadata);
    await getProject(id);
    expect(fetchMock).toHaveBeenCalledWith("/api/projects/a%2Fb%3Fquery%23fragment", { cache: "no-store" });
  });

  it.each(["", ".", ".."]) ("rejects empty or normalizing project segments: %s", (id) => {
    expect(() => audioUrl(id)).toThrow("Invalid project ID");
  });

  it.each(["expert", "../audio", "toString", "__proto__"])(
    "rejects invalid runtime difficulties: %s",
    (invalid) => {
      expect(() => midiUrl(PROJECT_ID, invalid as Difficulty)).toThrow("Invalid difficulty");
      expect(() => musicxmlUrl(PROJECT_ID, invalid as Difficulty)).toThrow("Invalid difficulty");
    },
  );
});

describe("local development proxy", () => {
  it("forwards relative API routes to the local development backend", async () => {
    vi.stubEnv("NODE_ENV", "development");
    await expect(nextConfig.rewrites?.()).resolves.toEqual([
      { source: "/api/:path*", destination: "http://127.0.0.1:8000/api/:path*" },
    ]);
  });

  it("does not rewrite production traffic to localhost", async () => {
    vi.stubEnv("NODE_ENV", "production");
    await expect(nextConfig.rewrites?.()).resolves.toEqual([]);
  });
});

"""Project HTTP contract exercised with real processing and fake transcription."""

import asyncio
from dataclasses import replace
import json
from pathlib import Path
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import pytest

from apps.api.main import app
from pianofold.projects import PianoFoldPipeline, create_project_metadata, read_metadata, write_metadata
from pianofold.symbolic.models import Note, ScoreIR


class FakeTranscriber:
    def transcribe(self, audio_path: Path) -> ScoreIR:
        assert audio_path.read_bytes() == b"audio"
        return ScoreIR((Note("bass", 43, 0, 1, "bass"), Note("melody", 67, 0, 1, "piano")))


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(app.state, "project_root", tmp_path, raising=False)
    monkeypatch.setattr(app.state, "pipeline_factory", lambda: PianoFoldPipeline(FakeTranscriber()), raising=False)
    with TestClient(app) as client:
        yield client


def test_upload_returns_project_id_then_status_and_artifacts(client, tmp_path):
    response = client.post("/api/projects", files={"audio": ("song.wav", b"audio", "audio/wav")})

    assert response.status_code == 202
    payload = response.json()
    project_id = payload["project_id"]
    assert UUID(project_id).version == 4
    assert str(UUID(project_id)) == project_id
    assert payload == {"project_id": project_id, "status": "processing"}
    metadata = client.get(f"/api/projects/{project_id}")
    assert metadata.status_code == 200
    assert metadata.json() == {
        "project_id": project_id, "status": "done", "stage": "done", "progress": 1.0,
        "error": None, "duration": 1.0, "model": "muscriptor-small", "device": "mps",
        "profiles": ["simple", "standard", "rich"],
    }
    assert client.get(f"/api/projects/{project_id}/audio").content == b"audio"
    for difficulty in ("simple", "standard", "rich"):
        for kind, suffix in (("midi", "mid"), ("musicxml", "musicxml")):
            artifact = client.get(f"/api/projects/{project_id}/arrangements/{difficulty}/{kind}")
            assert artifact.status_code == 200
            assert artifact.content == (tmp_path / project_id / f"{difficulty}.{suffix}").read_bytes()
            assert f'filename="{difficulty}.{suffix}"' in artifact.headers["content-disposition"]


@pytest.mark.parametrize("filename", ["../track.MP3", r"C:\uploads\track.WAV", "song.m4a", "song.flac"])
def test_upload_uses_only_normalized_supported_extension(client, tmp_path, filename):
    response = client.post("/api/projects", files={"audio": (filename, b"audio")})
    assert response.status_code == 202
    project_dir = tmp_path / response.json()["project_id"]
    assert (project_dir / f"input{Path(filename).suffix.lower()}").read_bytes() == b"audio"
    assert client.get(f"/api/projects/{project_dir.name}/audio").content == b"audio"


@pytest.mark.parametrize("filename,body", [("song.txt", b"audio"), ("song", b"audio"), ("song.wav.exe", b"audio"), ("song.wav", b"")])
def test_invalid_upload_is_400_and_creates_no_project(client, tmp_path, filename, body):
    response = client.post("/api/projects", files={"audio": (filename, body)})
    assert response.status_code == 400
    assert list(tmp_path.iterdir()) == []


def test_missing_upload_is_400(client, tmp_path):
    assert client.post("/api/projects").status_code == 400
    assert list(tmp_path.iterdir()) == []


def test_missing_filename_is_400(client, tmp_path):
    assert client.post("/api/projects", files={"audio": ("", b"audio")}).status_code == 400
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("project_id", ["not-a-uuid", "d5dc135057184320acb8a10120741111", "D5DC1350-5718-4320-ACB8-A10120741111", "{d5dc1350-5718-4320-acb8-a10120741111}", "d5dc1350-5718-4320-acb8-a10120741111"])
@pytest.mark.parametrize("suffix", ["", "/audio", "/arrangements/simple/midi", "/arrangements/rich/musicxml"])
def test_invalid_or_unknown_project_is_404(client, project_id, suffix):
    assert client.get(f"/api/projects/{project_id}{suffix}").status_code == 404


@pytest.fixture
def uploaded_project(tmp_path):
    project_id = str(uuid4())
    project_dir = tmp_path / project_id
    project_dir.mkdir()
    write_metadata(project_dir, create_project_metadata(project_id))
    return project_dir


def test_status_reads_persisted_metadata(client, uploaded_project):
    write_metadata(uploaded_project, replace(read_metadata(uploaded_project), status="failed", stage="failed", error="provider failed"))
    response = client.get(f"/api/projects/{uploaded_project.name}")
    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["error"] == "provider failed"


@pytest.mark.parametrize("suffix", ["audio", "arrangements/simple/midi", "arrangements/standard/musicxml", "arrangements/rich/midi"])
def test_missing_artifact_is_404(client, uploaded_project, suffix):
    write_metadata(uploaded_project, replace(read_metadata(uploaded_project), status="done", stage="done", progress=1.0))
    assert client.get(f"/api/projects/{uploaded_project.name}/{suffix}").status_code == 404


@pytest.mark.parametrize("kind,suffix", [("midi", "mid"), ("musicxml", "musicxml")])
def test_export_in_progress_does_not_serve_partial_file(client, uploaded_project, kind, suffix):
    write_metadata(uploaded_project, replace(read_metadata(uploaded_project), status="processing", stage="exporting", progress=0.75))
    (uploaded_project / f"simple.{suffix}").write_bytes(b"incomplete export")
    assert client.get(f"/api/projects/{uploaded_project.name}/arrangements/simple/{kind}").status_code == 404


@pytest.mark.parametrize("difficulty", ["easy", "SIMPLE", "metadata.json", "..", "simple%2F..%2F..%2Faudio"])
@pytest.mark.parametrize("kind", ["midi", "musicxml"])
def test_invalid_difficulty_is_404(client, uploaded_project, difficulty, kind):
    response = client.get(f"/api/projects/{uploaded_project.name}/arrangements/{difficulty}/{kind}")
    assert response.status_code == 404


@pytest.mark.parametrize("path", ["%2E%2E%2Fmetadata.json", "%2E%2E%2Fmetadata.json/audio", "%2E%2E%2Fmetadata.json/arrangements/simple/midi"])
def test_encoded_project_traversal_is_404(client, path):
    assert client.get(f"/api/projects/{path}").status_code == 404


@pytest.mark.parametrize("filename,endpoint", [("input.wav", "audio"), ("simple.mid", "arrangements/simple/midi"), ("rich.musicxml", "arrangements/rich/musicxml")])
def test_artifact_symlink_cannot_escape_project(client, uploaded_project, tmp_path, filename, endpoint):
    write_metadata(uploaded_project, replace(read_metadata(uploaded_project), status="done", stage="done", progress=1.0))
    secret = tmp_path / "private"
    secret.write_bytes(b"private")
    (uploaded_project / filename).symlink_to(secret)
    response = client.get(f"/api/projects/{uploaded_project.name}/{endpoint}")
    assert response.status_code == 404
    assert b"private" not in response.content


def test_project_symlink_cannot_escape_root(client, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    project_id = str(uuid4())
    write_metadata(outside, create_project_metadata(project_id))
    (tmp_path / project_id).symlink_to(outside, target_is_directory=True)
    assert client.get(f"/api/projects/{project_id}").status_code == 404


def test_factory_failure_is_persisted(client, tmp_path, monkeypatch):
    def broken_factory():
        raise RuntimeError("provider initialization failed")

    monkeypatch.setattr(app.state, "pipeline_factory", broken_factory)
    response = client.post("/api/projects", files={"audio": ("song.wav", b"audio")})
    assert response.status_code == 202
    metadata = client.get(f'/api/projects/{response.json()["project_id"]}').json()
    assert metadata["status"] == metadata["stage"] == "failed"
    assert metadata["error"] == "provider initialization failed"


def test_response_is_sent_before_pipeline_construction(client, tmp_path, monkeypatch):
    messages = []
    body = b'--upload\r\nContent-Disposition: form-data; name="audio"; filename="song.wav"\r\nContent-Type: audio/wav\r\n\r\naudio\r\n--upload--\r\n'

    def factory():
        assert messages[0]["status"] == 202
        assert messages[-1]["type"] == "http.response.body"
        assert not messages[-1].get("more_body", False)
        project_id = json.loads(messages[-1]["body"])["project_id"]
        assert read_metadata(tmp_path / project_id).status == "uploaded"
        return PianoFoldPipeline(FakeTranscriber())

    monkeypatch.setattr(app.state, "pipeline_factory", factory)

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        messages.append(message)

    asyncio.run(app({
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "POST",
        "scheme": "http", "path": "/api/projects", "raw_path": b"/api/projects", "query_string": b"",
        "headers": [(b"content-type", b"multipart/form-data; boundary=upload")],
        "client": ("testclient", 50000), "server": ("testserver", 80), "root_path": "",
    }, receive, send))
    assert messages[0]["status"] == 202
    project_id = json.loads(messages[-1]["body"])["project_id"]
    assert read_metadata(tmp_path / project_id).status == "done"

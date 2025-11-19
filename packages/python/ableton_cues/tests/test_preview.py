import wave
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[4]
SERVER_SRC = ROOT / "apps" / "python" / "ableton_video_sync_server"
for path in (ROOT, SERVER_SRC):
    if str(path) not in sys.path:
        sys.path.append(str(path))

try:
    from cue_runtime.preview import RecordingCuePreviewer
except ImportError:  # pragma: no cover - fallback for legacy layout
    from packages.python.cue_runtime.preview import RecordingCuePreviewer
from music_video_generation.ableton.ableton_recording import AbletonRecording


def _write_stereo_wav(path, data, samplerate=22050):
    arr = np.asarray(data, dtype=np.float32)
    if arr.ndim == 1:
        arr = np.column_stack((arr, arr))
    pcm = (np.clip(arr, -1.0, 1.0) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(samplerate)
        wf.writeframes(pcm.tobytes())
    return arr, samplerate


def _build_recording(**overrides):
    base = dict(
        project_name="Test",
        file_path="",
        takes_recorded=False,
        multiple_takes=False,
        start_recording_bar=0.0,
        end_recording_bar=1.0,
        loop_start_bar=0.0,
        loop_end_bar=1.0,
        time_start_recording=0.0,
        time_end_recording=1.0,
        bpm_at_start=120.0,
        ts_num=4,
        ts_den=4,
        start_sound_path="",
        end_sound_path="",
        start_combined_path="",
        end_combined_path="",
        recording_track_names=[],
    )
    base.update(overrides)
    return AbletonRecording(**base)


@pytest.fixture()
def stub_player(monkeypatch):
    class StubCuePlayer:
        def __init__(self):
            self.calls = []
            self.fs_out = 48000
            self.master_gain = 1.0
            self.device_index = None

        def play(self, data, samplerate=48000):
            self.calls.append((np.array(data, dtype=np.float32), samplerate))

    instance = StubCuePlayer()

    class _StubWrapper:
        _instance = None

        @classmethod
        def instance(cls):
            return cls._instance

    _StubWrapper._instance = instance

    monkeypatch.setattr("packages.python.cue_runtime.preview.CuePlayer", _StubWrapper)
    monkeypatch.setattr("packages.python.cue_runtime.preview.mk_barker_bpsk", lambda **kwargs: np.zeros(8, dtype=np.float32))
    monkeypatch.setattr("packages.python.cue_runtime.preview.unique_cue", lambda *args, **kwargs: np.zeros(8, dtype=np.float32))
    monkeypatch.setattr(
        "packages.python.cue_runtime.preview.RecordingCuePreviewer._prepare_templates",
        lambda self, cue_dir: (np.zeros((4, 2), dtype=np.float32), np.zeros((4, 2), dtype=np.float32)),
    )
    return instance


def test_preview_replays_recorded_start_seed(tmp_path, stub_player):
    cue_path = tmp_path / "start_custom.wav"
    recorded, rate = _write_stereo_wav(cue_path, np.column_stack((np.linspace(-1, 1, 32), np.linspace(1, -1, 32))), samplerate=16000)
    recording = _build_recording(start_combined_path=str(cue_path))
    previewer = RecordingCuePreviewer(default_cue_dir=tmp_path)

    previewer.play(recording, "start", project_path=str(tmp_path))

    assert stub_player.calls, "expected CuePlayer to be invoked"
    played_data, played_rate = stub_player.calls[-1]
    np.testing.assert_allclose(played_data, recorded, atol=1e-4)
    assert played_rate == rate


def test_preview_replays_recorded_stop_seed(tmp_path, stub_player):
    cue_path = tmp_path / "stop_custom.wav"
    recorded, rate = _write_stereo_wav(cue_path, np.column_stack((np.ones(16) * 0.25, np.ones(16) * -0.5)), samplerate=11025)
    recording = _build_recording(end_combined_path=str(cue_path))
    previewer = RecordingCuePreviewer(default_cue_dir=tmp_path)

    previewer.play(recording, "stop", project_path=str(tmp_path))

    assert stub_player.calls, "expected CuePlayer to be invoked"
    played_data, played_rate = stub_player.calls[-1]
    np.testing.assert_allclose(played_data, recorded, atol=1e-4)
    assert played_rate == rate

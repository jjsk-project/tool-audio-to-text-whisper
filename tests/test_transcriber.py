import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src import config, transcriber as t, utils


class FakeModel:
    def transcribe(self, *args, **kwargs):
        return {"language": "en", "segments": [
            {"start": 0.0, "end": 1.25, "text": " Hello world. "}
        ]}


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.patches = patch.multiple(config, ROOT=root, INPUT_DIR=root / "input", OUTPUT_DIR=root / "output")
        self.patches.start()
        self.addCleanup(self.patches.stop)
        utils.ensure_folders()

    def audio(self):
        path = config.INPUT_DIR / "sample.wav"
        path.write_bytes(b"test audio")
        return path

    def test_success_moves_audio_and_writes_transcripts(self):
        source = self.audio()
        with utils.processing_lock():
            destination, _ = t.transcribe_file(source, FakeModel())
        self.assertFalse(source.exists())
        self.assertEqual((destination / source.name).read_bytes(), b"test audio")
        self.assertEqual((destination / "transcript.txt").read_text(), "Hello world.\n")
        self.assertIn("00:00:00,000 --> 00:00:01,250", (destination / "subtitle.srt").read_text())
        self.assertTrue((destination / "transcript.json").exists())
        self.assertEqual(destination, config.OUTPUT_DIR / "sample")
        metadata = json.loads((destination / "metadata.json").read_text())
        self.assertEqual(metadata["status"], "completed")
        self.assertEqual(metadata["model"], "small")
        self.assertGreaterEqual(metadata["runtime_seconds"], 0)

    def test_failed_inference_preserves_audio(self):
        source = self.audio()
        model = FakeModel()
        def fail(*args, **kwargs):
            raise RuntimeError("inference failed")
        model.transcribe = fail
        with self.assertRaises(RuntimeError):
            t.transcribe_file(source, model)
        self.assertTrue(source.exists())
        self.assertEqual(list(config.OUTPUT_DIR.iterdir()), [])

    def test_write_failure_preserves_audio_and_cleans_output(self):
        source = self.audio()
        with patch.object(Path, "write_text", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                t.transcribe_file(source, FakeModel())
        self.assertTrue(source.exists())
        self.assertEqual(list(config.OUTPUT_DIR.iterdir()), [])

    def test_same_name_does_not_overwrite(self):
        first, _ = t.transcribe_file(self.audio(), FakeModel())
        source = self.audio()
        with self.assertRaises(FileExistsError):
            t.transcribe_file(source, FakeModel())
        self.assertTrue(source.exists())
        self.assertTrue((first / "sample.wav").exists())

    def test_only_direct_regular_audio_files(self):
        source = self.audio()
        (config.INPUT_DIR / "notes.txt").write_text("ignored")
        (config.INPUT_DIR / "nested").mkdir()
        (config.INPUT_DIR / "nested" / "other.wav").write_bytes(b"ignored")
        (config.INPUT_DIR / "link.wav").symlink_to(source)
        self.assertEqual(utils.input_files(), [source])
        with self.assertRaises(ValueError):
            t.transcribe_file(config.INPUT_DIR / "link.wav", FakeModel())
        outside = config.ROOT / "outside.wav"
        outside.write_bytes(b"ignored")
        with self.assertRaises(ValueError):
            t.transcribe_file(outside, FakeModel())

    def test_standard_whisper_options_and_result(self):
        model = Mock()
        model.transcribe.return_value = FakeModel().transcribe()
        source = self.audio()
        destination, rows = t.transcribe_file(source, model, "en")
        model.transcribe.assert_called_once_with(
            str(source), language="en", task="transcribe", beam_size=5,
            fp16=False, verbose=False,
        )
        self.assertEqual(rows[0]["text"], "Hello world.")
        self.assertIn('"engine": "openai-whisper"', (destination / "transcript.json").read_text())

    def test_subtitles_can_be_disabled(self):
        destination, _ = t.transcribe_file(self.audio(), FakeModel(), generate_subtitles=False)
        self.assertFalse((destination / "subtitle.srt").exists())
        metadata = json.loads((destination / "metadata.json").read_text())
        self.assertFalse(any(p.endswith(".srt") for p in metadata["artifacts_created"]))

    def test_move_failure_leaves_audio_and_cleans_output(self):
        source = self.audio()
        with patch.object(Path, "rename", side_effect=OSError("move failed")):
            with self.assertRaises(OSError):
                t.transcribe_file(source, FakeModel())
        self.assertTrue(source.exists())
        self.assertEqual(list(config.OUTPUT_DIR.iterdir()), [])

    def test_timestamp_carries_rounding(self):
        self.assertEqual(utils.timestamp(59.9999), "00:01:00,000")


if __name__ == "__main__":
    unittest.main()

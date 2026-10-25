import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src import config, tools, utils
from src.schemas import FileProcessingInput


class ToolTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        paths = patch.multiple(config, ROOT=root, INPUT_DIR=root / "input", OUTPUT_DIR=root / "output")
        paths.start()
        self.addCleanup(paths.stop)
        utils.ensure_folders()

    def test_validation_rejects_paths_types_and_unknown_arguments(self):
        for args in ({}, {"file_name": "../outside.wav"}, {"file_name": "/tmp/a.wav"},
                     {"file_name": "nested/a.wav"}, {"file_name": "..wav"},
                     {"file_name": "a.wav", "generate_subtitles": "false"},
                     {"file_name": "a.wav", "model": "fake"},
                     {"file_name": "a.wav", "unknown": True}):
            with self.subTest(args=args), patch.object(tools, "load_model") as load:
                result = json.loads(tools.file_processor_tool.run(**args))
                self.assertEqual(result["status"], "validation_error")
                load.assert_not_called()

    def test_missing_file_returns_error_without_model_download(self):
        with patch.object(tools, "load_model") as load:
            result = json.loads(tools.file_processor_tool.run(file_name="missing.wav"))
            self.assertEqual(result["error_type"], "FileNotFoundError")
            load.assert_not_called()

    def test_tool_success_and_collision(self):
        source = config.INPUT_DIR / "example.wav"
        source.write_bytes(b"audio")
        class Model:
            def transcribe(self, *args, **kwargs):
                return {"language": "en", "segments": []}
        with patch.object(tools, "load_model", return_value=Model()) as load:
            result = json.loads(tools.file_processor_tool.run(file_name=source.name))
            self.assertEqual(result["status"], "success")
            self.assertFalse(source.exists())
            self.assertIn("output/example/example.metadata.json", result["artifacts"])
            self.assertTrue(result["warnings"])
            source.write_bytes(b"second audio")
            duplicate = json.loads(tools.file_processor_tool.run(file_name=source.name))
            self.assertEqual(duplicate["error_type"], "FileExistsError")
            self.assertEqual(source.read_bytes(), b"second audio")
            load.assert_called_once_with("small")

    def test_symlink_rejected(self):
        outside = config.ROOT / "outside.wav"
        outside.write_bytes(b"audio")
        (config.INPUT_DIR / "link.wav").symlink_to(outside)
        result = json.loads(tools.file_processor_tool.run(file_name="link.wav"))
        self.assertEqual(result["status"], "error")
        self.assertTrue(outside.exists())

    def test_execution_exceptions_are_json(self):
        def fail(**kwargs):
            raise OSError("disk failure")
        tool = tools.BaseTool("fail", "test", FileProcessingInput, fail)
        result = json.loads(tool.run(file_name="a.wav"))
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error_type"], "OSError")

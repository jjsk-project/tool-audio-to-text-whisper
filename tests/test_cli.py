import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from src import cli


class CliTests(unittest.TestCase):
    def test_empty_queue_does_not_run_tool(self):
        with patch.object(cli, "input_files", return_value=[]), patch.object(cli.file_processor_tool, "run") as run:
            self.assertEqual(cli.main([]), 0)
            run.assert_not_called()

    def test_batch_continues_after_error(self):
        with patch.object(cli, "input_files", return_value=[Path("a.wav"), Path("b.wav")]), \
             patch.object(cli.file_processor_tool, "run", side_effect=['{"status":"error"}', '{"status":"success"}']) as run:
            self.assertEqual(cli.main([]), 1)
            self.assertEqual(run.call_count, 2)
            run.assert_called_with(file_name="b.wav", model="small", language=None, generate_subtitles=True)

    def test_invalid_json_returns_structured_error(self):
        stream = io.StringIO()
        with redirect_stdout(stream):
            self.assertEqual(cli.main(["--tool-call", "{broken"]), 1)
        self.assertEqual(json.loads(stream.getvalue())["status"], "error")

    def test_schema_does_not_scan_input(self):
        stream = io.StringIO()
        with patch.object(cli, "input_files") as scan, redirect_stdout(stream):
            self.assertEqual(cli.main(["--tool-schema"]), 0)
            scan.assert_not_called()
        self.assertEqual(json.loads(stream.getvalue())["function"]["name"], "process_input_file")

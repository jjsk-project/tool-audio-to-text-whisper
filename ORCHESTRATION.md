# Local transcription tool contract

## Execution context

This project is a local terminal application, not an autonomous agent or API client. `main.py` delegates to `src.cli.main`. It never sends audio to an external transcription service. Standard OpenAI Whisper `small`, CPU FP32, is the default. Model downloads need internet on first use. Python 3.9+ remains supported by this implementation.

## Registration and invocation

`src.tools.file_processor_tool` is a `BaseTool` with `FileProcessingInput` (Pydantic V2) as its argument schema. `to_openai_tool()` exports the template’s Chat Completions function-tool shape. It is a schema export only; it is not registered remotely and does not claim strict structured-output mode. An external agent must dispatch calls explicitly to `.run(**arguments)`.

```python
from src.tools import file_processor_tool

schema = file_processor_tool.to_openai_tool()
result_json = file_processor_tool.run(
    file_name="meeting.wav",
    generate_subtitles=True,
    model="small",
    language=None,
)
```

Equivalent terminal commands:

```sh
./run.sh --tool-schema
./run.sh --tool-call '{"file_name":"meeting.wav","generate_subtitles":true}'
```

The arguments object is the complete configuration for `--tool-call`; other transcription flags are ignored in this mode. `.run()` returns a JSON string. Unknown fields, invalid types, unsupported models, and unsafe filenames produce `status: validation_error` with JSON-serializable details. File, decoding, model-loading, lock, and output errors produce `status: error`, `error_type`, and `message`. Success returns `status: success`, `output_folder`, `artifacts`, `audio_file`, and `warnings`.

## Routing and lifecycle

- Paths are anchored to the project, independent of the working directory. Settings are in `src/config.py` (`INPUT_DIR`, `OUTPUT_DIR`).
- `file_name` is a basename with a supported audio extension. Absolute paths, traversal, subfolders, and symlinks are rejected. The tool never accepts arbitrary source/output directories.
- Batch mode scans only the top level of `input/` and invokes the same validated tool once per file. The last model is cached for reuse across calls in the process.
- Each call obtains the project’s nonblocking process lock. Concurrent calls fail with a JSON error and can be retried later.
- Output is exactly `output/<audio_stem>/`. Existing folders, files, or symlinks at that location are never overwritten. Same-stem recordings (including differing extensions) conflict; rename the new input or archive the old output first.
- The pipeline writes `transcript.txt`, `transcript.json`, optional `subtitle.srt`, and `metadata.json`, then moves the original audio last.
- `metadata.json` records completed status, source, output directory, generated artifact paths, moved-audio path, engine, model, detected language, UTC timestamp, segment count, source bytes, warnings, and runtime seconds. Runtime covers inference and artifact creation, excluding model loading and the final move. The artifact list excludes the metadata file itself and original audio, which have separate roles.
- Empty speech is a success with warnings and empty transcript files. Original audio is still moved.
- Handled failures and interruptions clean the newly created output and preserve input. Abrupt process termination or power loss can leave a partial folder; inspect and archive it before retrying. Success is authoritative only when the call returns success; metadata is written immediately before the final move.
- Original audio is never intentionally deleted. Historical output folders are not migrated.

## Runner behavior

No arguments means batch processing. `--file NAME` processes one recording. `--no-subtitles` disables SRT generation. Progress and batch summaries go to stderr, while per-file JSON results go to stdout. Empty batches print a human-readable message. Exit codes: 0 success/empty queue/schema, 1 processing or validation error, 2 invalid CLI syntax, 130 interruption. A failed batch item does not prevent later items from running.

## Maintenance

`src/database.py` is reserved; metadata files provide current execution records and no database service is used. Run `.venv/bin/python -m unittest discover -s tests -v`. Tests use temporary directories and mocked recognition; they do not process user recordings or download weights.

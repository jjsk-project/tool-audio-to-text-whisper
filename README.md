# Audio to Text — Standard Whisper small

A terminal-only audio transcription tool following the Pydantic V2 tool-calling template. It processes recordings directly inside `input/`, saves results in `output/<recording_stem>/`, and moves the original audio there after successful processing.

## Setup

```sh
cd /Users/jjsk/mac-projects/tool-audio-to-text-whisper
brew install ffmpeg
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Python 3.9+ is supported. Whisper weights download on first use and are cached. Once cached, transcription runs locally offline without an API key.

## Run

Copy audio into `input/`, finish copying, and run:

```sh
./run.sh
# Or:
.venv/bin/python main.py

# Process one input recording with a known language:
./run.sh --file meeting.wav --language en
# Skip subtitles:
./run.sh --no-subtitles
# Optional model override:
./run.sh --model medium
```

The default is standard OpenAI Whisper `small`, CPU FP32, with automatic language detection. Available models: `tiny`, `base`, `small`, `medium`, `large-v3`, `turbo`. Larger models need more memory/time; review transcripts for recognition errors.

Supported extensions: MP3, WAV, M4A, FLAC, OGG, OPUS, AAC, AIFF, AIF, WMA. Subfolders and symlinks are ignored by batch scanning. Each run processes the current queue and exits; it does not continuously watch the folder.

## Output

For `input/meeting.wav`:

```text
output/meeting/
├── meeting.wav       # Original audio moved after success
├── meeting.txt
├── meeting.md        # Markdown transcript
├── meeting.srt      # Omitted with --no-subtitles
├── meeting.transcript.json   # Timed segments and detected language
└── meeting.metadata.json     # Status, artifacts, model, timestamp, runtime
```

Existing output folders are never overwritten. If `output/meeting/` already exists, processing returns an error and leaves the new audio in `input/`. Archive/rename the old output or rename the new recording before retrying. Recordings with the same stem but different extensions also conflict.

Handled processing failures preserve the audio in `input/` and clean up the newly created output folder. Other batch items continue. No detected speech produces empty text/subtitle files, a Markdown title, and a warning, and moves the audio to output. Do not modify input files while processing. After a hard crash, inspect any partial output folder before retrying.

## Pydantic tool interface

```sh
# Print the tool registration schema without loading Whisper:
./run.sh --tool-schema
# Run one call with a JSON arguments object:
./run.sh --tool-call '{"file_name":"meeting.wav","generate_subtitles":true,"model":"small","language":"en"}'
```

```python
from src.tools import file_processor_tool

print(file_processor_tool.run(file_name="meeting.wav"))
```

Arguments are validated with Pydantic V2. Results are JSON strings with `success`, `error`, or `validation_error` status. JSON tool calls supply their own settings; other transcription flags are ignored in that mode. No external LLM service is called. See [ORCHESTRATION.md](ORCHESTRATION.md) for the complete machine-facing contract and schema format.

## Project structure

```text
main.py                 # Entry point
README.md
ORCHESTRATION.md
requirements.txt
.gitignore
run.sh
input/
output/
src/
  __init__.py
  config.py             # Paths and model settings
  schemas.py            # Pydantic argument validation
  tools.py              # Tool harness, registration, execution
  cli.py                # Terminal batch/tool runner
  transcriber.py        # Whisper inference and artifact writing
  utils.py              # Path validation, scanning, locking, timestamps
  database.py           # Reserved; no database required
tests/
```

## Troubleshooting and checks

- Model download fails: check the connection and retry.
- FFmpeg missing: run `brew install ffmpeg` and ensure it is on PATH.
- Wrong language: specify `--language en` or the appropriate language code.
- Another process running: wait for it to finish before retrying.
- Invalid/corrupt audio: convert to WAV or MP3.

```sh
.venv/bin/python -m unittest discover -s tests -v
```

Tests cover schema validation, path restrictions, tool errors, metadata, optional subtitles, output collisions, successful audio moves, rollback, and batch handling with fake models. They do not measure transcription accuracy.

Migration: previous generated folders are untouched. New outputs use the original recording’s stem for every filename, including `<stem>.md`, `<stem>.txt`, `<stem>.srt`, `<stem>.transcript.json`, and `<stem>.metadata.json`. Markdown includes a title and transcript paragraphs.

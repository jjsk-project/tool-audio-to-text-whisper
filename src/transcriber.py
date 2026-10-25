"""Standard Whisper inference and per-recording artifact persistence."""
import json
import shutil
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from time import perf_counter

from . import config
from .utils import ensure_folders, resolve_input_file, timestamp


@lru_cache(maxsize=1)
def load_model(name):
    if name not in config.MODELS:
        raise ValueError("Unknown model")
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("FFmpeg is required. Install it with: brew install ffmpeg")
    import whisper
    return whisper.load_model(name, device=config.DEVICE)


def transcribe_file(source, model, language=None, generate_subtitles=True, model_name=config.DEFAULT_MODEL):
    """Call under processing_lock; reject existing output and preserve input on failure."""
    started = perf_counter()
    source = Path(source)
    if source.parent.resolve() != config.INPUT_DIR.resolve():
        raise ValueError("Only files directly inside input are allowed.")
    source = resolve_input_file(source.name)
    ensure_folders()
    destination = config.OUTPUT_DIR / source.stem
    # Exclusive creation: never delete or modify an output belonging to an earlier run.
    destination.mkdir(exist_ok=False)
    try:
        result = model.transcribe(str(source), language=language, task="transcribe", beam_size=5,
                                  fp16=config.FP16, verbose=False)
        rows = [{"start": float(s["start"]), "end": float(s["end"]), "text": s["text"].strip()}
                for s in result["segments"]]
        (destination / f"{source.stem}.txt").write_text(
            "\n".join(row["text"] for row in rows) + ("\n" if rows else ""), encoding="utf-8")
        (destination / f"{source.stem}.md").write_text(
            f"# {source.stem}\n\n" + "\n\n".join(row["text"] for row in rows) + ("\n" if rows else ""),
            encoding="utf-8",
        )
        names = [f"{source.stem}.txt", f"{source.stem}.md", f"{source.stem}.transcript.json"]
        if generate_subtitles:
            (destination / f"{source.stem}.srt").write_text("\n\n".join(
                f"{i}\n{timestamp(row['start'])} --> {timestamp(row['end'])}\n{row['text']}"
                for i, row in enumerate(rows, 1)) + ("\n" if rows else ""), encoding="utf-8")
            names.append(f"{source.stem}.srt")
        (destination / f"{source.stem}.transcript.json").write_text(json.dumps({
            "source": source.name, "language": result["language"],
            "engine": "openai-whisper", "segments": rows,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        metadata = {
            "source_file": source.name, "status": "completed",
            "output_directory": str(destination.relative_to(config.ROOT)),
            "artifacts_created": [str((destination / name).relative_to(config.ROOT)) for name in names],
            "audio_file": str((destination / source.name).relative_to(config.ROOT)),
            "engine": "openai-whisper", "model": model_name, "language": result["language"],
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "runtime_seconds": round(perf_counter() - started, 3),
            "segment_count": len(rows), "source_bytes": source.stat().st_size,
            "warnings": [] if rows else ["No speech detected."],
        }
        (destination / f"{source.stem}.metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        # Move last: all artifacts must exist before the original leaves input.
        source.rename(destination / source.name)
    except BaseException:
        shutil.rmtree(destination)
        raise
    return destination, rows

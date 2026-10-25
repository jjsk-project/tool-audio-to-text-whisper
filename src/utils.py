"""Folder scanning, process locking, and timestamp helpers."""
import fcntl
from pathlib import Path
from contextlib import contextmanager

from . import config


def ensure_folders():
    config.INPUT_DIR.mkdir(exist_ok=True)
    config.OUTPUT_DIR.mkdir(exist_ok=True)


def input_files():
    ensure_folders()
    return sorted((p for p in config.INPUT_DIR.iterdir()
                   if p.is_file() and not p.is_symlink() and p.suffix.lower() in config.EXTENSIONS),
                  key=lambda p: p.name.lower())


@contextmanager
def processing_lock():
    """Prevent two processes from processing the same input simultaneously."""
    with (config.ROOT / ".process.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another transcription is running. Wait for it to finish.")
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)



def timestamp(seconds):
    ms = max(0, round(seconds * 1000))
    hours, ms = divmod(ms, 3600000)
    minutes, ms = divmod(ms, 60000)
    seconds, ms = divmod(ms, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{ms:03d}"



def validate_file_name(file_name):
    """Accept a basename only, never an absolute, relative, or nested path."""
    if not file_name or file_name in {".", ".."} or any(c in file_name for c in ("/", "\\", "\0")):
        raise ValueError("file_name must be a filename directly inside input/.")
    if Path(file_name).suffix.lower() not in config.EXTENSIONS:
        raise ValueError("Unsupported audio extension.")
    if Path(file_name).stem in {".", ".."}:
        raise ValueError("Invalid audio filename stem.")
    return file_name


def resolve_input_file(file_name):
    validate_file_name(file_name)
    source = config.INPUT_DIR / file_name
    if source.is_symlink() or source.resolve().parent != config.INPUT_DIR.resolve():
        raise ValueError("Only regular audio files directly inside input are allowed.")
    if not source.is_file():
        raise FileNotFoundError(f"Input file not found: {source}")
    return source

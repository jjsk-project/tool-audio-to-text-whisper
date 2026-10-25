"""Project paths and transcription settings."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INPUT_DIR = ROOT / "input"
OUTPUT_DIR = ROOT / "output"
EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".opus", ".aac", ".aiff", ".aif", ".wma"}
MODELS = ("tiny", "base", "small", "medium", "large-v3", "turbo")

DEFAULT_MODEL = "small"
DEVICE = "cpu"
FP16 = False

"""Pydantic tool harness and local tool registration; no API calls are made."""
import json
from typing import Callable, Type

from pydantic import BaseModel, ValidationError

from . import config
from .schemas import FileProcessingInput
from .transcriber import load_model, transcribe_file
from .utils import ensure_folders, processing_lock, resolve_input_file


def error_payload(exc):
    return json.dumps({"status": "error", "error_type": type(exc).__name__, "message": str(exc)})


class BaseTool:
    def __init__(self, name: str, description: str, args_schema: Type[BaseModel], func: Callable):
        self.name = name
        self.description = description
        self.args_schema = args_schema
        self.func = func

    def to_openai_tool(self):
        """Export the template's Chat Completions function-tool schema."""
        return {"type": "function", "function": {
            "name": self.name, "description": self.description,
            "parameters": self.args_schema.model_json_schema(),
        }}

    def run(self, **kwargs):
        try:
            validated = self.args_schema.model_validate(kwargs)
            return self.func(**validated.model_dump())
        except ValidationError as exc:
            return json.dumps({"status": "validation_error", "message": "Invalid arguments provided to tool.",
                               "details": json.loads(exc.json(include_url=False, include_context=False))})
        except Exception as exc:
            return error_payload(exc)


def process_input_file(file_name, generate_subtitles=True, model=config.DEFAULT_MODEL, language=None):
    """Transcribe one input recording into output/<stem>/ and move its original audio on success."""
    try:
        args = FileProcessingInput(file_name=file_name, generate_subtitles=generate_subtitles,
                                   model=model, language=language)
        with processing_lock():
            ensure_folders()
            source = resolve_input_file(args.file_name)
            destination = config.OUTPUT_DIR / source.stem
            if destination.exists() or destination.is_symlink():
                raise FileExistsError(f"Output folder already exists: {destination}. Archive or rename it before retrying.")
            speech_model = load_model(args.model)
            folder, rows = transcribe_file(source, speech_model, args.language,
                                          args.generate_subtitles, args.model)
            artifacts = [str(p.relative_to(config.ROOT)) for p in sorted(folder.iterdir())
                         if p.name != source.name]
            return json.dumps({"status": "success", "message": f"Processed {source.name}.",
                               "output_folder": str(folder), "artifacts": artifacts,
                               "audio_file": str(folder / source.name),
                               "warnings": [] if rows else ["No speech detected; transcript is empty."]})
    except ValidationError as exc:
        return json.dumps({"status": "validation_error", "message": "Invalid arguments provided to tool.",
                           "details": json.loads(exc.json(include_url=False, include_context=False))})
    except Exception as exc:
        return error_payload(exc)


file_processor_tool = BaseTool("process_input_file", process_input_file.__doc__,
                               FileProcessingInput, process_input_file)

"""Terminal batch runner and JSON tool-call entry point."""
import argparse
import json
import sys

from .config import DEFAULT_MODEL, MODELS
from .tools import error_payload, file_processor_tool
from .utils import input_files


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=MODELS, default=DEFAULT_MODEL, help="Speech model (default: %(default)s)")
    parser.add_argument("--language", default=None, help="Language code (default: auto-detect)")
    parser.add_argument("--no-subtitles", action="store_true")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--file", help="Process one filename inside input/")
    mode.add_argument("--tool-schema", action="store_true", help="Print the function-tool JSON schema and exit")
    mode.add_argument("--tool-call", help="Run a JSON arguments object; other transcription flags are ignored")
    args = parser.parse_args(argv)
    try:
        if args.tool_schema:
            print(json.dumps(file_processor_tool.to_openai_tool(), indent=2))
            return 0
        if args.tool_call is not None:
            payload = json.loads(args.tool_call)
            if not isinstance(payload, dict):
                raise ValueError("Tool-call arguments must be a JSON object.")
            result = file_processor_tool.run(**payload)
            print(result)
            return 0 if json.loads(result)["status"] == "success" else 1
        names = [args.file] if args.file is not None else [p.name for p in input_files()]
        if not names:
            print("No audio files in input. Add recordings and run again.")
            return 0
        failed = 0
        for index, name in enumerate(names, 1):
            print(f"[{index}/{len(names)}] Processing {name}…", file=sys.stderr, flush=True)
            result = file_processor_tool.run(file_name=name, model=args.model,
                                             language=args.language, generate_subtitles=not args.no_subtitles)
            print(result, flush=True)
            failed += json.loads(result)["status"] != "success"
        print(f"Finished: {len(names) - failed} succeeded, {failed} failed.", file=sys.stderr)
        return 1 if failed else 0
    except KeyboardInterrupt:
        print(error_payload(RuntimeError("Processing interrupted.")), flush=True)
        return 130
    except Exception as exc:
        print(error_payload(exc), flush=True)
        return 1

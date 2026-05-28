import importlib.util
import sys
from pathlib import Path


def _load(alias, filename):
    path = Path(__file__).parent / filename
    if not path.exists():
        raise ImportError(f"Cannot load '{alias}': '{path}' not found")
    spec = importlib.util.spec_from_file_location(alias, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[alias] = module
    spec.loader.exec_module(module)


# Scripts use hyphenated filenames which Python cannot import directly.
# We register them under underscore aliases so tests can use normal imports.
_load("get_smoothcomp_timestamps", "get-smoothcomp-timestamps.py")
_load("make_clips", "make-clips.py")

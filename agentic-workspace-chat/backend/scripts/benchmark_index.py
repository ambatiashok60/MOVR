"""Measure cold and warm incremental repository-index latency."""
import argparse
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

from app.repository_index import build_index


def measured(root: Path, cache: Path) -> tuple[dict, int]:
    started = perf_counter()
    result = build_index(root, cache_dir=cache)
    return result, round((perf_counter() - started) * 1000)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    args = parser.parse_args()
    root = args.workspace.expanduser().resolve()
    with TemporaryDirectory() as directory:
        cold, cold_ms = measured(root, Path(directory))
        warm, warm_ms = measured(root, Path(directory))
    print(f"files={cold['files']} symbols={cold['indexed']} cold_ms={cold_ms} warm_ms={warm_ms} reused={warm['reused']}")


if __name__ == "__main__":
    main()

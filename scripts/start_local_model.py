"""Start the downloaded generator on localhost; Ctrl+C releases its memory."""

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    config = json.loads((ROOT / "config/local-generator.json").read_text())
    binaries = list((ROOT / ".cache/llama").rglob("llama-server"))
    model = ROOT / "models/generator" / config["model_file"]
    if len(binaries) != 1 or not model.is_file():
        raise SystemExit("Run .venv/bin/python -m scripts.setup_local_generator first.")
    command = [str(binaries[0]), "--model", str(model), "--alias", "local-rag",
               "--host", "127.0.0.1", "--port", str(config["port"]),
               "--ctx-size", str(config["context_size"]), "--parallel", "1",
               "--threads", str(config["threads"]), "--n-gpu-layers", "0",
               "--jinja", "--reasoning-budget", "0", "--no-context-shift"]
    os.execv(command[0], command)


if __name__ == "__main__":
    main()

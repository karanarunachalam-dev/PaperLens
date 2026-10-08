"""Download and verify the pinned Linux x86-64 CPU runtime and model."""

import hashlib
import json
from pathlib import Path
import platform
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def verify(path, expected):
    with path.open("rb") as file:
        actual = hashlib.file_digest(file, "sha256").hexdigest()
    if actual != expected:
        raise ValueError(f"Checksum mismatch: {path}. Remove the incomplete file and rerun setup.")


def download(url, path, expected):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        temporary = path.with_suffix(path.suffix + ".part")
        subprocess.run(["curl", "-fL", "--retry", "2", "-C", "-", url,
                        "-o", str(temporary)], check=True)
        verify(temporary, expected)
        temporary.replace(path)
    verify(path, expected)


def main():
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise SystemExit("This pinned runtime is for Linux x86-64 only.")
    config = json.loads((ROOT / "config/local-generator.json").read_text())
    archive = ROOT / ".cache/llama/runtime.tar.gz"
    download(config["runtime_url"], archive, config["runtime_sha256"])
    with tarfile.open(archive) as bundle:
        bundle.extractall(ROOT / ".cache/llama", filter="data")
    url = (f"https://huggingface.co/{config['model_repository']}/resolve/"
           f"{config['model_revision']}/{config['model_file']}")
    download(url, ROOT / "models/generator" / config["model_file"], config["model_sha256"])
    print("Runtime and model verified. Start with: .venv/bin/python -m scripts.start_local_model")


if __name__ == "__main__":
    main()

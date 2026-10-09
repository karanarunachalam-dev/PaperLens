# Setup and daily use

Run commands from the repository root: the folder containing `requirements.txt`, `api/`, and `scripts/`. This guide targets a clean installation. If the project already works on your machine, use **Daily startup** below; no new downloads or reindexing are needed.

## Requirements

- Linux x86-64 and Python 3.12. The pinned llama.cpp setup is specific to that platform.
- `curl` for downloading the generator runtime/model and reference papers.
- Internet access for initial dependency, model, and paper downloads. Inference uses local files and localhost afterward.
- Disk space for the Python environment, embedding model, PDFs/index, and approximately 1.28 GB generator file. Runtime memory is additional; no minimum-RAM benchmark was established.

No GPU, API key, or paid model service is required. Commands below do not install system packages or assume a particular Linux package manager.

## 1. Create the Python environment

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip check
```

`requirements.txt` pins direct dependencies, including CPU PyTorch. `requirements-lock.txt` records the development environment's transitive dependencies; it can be used instead on a matching Linux/Python 3.12 setup. Neither file includes model weights.

## 2. Download the pinned embedding model once

The app's normal loader deliberately uses cached files. Populate its cache before starting it:

```bash
.venv/bin/python - <<'PY'
from sentence_transformers import SentenceTransformer
from scripts.semantic_search_demo import MODEL_ID, MODEL_REVISION

SentenceTransformer(
    MODEL_ID,
    revision=MODEL_REVISION,
    device="cpu",
    cache_folder=".cache/models",
)
print("Embedding model is cached.")
PY
```

This imports model constants from the teaching script; it does not import synthetic documents into the application.

## 3. Download and verify the local generator

```bash
.venv/bin/python -m scripts.setup_local_generator
```

The script downloads the pinned Linux runtime and Qwen3.5-2B quantization and verifies SHA-256 checksums against `config/local-generator.json`. Existing complete files are verified and reused. Resolve download/checksum failures before starting the model; do not remove unrelated model files or indexes.

## 4. Prepare the reference papers and app index

For a fresh collection:

```bash
HF_HUB_OFFLINE=1 .venv/bin/python -m scripts.evaluate_research \
  --prepare --retrieval-only \
  --db data/index/research-eval \
  --output data/processed/research-eval/setup-retrieval.json
```

This downloads and verifies three pinned research PDFs, extracts 45 physical pages, and indexes their 158 chunks with the pinned configuration. It records a retrieval-only evaluation; no generator needs to be running yet. `HF_HUB_OFFLINE=1` keeps BGE on its cache; initial PDF downloads still need the internet.

The output must be a new filename. Preserve existing reports and choose another output name for a rerun. If this app index already contains uploaded papers, skip preparation: the evaluator requires exactly its three reference documents. Use a separate evaluation index for later experiments, as shown below.

## 5. Start the two services

Terminal 1:

```bash
.venv/bin/python -m scripts.start_local_model
```

Wait until the model reports that it has loaded and is listening on `127.0.0.1:8081`.

Terminal 2:

```bash
HF_HUB_OFFLINE=1 .venv/bin/python -m api.app
```

Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/). The three reference papers should appear. Ask **How many layers are in the Transformer encoder?** and inspect the quote and page link.

`GET /health` checks Flask only, not the generator. The app uses `data/index/research-eval`; the teaching CLI defaults to a different index (`data/index/qdrant`). Specify the app index for CLI answers:

```bash
HF_HUB_OFFLINE=1 .venv/bin/python -m scripts.answer_question \
  "How many layers are in the Transformer encoder?" \
  --db data/index/research-eval --json
```

Do not run an index/search CLI against the same embedded Qdrant store while the app is processing a request. Its lock coordinates app requests, not separate processes.

## Daily startup

Repeat only the two service commands in step 5. Models and indexed documents persist locally. Stop each service with Ctrl+C in its own terminal. After Python changes, restart the app and refresh the browser; automatic reload is disabled. The model server can stay running if its configuration has not changed.

## Upload and delete

Choose a text-based PDF and select **Add PDF**. Upload one file at a time; the limit is 10 MiB and 100 pages. Identical file bytes reuse the indexed document. A successful upload is selected automatically for questions. Under **Search in**, tick additional papers to search several together, or choose **All research papers**.

Use **Delete** beside a web upload to remove its app-managed copy and indexed passages. Confirm the filename. The original file selected outside app storage is unaffected. Imported reference papers are protected. Removing a file manually does not remove its indexed text.

## Verify the software

After caching BGE:

```bash
HF_HUB_OFFLINE=1 .venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m pip check
```

The recorded suite contains 87 tests. It uses temporary indexes, fixtures, cached tokenization, and controlled model responses. It does not need the generator or establish LLM accuracy. The [evaluation summary](../reports/final-evaluation.md) describes the separate live checks.

To evaluate retrieval on a collection isolated from uploads:

```bash
HF_HUB_OFFLINE=1 .venv/bin/python -m scripts.evaluate_research \
  --prepare --retrieval-only \
  --db data/index/evaluation-only \
  --output data/processed/research-eval/evaluation-only-retrieval.json
```

The evaluator defaults to `--neighbors 0` for the historical retrieval baseline. Add `--neighbors 2` to prepare recovery candidates. Omit `--retrieval-only` while the generator is running to evaluate current generation; use a fresh output filename for each run. The current recovery policy differs from historical runs, so keep results separate. See [evaluation details](research-evaluation.md).

## Troubleshooting

| Symptom | What to check |
|---|---|
| Cached model/tokenizer missing | Complete step 2 from the repository root using the pinned revision. |
| Research index missing | On a fresh installation, complete step 4 before the demo. |
| Index busy/already open | Let the request finish; close a separate CLI using that index. |
| Model unavailable | Check terminal 1 and wait for loading on port 8081. |
| Port already in use | Check whether your existing app/model is already running; avoid starting a duplicate. |
| Not enough evidence | This is an abstention, not proof that the entire PDF lacks an answer. Inspect the supplied passages. |
| Evidence quote did not match | Quote provenance failed after recovery; the invalid answer is withheld. |
| PDF opens on another page | Page-fragment support depends on the viewer; use the physical page on the source card. |
| Original PDF missing/changed | Restore the exact original, or delete and re-upload an app-managed upload. Indexed text can outlive a deleted file. |

This sequence was checked against the code and cached environment. A fresh network installation on a second machine has not been verified.

# First backend component: ask the research papers

The command-line program already retrieves passages and generates an answer. The
API lets another program, including our webpage, use those same functions over
HTTP. The API searches indexed papers and now also accepts PDF uploads.

## Start it

Keep the local model running in its existing terminal on port 8081. In a second
terminal, from the project folder:

```bash
.venv/bin/python -m api.app
```

The API loads the embedding model once, then listens at http://127.0.0.1:8000.
It uses `data/index/research-eval`, **not the demo PDFs**. This is Flask's local
development server; deployment is a later component. No API keys are required.

Open http://127.0.0.1:8000/ for the question page, or
http://127.0.0.1:8000/documents to see the indexed paper names as JSON.
`GET /health` checks only that this API is running; it does not check the separate
answer model. Stop the API with Ctrl+C in its own terminal.

## Ask a question

In another terminal:

```bash
curl --max-time 240 http://127.0.0.1:8000/questions \
  -H 'Content-Type: application/json' \
  -d '{"question":"How many layers are in the Transformer encoder and decoder?"}'
```

`POST /questions` accepts a JSON object with `question`, optional `top_k` (default
3, integer 1–10), and optional `document_id` from the documents response. Unknown
fields are rejected. An unknown document ID retrieves nothing and produces an
insufficient-evidence response. The embedding tokenizer also limits question
length, and the request body is capped at 16 KiB.

The response contains `status`, `answer`, `citations`, `retrieved` passages,
`generation_seconds`, and `total_seconds`. Original PDF filenames and physical
page numbers remain attached to each citation. A missing-evidence answer is a
successful HTTP 200 response with `status: "insufficient_evidence"`; a failed
model call is an error, not evidence that the documents lack the answer.

## Four pieces of code to understand

For uploads, `POST /documents` accepts one multipart `file` and returns HTTP 201
with `status: "indexed"`, document metadata, and elapsed time. Identical bytes
already in the index return HTTP 200 with `status: "already_indexed"`. See
`docs/pdf-upload.md` for limits, validation, storage, and a request example.

`GET /documents` also returns `can_delete`. `DELETE /documents/<document_id>`
removes a web-uploaded document's stored copy and Qdrant passages. Imported papers
are protected by the server. The webpage asks for confirmation before calling
this endpoint; see `docs/pdf-upload.md` for deletion errors and retry behavior.

Read `api/app.py`:

1. `create_app()` creates the Flask app and loads BGE once. It accepts a different
   index and a supplied model for tests, without exposing file paths in requests.
2. `@app.post("/questions")` connects an HTTP address to a Python function.
   `request.get_json()` reads the submitted question and options.
3. `retrieve(...)` and `generate_answer(...)` are our existing pipeline. The API
   does not train either model or change retrieval thresholds.
4. `jsonify(...)` sends structured results back to the caller. The webpage
   displays these fields instead of showing raw JSON.

The other code validates inputs, closes the index, and handles failures. A lock
permits one operation at a time because this setup uses embedded Qdrant and one
CPU generator slot. A second request gets a clear busy response. Do not run
separate indexing/search commands concurrently with an API request; this lock
coordinates API threads, not unrelated processes. Browsers must call the API
from its own origin; the UI is served by this app.

## Errors and limitations

- HTTP 400: invalid fields/options; 413: oversized request; 415: incorrect content type.
- HTTP 422: invalid, unreadable, encrypted, or over-page-limit PDF.
- HTTP 502: generated output failed our checks or exceeded the context budget.
- HTTP 503: busy, unavailable index, or unavailable/timed-out answer model.
- Errors use `{"error":{"code":"...","message":"..."}}`.

The API preserves the pipeline's limitations: quotations can be real while the
answer interprets them incorrectly, and comparisons can be incomplete. Adding
an HTTP interface does not improve model accuracy. A request blocks until the
model finishes; streaming, authentication, and public hosting are not
part of this component.

Run checks with `.venv/bin/python -m unittest discover -s tests`. API tests use
Flask's test client and substitute the expensive model functions; live checks
must be reported separately.

For a fresh environment install `requirements.txt`. On this development machine,
the package index was unreachable, so Flask 3.1.3 and three pure-Python dependencies
were installed from locally repacked copies of existing installed distributions.
Their files were checked against those distributions' RECORD hashes. The ignored
`.cache/offline-wheels` directory holds those copies; requirements remain pinned
to normal package versions for installation elsewhere.

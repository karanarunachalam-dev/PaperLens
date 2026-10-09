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
3, integer 1–10), and optional `document_ids`, a nonempty array of document ID
strings from the documents response. For example:

```json
{"question":"What training settings do these papers report?","document_ids":["first-document-id","second-document-id"]}
```

Replace the example IDs with real IDs from `GET /documents`. Retrieval filters
to their union before ranking. The top-k budget is shared across the selected
papers; it does not guarantee a passage or citation from every paper.

Omit the selection field to search all papers. The original `document_id` string
is still supported for a single paper, but sending both fields is rejected.
Empty arrays and invalid entries are rejected; duplicate IDs are deduplicated.
Unknown IDs match nothing, without broadening the selection. If none match, the
response reports insufficient evidence. Unknown fields are rejected. The embedding
tokenizer also limits question length, and the request body is capped at 16 KiB.

`top_k` counts the initial ranked matches. Generation first uses those matches
in their original ranking with the existing prompt. A valid answer returns
immediately. The pipeline also prepares up to two immediate neighbors from the
same documents for a possible recovery attempt. Neighbors retain their original
page and text and carry `retrieval_role: "neighbor"`, `neighbor_of` chunk IDs,
and their actual cosine similarity. Main matches retain `retrieval_rank`.
The returned `retrieved` list contains exactly the passages sent in the last
model attempt. No reindexing is required.

The response contains `status`, `answer`, `citations`, `retrieved` passages,
`generation_seconds`, and `total_seconds`. Original PDF filenames and physical
page numbers remain attached to each citation. A missing-evidence answer is a
successful HTTP 200 response with `status: "insufficient_evidence"`; a failed
model call is an error, not evidence that the documents lack the answer.

If the first attempt abstains or its quote does not occur in the cited passage,
the pipeline makes one recovery attempt with the expanded context in reading
order and evidence-first instructions. Quote errors also receive corrective
instructions. The response must pass all original checks. Other validation
errors do not trigger recovery. A failed recovery cannot replace an initial safe
abstention with an invalid answer; the abstention is retained and diagnostics
record the failure. If the original result was a quote error, a repeated failure
still produces an API error. No third attempt is made.

The complete recovery prompt must fit the generator's context budget. Optional
neighbors are removed first when needed. If it still cannot fit, retain the
original abstention or quote error. `generation_seconds` includes both calls;
requests needing recovery can take several minutes.

## Four pieces of code to understand

For uploads, `POST /documents` accepts one multipart `file` and returns HTTP 201
with `status: "indexed"`, document metadata, and elapsed time. Identical bytes
already in the index return HTTP 200 with `status: "already_indexed"`. See
`docs/pdf-upload.md` for limits, validation, storage, and a request example.

`GET /documents` also returns `can_delete`. `DELETE /documents/<document_id>`
removes a web-uploaded document's stored copy and Qdrant passages. Imported papers
are protected by the server. The webpage asks for confirmation before calling
this endpoint; see `docs/pdf-upload.md` for deletion errors and retry behavior.

`GET /documents/<document_id>/pdf` serves an indexed document's verified original
as an inline PDF. The frontend appends `#page=<physical-page>` for browser viewing.
This supports web uploads and the three pinned research PDFs. The endpoint checks
the indexed identity and local storage roots, rejects symbolic links and changed
file contents, and supports byte-range requests from PDF viewers. Responses use
`Cache-Control: no-store`. Missing documents/files return 404, invalid IDs 400,
changed/unsafe stored files 409, and busy/unavailable storage 503. Browser requests
receive an HTML error page; API requests receive the usual JSON error format.

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

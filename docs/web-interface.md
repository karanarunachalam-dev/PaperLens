# A page for the existing question API

Open http://127.0.0.1:8000/ after starting `.venv/bin/python -m api.app` from the
project folder. Keep the local model server running on port 8081. If the API was
already running when this component was added, stop **only the API** with Ctrl+C
and start it again. Debug reload is disabled, so the new Python route needs a
restart. No frontend build, downloads, or extra server are needed.

The page lists the indexed research papers, lets you select one or all, and sends
your question to the same `/questions` address used by curl. The optional document
selection sends its stored ID, so filtering still happens in retrieval.

## Follow one question through three files

1. `api/templates/index.html` describes the page: paper selector, question form,
   answer area, citations, and an expandable list of retrieved passages.
2. `api/static/app.css` sets the spacing, colors, type, and narrow-screen layout.
3. `api/static/app.js` handles interaction. `loadDocuments()` fetches `/documents`.
   The form's submit handler sends a JSON question to `/questions` using `fetch()`.
   `renderAnswer()` puts the returned answer and evidence into the page.

The only Python behavior added is `GET /`, which calls Flask's `render_template`.
Flask also serves the two static files. Retrieval and generation are unchanged.
Plain JavaScript keeps this component small; a framework is not required for one
form and its results.

## What the page does while you wait

The Ask button, question, and paper selector are disabled during a request, and an
elapsed timer is displayed. The timer measures waiting time; it does not estimate
completion or claim to know which processing stage the server is in.

On success, the page shows the question, answer, time, source filenames, physical
page numbers, and evidence quotes. Retrieved passages are available separately,
including those the model did not cite. Similarity scores are not confidence in
the answer.

Missing evidence gets its own heading and no fabricated citations. A failed API
call shows an error and preserves the question for retry. Old answers are hidden
when a new request begins. Empty/unavailable collections disable asking and offer
a refresh action. The browser stops waiting after four minutes; a timed-out call
may still be running on the server, so the message advises waiting before retry.

Answer text, filenames, quotes, and passages are inserted using `textContent`,
not interpreted as HTML. This also means Markdown in model output stays plain
text. Source cards currently show names and page numbers, not PDF download links.
Conversation history and streaming are not implemented here.

## Upload your own PDF

Choose a file in **Add your own PDF**, then click **Add PDF**. The browser sends a
`FormData` request to `POST /documents`; it sets the multipart boundary itself.
The upload and question controls are disabled until indexing finishes. An elapsed
timer shows that the request is still pending without inventing a completion
percentage. On success the page refreshes its paper list and selects the returned
document ID. A renamed duplicate selects the original document without adding a
copy. Blank-page warnings are displayed after a successful partial-text import.

The browser checks extension, empty files, and the 10 MiB size limit for quick
feedback. The server independently validates the upload and enforces the 100-page
limit. Upload waiting times out after ten minutes, and the request may still run
on the server; refresh the paper list after it finishes. See `docs/pdf-upload.md`
for the backend implementation and current format limitations.

## Checks

Flask's test client checks that the actual home template and static files serve
successfully. Existing API/pipeline tests run with
`.venv/bin/python -m unittest discover -s tests`.

Browser checks use controlled API responses to cover successful answers, document
selection, disabled controls while waiting, missing evidence, service/network
errors, literal rendering of HTML-like text, empty collections, retry, and mobile
layout. These checks verify interface behavior, not live model accuracy. The
model's previously observed answer/citation limitations still apply.

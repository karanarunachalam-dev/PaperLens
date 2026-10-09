# A page for the existing question API

Open http://127.0.0.1:8000/ after starting `.venv/bin/python -m api.app` from the
project folder. Keep the local model server running on port 8081. If the API was
already running when this component was added, stop **only the API** with Ctrl+C
and start it again. Debug reload is disabled, so the new Python route needs a
restart. No frontend build, downloads, or extra server are needed.

The page lists the indexed research papers. Under **Search in**, tick one or
several papers, or use **All research papers**. It sends your question to the
same `/questions` address used by curl, with selected IDs in `document_ids`.
All-papers mode omits the filter. Filtering happens before retrieval ranking;
the three initial matches are shared across your selected papers.

Refreshing preserves a custom selection. All-papers mode includes newly listed
papers automatically. With no papers checked, Ask is disabled. Deleting the last
selected paper leaves the selection empty until you choose another. A successful
upload selects just that uploaded paper; tick others to include them too.

The passage inspector labels additional neighboring passages **Nearby context**.
These help when an explanation continues into another chunk or onto the next
page. They retain their own page numbers; quotes and PDF links still refer to a
single source page. A successful first attempt uses the three ranked matches. If that attempt
cannot produce a valid answer, recovery can include up to two extra passages
and follows reading order within each document. The inspector shows the last
attempt’s actual context.

## Follow one question through three files

1. `api/templates/index.html` describes the page: paper selector, question form,
   answer area, citations, and an expandable list of retrieved passages.
2. `api/static/app.css` sets the spacing, colors, type, and narrow-screen layout.
3. `api/static/app.js` handles interaction. `loadDocuments()` fetches `/documents`.
   The form's submit handler sends a JSON question to `/questions` using `fetch()`.
   `renderAnswer()` puts the returned answer and evidence into the page.

`GET /` calls Flask's `render_template`, and Flask serves the two static files.
The question API accepts multiple document IDs and filters retrieval to their
union. The generation and quote-validation behavior is unchanged.
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
text. Answer citation markers and source-card links open the original PDF at its
cited physical page in a new tab. The evidence quote stays visible in the assistant.
Conversation history and streaming are not implemented here.

## Open a citation in its PDF

Click `[S1]` in an answer or **Open PDF at page …** in the corresponding source
card. `pdfLink()` builds a local link using the stored document ID and a positive
physical page number: `/documents/<id>/pdf#page=3`, for example. Only recognized
citation markers become links; all remaining model text still uses text nodes.
The link opens a new tab with the browser's PDF viewer. Page-jump support depends
on that viewer; the source card always states the physical page explicitly.

The API resolves uploaded originals from their content-specific storage folder
and the three reference PDFs from their pinned manifest. It checks that the file's
SHA-256 still matches the indexed document before serving a PDF snapshot inline.
It accepts no client-supplied filesystem path. Missing/deleted or modified PDFs
open a readable error page instead of showing an unrelated or changed file.

This component opens the correct page; it does not highlight the exact words.
Locating the quoted text and its page coordinates is the next separate step.

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

## Remove a web-uploaded paper

Uploaded documents have a **Delete** button in the paper list. A browser dialog
shows the filename and asks for confirmation. `deleteDocument()` sends a DELETE
request only after confirmation, disables conflicting controls, and refreshes
the list on success. It clears the old answer and evidence because the collection
has changed. A failed delete leaves the list visible and displays an error for
retry. Imported research papers are protected by both the API and the interface.

## Checks

Flask's test client checks that the actual home template and static files serve
successfully. Existing API/pipeline tests run with
`.venv/bin/python -m unittest discover -s tests`.

Browser checks use controlled API responses to cover successful answers, document
selection, disabled controls while waiting, missing evidence, service/network
errors, literal rendering of HTML-like text, empty collections, retry, and mobile
layout. These checks verify interface behavior, not live model accuracy. The
model's previously observed answer/citation limitations still apply.

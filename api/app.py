"""Serve the existing RAG pipeline through a small local Flask API."""

from pathlib import Path
from threading import Lock
import time

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

from api.uploads import MAX_UPLOAD_BYTES, UploadError, index_upload
from scripts.answer_question import retrieve
from scripts.grounded_answer import generate_answer
from scripts.local_index import list_documents, open_index
from scripts.search_documents import load_model

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data/index/research-eval"


def create_app(db=DEFAULT_DB, model=None, upload_dir=ROOT / "data/raw/uploads"):
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024
    db = Path(db)
    # One embedding model for the lifetime of this server.
    model = load_model() if model is None else model
    # Embedded Qdrant and our local generator serve one operation at a time.
    work_lock = Lock()

    def error(code, message, status):
        return jsonify(error={"code": code, "message": message}), status

    @app.errorhandler(HTTPException)
    def http_error(exc):
        if exc.code == 413 and request.endpoint == "upload_document":
            return error("upload_too_large", "Upload one PDF up to 10 MB.", 413)
        return error(exc.name.lower().replace(" ", "_"), exc.description, exc.code)

    @app.errorhandler(Exception)
    def unexpected_error(exc):
        app.logger.exception("Unexpected API failure")
        return error("internal_error", "The request failed unexpectedly. Check the API terminal.", 500)

    @app.before_request
    def restrict_browser_origin():
        if request.endpoint == "upload_document":
            # Allow multipart overhead; the file itself is separately limited to 10 MiB.
            request.max_content_length = MAX_UPLOAD_BYTES + 64 * 1024
        # The UI is served by this app. Do not accept cross-origin
        # browser requests that could trigger expensive local generation.
        origin = request.headers.get("Origin")
        if origin and origin != request.host_url.rstrip("/"):
            return error("origin_not_allowed", "Use the API from its own address.", 403)

    @app.get("/")
    def home():
        return render_template("index.html")

    @app.get("/health")
    def health():
        # API liveness only: this does not probe the separate generator server.
        return jsonify(status="ok", component="api")

    def acquire_index(allow_create=False):
        if not allow_create and not db.is_dir():
            return error("index_unavailable", "The research index is missing. Index the papers first.", 503)
        if not work_lock.acquire(blocking=False):
            return error("busy", "Another request is running. Please try again shortly.", 503)
        return None

    @app.get("/documents")
    def documents():
        problem = acquire_index()
        if problem is not None:
            return problem
        try:
            client = open_index(db)
            try:
                return jsonify(documents=list_documents(client))
            finally:
                client.close()
        except (OSError, RuntimeError) as exc:
            app.logger.warning("Index unavailable: %s", exc)
            return error("index_unavailable", "Cannot open the index. Close other indexing or search processes.", 503)
        finally:
            work_lock.release()

    @app.post("/documents")
    def upload_document():
        if request.mimetype != "multipart/form-data":
            return error("invalid_upload", "Send one PDF in the multipart file field.", 415)
        problem = acquire_index(allow_create=True)
        if problem is not None:
            return problem
        started = time.perf_counter()
        try:
            if set(request.files) != {"file"} or len(request.files.getlist("file")) != 1 or request.form:
                return error("invalid_upload", "Choose exactly one PDF to upload.", 400)
            client = open_index(db)
            try:
                result = index_upload(request.files["file"], client, model, upload_dir)
            finally:
                client.close()
            result["total_seconds"] = round(time.perf_counter() - started, 3)
            return jsonify(result), 201 if result["status"] == "indexed" else 200
        except UploadError as exc:
            return error("invalid_upload", str(exc), exc.status)
        except ValueError as exc:
            return error("invalid_pdf", str(exc), 422)
        except (OSError, RuntimeError) as exc:
            app.logger.warning("Upload failed: %s", exc)
            return error("upload_failed", "Could not finish indexing the PDF. Check the API terminal, then retry.", 503)
        finally:
            work_lock.release()

    @app.post("/questions")
    def questions():
        data = request.get_json()
        if not isinstance(data, dict) or set(data) - {"question", "top_k", "document_id"}:
            return error("invalid_request", "Send question, with optional top_k and document_id.", 400)
        question, top_k, document_id = data.get("question"), data.get("top_k", 3), data.get("document_id")
        if not isinstance(question, str) or not question.strip():
            return error("invalid_request", "Question must be a nonempty string.", 400)
        if type(top_k) is not int or not 1 <= top_k <= 10:
            return error("invalid_request", "top_k must be an integer from 1 to 10.", 400)
        if document_id is not None and (not isinstance(document_id, str) or not document_id.strip()):
            return error("invalid_request", "document_id must be a nonempty string.", 400)
        problem = acquire_index()
        if problem is not None:
            return problem
        started = time.perf_counter()
        try:
            try:
                matches = retrieve(question.strip(), model, db, top_k, document_id)
            except ValueError as exc:
                return error("invalid_request", str(exc), 400)
            except (OSError, RuntimeError) as exc:
                app.logger.warning("Retrieval failed: %s", exc)
                return error("index_unavailable", "Cannot search the index. Check the API terminal.", 503)
            try:
                result = generate_answer(question.strip(), matches)
            except ValueError as exc:
                app.logger.warning("Answer rejected: %s", exc)
                if str(exc).startswith("Model quote does not occur in "):
                    return error("generation_failed", "The model's evidence quote did not match the document text, so the answer was not displayed. Try asking for one specific fact.", 502)
                return error("generation_failed", "The model could not produce an answer that passed our checks. Try a narrower question.", 502)
            except RuntimeError as exc:
                app.logger.warning("Generator unavailable: %s", exc)
                return error("generator_unavailable", "The local model is unavailable or timed out. Check its terminal and retry.", 503)
            return jsonify(status=result["status"], answer=result["answer"],
                           citations=result["citations"], retrieved=result["retrieved"],
                           generation_seconds=result["generation_seconds"],
                           total_seconds=round(time.perf_counter() - started, 3))
        finally:
            work_lock.release()

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=8000, debug=False, use_reloader=False)

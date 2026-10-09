"use strict";

const byId = (id) => document.getElementById(id);
const form = byId("question-form");
const question = byId("question");
const documentSelect = byId("document");
let papersReady = false;
let busy = false;
let uploading = false;
let deleting = false;
let loadingDocuments = false;

// Model output and PDF text are untrusted text, never HTML.
function textElement(tag, text, className) {
  const element = document.createElement(tag);
  element.textContent = text;
  if (className) element.className = className;
  return element;
}

function updateControls() {
  byId("ask-button").disabled = busy || !papersReady;
  documentSelect.disabled = busy || !papersReady;
  question.disabled = busy;
  byId("example-button").disabled = busy;
  byId("reload-documents").disabled = busy || loadingDocuments;
  byId("ask-button").textContent = busy && !uploading && !deleting ? "Working…" : "Ask question ↗";
  byId("answer-panel").setAttribute("aria-busy", String(busy && !uploading && !deleting));
  byId("pdf-file").disabled = busy || loadingDocuments;
  byId("upload-button").disabled = busy || loadingDocuments;
  byId("upload-button").textContent = uploading ? "Adding…" : "Add PDF";
  byId("upload-form").setAttribute("aria-busy", String(uploading));
  document.querySelectorAll(".delete-document").forEach((button) => { button.disabled = busy || loadingDocuments; });
}

async function fetchJSON(url, options = {}, timeoutMs = 15000) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, { ...options, signal: controller.signal });
    let data;
    try { data = await response.json(); }
    catch { throw new Error("The server returned an unreadable response. Check that the API is running."); }
    if (!response.ok) throw new Error(data.error?.message || `Request failed (${response.status}).`);
    return data;
  } catch (error) {
    if (error.name === "AbortError") {
      throw new Error("The request timed out. The server may still be working; wait before trying again.");
    }
    if (error instanceof TypeError) throw new Error("Cannot reach the API. Check that it is running, then try again.");
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

async function loadDocuments(selectedId = documentSelect.value) {
  papersReady = false;
  loadingDocuments = true;
  updateControls();
  byId("reload-documents").disabled = true;
  byId("library-status").textContent = "Loading papers…";
  documentSelect.replaceChildren(new Option("All research papers", ""));
  byId("document-list").replaceChildren();
  try {
    const data = await fetchJSON("/documents");
    for (const paper of data.documents) {
      const item = textElement("li", "");
      item.append(textElement("span", paper.source, "document-name"));
      if (paper.can_delete === true) {
        const button = textElement("button", "Delete", "delete-document");
        button.type = "button";
        button.setAttribute("aria-label", `Delete ${paper.source}`);
        button.addEventListener("click", () => deleteDocument(paper));
        item.append(button);
      }
      byId("document-list").append(item);
      documentSelect.add(new Option(paper.source, paper.document_id));
    }
    papersReady = data.documents.length > 0;
    if (data.documents.some((paper) => paper.document_id === selectedId)) documentSelect.value = selectedId;
    byId("library-status").textContent = papersReady
      ? `${data.documents.length} ${data.documents.length === 1 ? "paper" : "papers"} available`
      : "No papers are indexed yet. Upload a PDF to start.";
    return true;
  } catch (error) {
    byId("library-status").textContent = error.message;
    return false;
  } finally {
    loadingDocuments = false;
    updateControls();
  }
}

async function deleteDocument(paper) {
  if (busy || loadingDocuments) return;
  if (!window.confirm(`Delete “${paper.source}”?\n\nThis removes its stored PDF and searchable passages from this app. This cannot be undone here.`)) return;
  busy = true;
  deleting = true;
  updateControls();
  byId("library-error").hidden = true;
  byId("library-action-status").textContent = `Deleting ${paper.source}…`;
  try {
    await fetchJSON(`/documents/${encodeURIComponent(paper.document_id)}`, { method: "DELETE" });
    // Clear old results so a removed source is not still displayed as current evidence.
    byId("answer-content").hidden = true;
    byId("answer-text").textContent = "";
    byId("answered-question").textContent = "";
    byId("citations").replaceChildren();
    byId("retrieved-passages").replaceChildren();
    byId("answer-time").textContent = "";
    byId("answer-title").textContent = "Your answer";
    byId("request-status").textContent = "";
    byId("request-error").hidden = true;
    byId("upload-status").textContent = "";
    byId("empty-message").hidden = false;
    byId("empty-message").textContent = "The collection has changed. Ask a question to get a fresh answer.";
    const refreshed = await loadDocuments();
    byId("library-action-status").textContent = `${paper.source} was deleted.${refreshed ? "" : " Refresh the paper list to update it."}`;
  } catch (error) {
    byId("library-action-status").textContent = "";
    byId("library-error").textContent = error.message;
    byId("library-error").hidden = false;
  } finally {
    deleting = false;
    busy = false;
    updateControls();
  }
}

function pdfLink(citation, label) {
  if (!/^[0-9a-f]{64}$/.test(citation.document_id || "") || !Number.isInteger(citation.page) || citation.page < 1) return null;
  const link = textElement("a", label, "pdf-link");
  link.href = `/documents/${citation.document_id}/pdf#page=${citation.page}`;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.setAttribute("aria-label", `Open ${citation.source}, physical page ${citation.page} (new tab)`);
  return link;
}

function renderAnswer(data, submittedQuestion) {
  byId("answer-title").textContent = data.status === "insufficient_evidence" ? "Not enough evidence" : "Your answer";
  byId("answered-question").textContent = submittedQuestion;
  const answer = byId("answer-text");
  answer.replaceChildren();
  const sources = new Map(data.citations.map((citation) => [`[${citation.source_id}]`, citation]));
  for (const part of data.answer.split(/(\[S\d+\])/g)) {
    const citation = sources.get(part);
    answer.append((citation && pdfLink(citation, part)) || document.createTextNode(part));
  }
  byId("answer-time").textContent = `${Number(data.total_seconds).toFixed(1)}s total`;
  const citations = byId("citations");
  citations.replaceChildren();
  for (const citation of data.citations) {
    const card = textElement("article", "", "source-card");
    card.append(textElement("p", `[${citation.source_id}] ${citation.source} · Physical page ${citation.page}`, "source-label"));
    card.append(textElement("blockquote", citation.quote));
    const link = pdfLink(citation, `Open PDF at page ${citation.page} ↗`);
    if (link) card.append(link);
    citations.append(card);
  }
  byId("sources-section").hidden = data.citations.length === 0;
  const passages = byId("retrieved-passages");
  passages.replaceChildren();
  for (const passage of data.retrieved) {
    const card = textElement("article", "", "passage-card");
    const contextLabel = passage.retrieval_role === "neighbor" ? " · Nearby context" : "";
    card.append(textElement("p", `[${passage.source_id}] ${passage.source} · Physical page ${passage.page} · Similarity ${Number(passage.score).toFixed(3)}${contextLabel}`, "source-label"));
    card.append(textElement("p", passage.text, "passage-text"));
    passages.append(card);
  }
  byId("retrieved-summary").textContent = `Inspect passages sent to the model (${data.retrieved.length})`;
  byId("retrieved-details").open = false;
  byId("retrieved-details").hidden = data.retrieved.length === 0;
  byId("empty-message").hidden = true;
  byId("answer-content").hidden = false;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (busy || !papersReady) return;
  const submittedQuestion = question.value.trim();
  question.setCustomValidity(submittedQuestion ? "" : "Please enter a question.");
  if (!form.reportValidity()) return;
  const payload = { question: submittedQuestion };
  if (documentSelect.value) payload.document_id = documentSelect.value;
  busy = true;
  updateControls();
  byId("request-error").hidden = true;
  byId("answer-content").hidden = true;
  byId("answer-time").textContent = "";
  byId("answer-title").textContent = "Your answer";
  byId("empty-message").hidden = false;
  byId("empty-message").textContent = "Reading the retrieved passages and preparing an answer…";
  const started = Date.now();
  const updateElapsed = () => {
    byId("request-status").textContent = `Working on your question · ${Math.floor((Date.now() - started) / 1000)}s elapsed. Local answers can take a few minutes.`;
  };
  updateElapsed();
  const timer = setInterval(updateElapsed, 1000);
  try {
    const data = await fetchJSON("/questions", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
    }, 240000);
    renderAnswer(data, submittedQuestion);
    byId("request-status").textContent = data.status === "insufficient_evidence"
      ? "Finished. The retrieved passages do not provide enough evidence."
      : "Answer ready. Review the supporting sources below.";
  } catch (error) {
    byId("request-status").textContent = "";
    byId("request-error").textContent = error.message;
    byId("request-error").hidden = false;
    byId("empty-message").textContent = "No answer was returned. Your question is still above so you can try again.";
  } finally {
    clearInterval(timer);
    busy = false;
    updateControls();
  }
});

question.addEventListener("input", () => question.setCustomValidity(""));
byId("reload-documents").addEventListener("click", () => loadDocuments());
byId("example-button").addEventListener("click", () => {
  question.value = "How many layers are in the Transformer encoder?";
  question.setCustomValidity("");
  documentSelect.value = "";
  question.focus();
});
byId("pdf-file").addEventListener("change", () => {
  byId("upload-error").hidden = true;
  byId("upload-status").textContent = "";
});
byId("upload-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (busy || loadingDocuments) return;
  const file = byId("pdf-file").files[0];
  byId("upload-error").hidden = true;
  byId("upload-status").textContent = "";
  if (!file || !file.name.toLowerCase().endsWith(".pdf") || file.size > 10 * 1024 * 1024 || file.size === 0) {
    byId("upload-error").textContent = "Choose a nonempty PDF up to 10 MB.";
    byId("upload-error").hidden = false;
    return;
  }
  const data = new FormData();
  data.append("file", file);
  busy = true;
  uploading = true;
  updateControls();
  const started = Date.now();
  const updateElapsed = () => {
    byId("upload-status").textContent = `Uploading and preparing your PDF · ${Math.floor((Date.now() - started) / 1000)}s elapsed. Keep this page open.`;
  };
  updateElapsed();
  const timer = setInterval(updateElapsed, 1000);
  try {
    // The browser sets the multipart boundary. Do not set Content-Type manually.
    const result = await fetchJSON("/documents", { method: "POST", body: data }, 600000);
    clearInterval(timer);
    const paper = result.document;
    const refreshed = await loadDocuments(paper.document_id);
    let message = result.status === "already_indexed"
      ? `${paper.source} is already in your collection. No duplicate was added.`
      : `${paper.source} is ready (${Number(result.total_seconds).toFixed(1)}s).`;
    if (paper.empty_pages?.length) {
      message += ` No readable text on physical pages ${paper.empty_pages.join(", ")}; answers cannot use those pages.`;
    }
    message += refreshed ? " The paper is selected below—ask a question." : " Refresh papers to select it.";
    byId("upload-status").textContent = message;
    byId("pdf-file").value = "";
  } catch (error) {
    byId("upload-status").textContent = "";
    byId("upload-error").textContent = error.message;
    byId("upload-error").hidden = false;
  } finally {
    clearInterval(timer);
    uploading = false;
    busy = false;
    updateControls();
  }
});
loadDocuments();

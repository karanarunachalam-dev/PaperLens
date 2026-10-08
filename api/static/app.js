"use strict";

const byId = (id) => document.getElementById(id);
const form = byId("question-form");
const question = byId("question");
const documentSelect = byId("document");
let papersReady = false;
let busy = false;

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
  byId("reload-documents").disabled = busy;
  byId("ask-button").textContent = busy ? "Working…" : "Ask question ↗";
  byId("answer-panel").setAttribute("aria-busy", String(busy));
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

async function loadDocuments() {
  papersReady = false;
  updateControls();
  byId("reload-documents").disabled = true;
  byId("library-status").textContent = "Loading papers…";
  const previousSelection = documentSelect.value;
  documentSelect.replaceChildren(new Option("All research papers", ""));
  byId("document-list").replaceChildren();
  try {
    const data = await fetchJSON("/documents");
    for (const paper of data.documents) {
      byId("document-list").append(textElement("li", paper.source));
      documentSelect.add(new Option(paper.source, paper.document_id));
    }
    papersReady = data.documents.length > 0;
    if (data.documents.some((paper) => paper.document_id === previousSelection)) documentSelect.value = previousSelection;
    byId("library-status").textContent = papersReady
      ? `${data.documents.length} ${data.documents.length === 1 ? "paper" : "papers"} available`
      : "No papers are indexed yet. Add papers to the research collection, then refresh.";
  } catch (error) {
    byId("library-status").textContent = error.message;
  } finally {
    updateControls();
  }
}

function renderAnswer(data, submittedQuestion) {
  byId("answer-title").textContent = data.status === "insufficient_evidence" ? "Not enough evidence" : "Your answer";
  byId("answered-question").textContent = submittedQuestion;
  byId("answer-text").textContent = data.answer;
  byId("answer-time").textContent = `${Number(data.total_seconds).toFixed(1)}s total`;
  const citations = byId("citations");
  citations.replaceChildren();
  for (const citation of data.citations) {
    const card = textElement("article", "", "source-card");
    card.append(textElement("p", `[${citation.source_id}] ${citation.source} · Physical page ${citation.page}`, "source-label"));
    card.append(textElement("blockquote", citation.quote));
    citations.append(card);
  }
  byId("sources-section").hidden = data.citations.length === 0;
  const passages = byId("retrieved-passages");
  passages.replaceChildren();
  for (const passage of data.retrieved) {
    const card = textElement("article", "", "passage-card");
    card.append(textElement("p", `[${passage.source_id}] ${passage.source} · Physical page ${passage.page} · Similarity ${Number(passage.score).toFixed(3)}`, "source-label"));
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
    byId("request-status").textContent = `Working on your question · ${Math.floor((Date.now() - started) / 1000)}s elapsed. Local answers can take a minute or two.`;
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
byId("reload-documents").addEventListener("click", loadDocuments);
byId("example-button").addEventListener("click", () => {
  question.value = "How many layers are in the Transformer encoder?";
  question.setCustomValidity("");
  documentSelect.value = "";
  question.focus();
});
loadDocuments();

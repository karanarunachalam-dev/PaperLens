# Short project demo

Use this as a 4–6 minute walkthrough, excluding local generation waits. It is a presentation script, not a claim that a video has been recorded. Complete [setup](setup.md), start both services, and keep the three reference papers available.

If recording, show waiting briefly and label time cuts. Show actual results rather than promising the recorded examples always recur.

## 1. Introduce the problem — 20 seconds

Open the homepage and say:

> This assistant helps me find answers in research PDFs and inspect the evidence. It retrieves passages, asks a local language model to explain them, and links citations to PDF pages. Uploading a paper does not train the model.

Point out the paper checkboxes and upload control. Choose one or several papers, or select **All research papers**. Qwen generates answers; BGE produces embeddings for retrieval.

## 2. Show a supported answer — 1 minute plus generation

Search all papers and ask:

> How many layers are in the Transformer encoder?

The recorded final check returned six layers with an exact quote on physical page 3 in 53.391 seconds of generation. That is an observation, not a guaranteed response time.

Show the answer, quote, and `[S1]`. Click the citation to open the PDF at page 3. Explain that the application supplies filenames/pages from stored metadata and checks whether the quote occurs in the cited passage.

## 3. Inspect retrieval — 30 seconds

Expand **Inspect passages sent to the model** and explain:

> A normal answer uses three search results. Similarity measures relevance, not correctness. If the model refuses or produces an invalid quote, one recovery attempt can include two neighboring chunks. Each retains its own page and source ID.

If only three passages appear, that is expected. Do not claim recovery ran when it did not.

## 4. Show an unsupported question — 30 seconds plus generation

Select the Transformer paper and ask:

> What annual salary was paid to the first author of Attention Is All You Need?

The recorded final check returned insufficient evidence after two attempts. Explain that abstention differs from invalid-quote errors, and retrieving similar text does not establish answerability. If the live result differs, inspect it and describe the limitation rather than calling it a successful refusal.

## 5. Show upload/deletion — optional 1 minute

Use a separate text-based research PDF you are comfortable displaying. Upload it, show its automatic selection, and ask one narrow factual question you have checked in the paper. Select **Delete** next to that upload and confirm its filename to demonstrate removal.

The imported reference papers cannot be deleted through this control. Re-uploading identical reference bytes is a duplicate, so use a different paper for this step. Avoid personal documents in a public demo.

## 6. Explain a real limitation — 40 seconds

Use the [recorded attention case](../reports/continuation-context.md) unless there is time for another model call:

> “What does attention mean?” initially failed while useful evidence was split across pages. Recovery now returns an answer, but its quote still does not support every detail of the explanation. Exact quote matching is useful; it is not a complete check of meaning.

Show the [evaluation summary](../reports/final-evaluation.md): software tests, historical retrieval measurements, and a small final development check. Do not describe the software-test pass count as answer accuracy.

## Portfolio description

> Built a local research-PDF question-answering application using BGE embeddings, Qdrant, Qwen through llama.cpp, and Flask. Implemented page-preserving extraction, upload/deletion, multi-paper selection, validated evidence quotes, PDF citation links, and bounded recovery with adjacent context. Evaluated retrieval and documented answer-quality failures separately from 87 automated software tests.

Be ready to explain why retrieval is not training, why a real quote can support a bad answer, why the original three-passage path is preserved, and why recovery stops after one retry.

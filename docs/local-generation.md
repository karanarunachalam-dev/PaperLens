# From retrieved passages to a cited answer

## The concept

The embedding model and the generator perform different jobs:

```text
Question → BGE embedding → Qdrant search → retrieved TEXT
                                              ↓
                              instructions + question + text
                                              ↓
                                        Qwen generator
                                              ↓
                                  answer + evidence references
                                              ↓
                              citation checks → displayed answer
```

BGE produces the vectors used to find passages. Qwen reads the question and those passages as text tokens. Neither model's weights change during this process. The generator never receives the 384-dimensional BGE vectors.

Example: Qdrant returns `Training batch size: 16.` with page 1 metadata. We label that passage `S1`. Qwen can produce `The training batch size was 16`, referencing `S1` and quoting the supporting words. Python maps `S1` back to the stored filename and page. We do not ask the generator to invent a filename or page number.

## Why this local model

We use **Qwen3.5-2B**, packaged by **Unsloth** as `Q4_K_M` GGUF, with **llama.cpp** on CPU. Qwen is the original model author; Unsloth provides this quantized file. Quantization represents many weights at lower precision, reducing memory and disk use with a possible quality tradeoff. `Q4_K_M` uses mixed precision; it does not mean every value is exactly four bits.

The file is 1,280,835,840 bytes (about 1.28 GB / 1.19 GiB). This is the file size, not total runtime RAM. The runtime also needs working memory and a context cache. We configure a 4,096-token context, one request at a time, four CPU threads, and at most 384 output tokens. These are conservative starting settings, not a hardware tuning result. Reasoning is disabled to keep short factual answers responsive.

Both artifacts have pinned versions and verified SHA-256 checksums in `config/local-generator.json`. Initial setup needs an internet download; cached embedding inference and generation run locally without a paid API. The provided runtime installer targets Linux x86-64. GPU drivers are not required.

## Code walkthrough

Read these functions in order:

1. `retrieve()` in `scripts/answer_question.py` encodes the question, searches Qdrant, and closes the embedded store. It returns text and metadata along with scores.
2. `make_messages()` in `scripts/grounded_answer.py` assigns instructions to the system message and serializes the question/passages into the user message. The instructions require evidence, treat document instructions as untrusted text, and allow abstention.
3. `generate_answer()` counts the formatted prompt using Qwen's tokenizer. BGE's token counts are not interchangeable with Qwen's. Input plus the output allowance must fit the context window; otherwise we return an explicit error instead of silently removing evidence.
4. The local `/v1/chat/completions` request runs Qwen. The server constrains output to a JSON shape. Temperature zero reduces sampling variability; it does not establish correctness.
5. `validate_answer()` checks output structure, source existence, and whether each evidence quote occurs in its cited passage, allowing whitespace differences. It attaches original PDF metadata and adds citation markers.

The important reasoning is **retrieve text → construct context → generate → verify references**. HTTP requests, command-line parsing, downloading, and JSON serialization are supporting code.

## Missing information and failures

- No retrieved passages: skip generation and return an insufficient-evidence response.
- Passages exist but lack an answer: the model should set `insufficient_evidence=true` with no statements. Python supplies a standard message: “The retrieved passages do not provide enough evidence to answer this question.”
- A fabricated source or quote: reject the response and report a generation error.
- Output truncation, unavailable server, or oversized context: report an error. These are not evidence that the documents lack an answer.

A valid quote does **not** prove that the accompanying claim follows from it. For example, quoting “batch size: 16” while claiming “batch size: 32” is still a semantic error that these mechanical checks cannot detect. JSON constraints guarantee structure only. Prompt instructions reduce risk but are not a complete defense against malicious documents. Real-paper evaluation must measure answer correctness, faithfulness, and citation support separately.

## Run it

From the repository root, one-time setup (already completed on this laptop):

```bash
.venv/bin/python -m scripts.setup_local_generator
```

Start the generator in one terminal, leaving it running:

```bash
.venv/bin/python -m scripts.start_local_model
```

In a second terminal:

```bash
HF_HUB_OFFLINE=1 .venv/bin/python -m scripts.answer_question "What training batch size does each document report?"
HF_HUB_OFFLINE=1 .venv/bin/python -m scripts.answer_question "What was the lead researcher's salary?"
```

Use `--document-id` with an ID from `scripts.search_documents list` to restrict retrieval before generation. Add `--json` to inspect the full retrieved context, raw model output, and timings. Press Ctrl+C in the server terminal when finished to release model memory.

The localhost service is a development tool. Application authentication and deployment hardening belong to the later API/UI module.

## Focused reading

Spend about 10 minutes reading the [Qwen model card's model details and usage](https://huggingface.co/Qwen/Qwen3.5-2B), the [Unsloth GGUF file listing](https://huggingface.co/unsloth/Qwen3.5-2B-GGUF/tree/f6d5376be1edb4d416d56da11e5397a961aca8ae), and llama.cpp's [chat completion and structured-output documentation](https://github.com/ggml-org/llama.cpp/blob/b11429/tools/server/README.md). Focus on how a pretrained model is loaded and how text messages become an inference request; skip training and multimodal examples for this module.

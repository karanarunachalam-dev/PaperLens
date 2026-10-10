# Usage examples

Complete [setup](setup.md), start both services, and open the homepage. The examples below use the reference papers installed during setup. Local generation can take a few minutes, and results can vary.

## Ask a factual question

Under **Search in**, choose the Transformer paper or **All research papers**, then ask:

> How many layers are in the Transformer encoder?

The [recorded evaluation](../reports/final-evaluation.md) returned six layers with a supporting quote on physical page 3. Read the answer and quote, then click `[S1]` to check the original PDF. Filenames and pages come from stored metadata; Python checks whether the proposed quote occurs in the cited passage.

## Choose multiple papers and inspect retrieval

Tick the papers to include under **Search in**. Retrieval ranks chunks only within that selection. The default budget is three matches across the selected papers, so a result need not include every paper.

Expand **Inspect passages sent to the model** to read the actual context. Similarity measures relevance, not correctness. If the first attempt abstains or produces a quote mismatch, one recovery attempt can add up to two neighboring chunks. Each retains its own page and source ID. Additional passages are labeled **Nearby context**.

## Try an unsupported question

Select the Transformer paper and ask:

> What annual salary was paid to the first author of Attention Is All You Need?

The recorded evaluation returned insufficient evidence after two attempts. This differs from an invalid-quote error: abstention means the model did not provide an answer from the retrieved evidence, while a quote error means the proposed evidence failed validation. Neither establishes that the entire document lacks an answer.

## Add and remove a paper

Choose a text-based research PDF and select **Add PDF**. A successful upload selects that paper automatically. Ask a narrow factual question whose answer you can check in the source, or tick other papers to include them too.

Select **Delete** next to a web upload and confirm its filename to remove its app-managed copy and indexed passages. The original file outside app storage is unaffected. Imported reference papers are protected, and uploading identical bytes reuses an existing document.

## Understand the limits

In the [recorded attention case](../reports/continuation-context.md), useful evidence was split across pages. Recovery produced an answer, but its quote did not support every detail of the explanation. Exact quote matching checks provenance; it does not fully check meaning.

The [evaluation summary](../reports/final-evaluation.md) separates software tests, retrieval measurements, and reviewed model answers. A passing software test suite is not an answer-accuracy score.

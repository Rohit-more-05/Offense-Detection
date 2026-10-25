# Inference and feedback diagnosis

Verified on `api-inference-2`, 26 October 2026. The existing Keras model weights
were preserved. These results describe this small diagnostic folder, not general
accuracy on Indian memes.

## Why the original predictions failed

- Tesseract was installed but not on PATH. Cloud OCR failures could leave empty
  text, and the application still returned a binary prediction.
- Even working OCR changed words or missed text. A multimodal model cannot recover
  the intended meaning reliably from an incorrect transcription.
- The baseline is EfficientNetB0 + a bidirectional LSTM with a 64-token text limit.
  It always produces a binary score, including for identity cards and screenshots
  outside its training task. A high score does not establish that an input is a meme.
- The API forced automatic decisions at 0.5 and marked them reviewed. That bypassed
  the review band and confused model decisions with human ground truth.
- Feedback failures were hidden; image filenames did not reliably resolve to saved
  uploads. Local-only image storage would also lose training material on redeploy.
- Port 8000 belonged to another project. The frontend now checks the backend's
  service identity and uses port 8001 locally.

## Measured results

All 12 supplied images were inspected. Filename labels were used for evaluation
only; anonymous filenames were submitted to inference. The weights did not change.

| Diagnostic condition | Correct binary outputs at 0.5 |
| --- | --- |
| Working Tesseract transcription + existing baseline | 7 / 12 |
| RapidOCR transcription + same baseline | 10 / 12 |
| RapidOCR + baseline, excluding the ID card and structure screenshot | 9 / 10 memes |

Two important remaining errors with RapidOCR:

| Image | User label | Raw harmful-class score | Baseline result |
| --- | --- | --- | --- |
| Cinderella / misogyny example | Harmful | 0.064746 | Safe: false negative |
| ID card | Safe (outside meme scope) | 0.920487 | Harmful: false positive |

The structure screenshot's score fell from approximately 0.840380 with Tesseract
to 0.321463 with RapidOCR. Improving OCR helps, but changing a threshold cannot
solve both the Cinderella and ID-card errors. Context understanding and input
scope are separate problems.

The default hybrid pipeline preserves the baseline score and uses the existing
Gemini integration as a separate contextual verifier. It can recognize non-memes
and interpret image/text relationships. It is not an improvement to the CNN's
weights and its output is explicitly identified in the UI.

During the full live HTTP run, Gemini quota was exhausted. All 12 uploads returned
HTTP 200, were saved, and were routed to **Needs review**. This is 12 abstentions,
not 12 correct predictions. Earlier successful verifier calls are exploratory
evidence, not a completed hybrid accuracy benchmark. The raw local-model output
remains available when verification is unavailable. Reliable automatic hybrid
decisions require available provider quota and further independent evaluation.

## Feedback and training verification

- Supabase schema is at migration 004. Transaction-pool prepared-statement errors
  were addressed in the application and migration connection configuration.
- All 12 diagnostic image endpoints returned HTTP 200. Their supplied labels were
  saved through the real verdict API and removed from the pending queue. The ID
  card and structure screenshot were recorded as non-memes for scope training.
- Images are now stored durably in `meme_images`, deduplicated by SHA-256. Legacy
  backfill recovered 12 available images; 39 older files were unavailable locally.
  Missing originals cannot be reconstructed from their prediction records.
- A further live upload after the durable-storage change returned HTTP 200,
  retrieved identical image bytes, accepted the supplied safe verdict, and passed
  a fresh database read of both the verdict and stored bytes.
- The feedback export produced 12 distinct examples. Fourteen other reviewed
  records were excluded because their images were missing. Exports retain human
  labels separately from the original prediction and exclude conflicting duplicates.
- The training command validates explicit train/validation/test splits, rejects
  duplicate-image leakage, and writes a separate candidate. A one-epoch run on six
  synthetic examples verified training plumbing only; it says nothing about model
  quality. The deployed model was not retrained on these diagnostic examples.

Verification passed: 33 backend tests, three frontend API-client tests, production
frontend build and lint. Backend tests use isolated SQLite and mocked model/provider
responses; real model/OCR and Supabase were checked separately as described above.
Visual browser verification was blocked by the computer-use URL check.

Private per-image results and feedback are saved locally under `output/evaluation`
and `output/feedback`; these folders and the supplied images are excluded from Git.

## Next model improvement

Build a larger reviewed Indian-context corpus covering Hindi, English, Hinglish,
regional languages, implicit misogyny, sarcasm, benign identity references and
non-meme documents/screenshots. Record annotation disagreements, split by template
and source to reduce leakage, and keep an untouched final test set. Evaluate a
scope classifier separately from harmful-meme classification. Compare a stronger
multimodal encoder with this baseline using precision, recall, F1, false-positive
rates and review coverage, and calibrate thresholds on validation data. Promote
a candidate only after this comparison; saving feedback alone does not retrain it.

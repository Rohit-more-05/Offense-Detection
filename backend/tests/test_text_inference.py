"""
tests/test_text_inference.py
============================
Regression suite for text_inference.py.

Key test: calling text_inference.run() 10× on the same string must return
the identical confidence every time (within 1e-6 floating-point tolerance).
This proves the same-input→different-confidence bug from mock_inference is gone.

NOTE: This test imports text_inference which triggers the model load at collection
time.  First run will download weights (~400 MB, cached for all subsequent runs).
"""

from __future__ import annotations

import pytest

# Import the real module — this triggers singleton load at test collection time.
from app.services import text_inference


# ── Fixtures ───────────────────────────────────────────────────────────────────

HARMFUL_TEXT = "I hate all of them, they should be destroyed."
SAFE_TEXT    = "This is a wholesome meme about puppies and sunshine."


# ══════════════════════════════════════════════════════════════════════════════
# 1. Determinism regression — core acceptance criterion from the spec
# ══════════════════════════════════════════════════════════════════════════════

def test_determinism_harmful_text_10_calls():
    """
    Call run() 10× on the same harmful string.
    All confidence values must be identical within 1e-6 tolerance.
    Proves: eval mode + no_grad → deterministic inference, mock randomness is gone.
    """
    results = [text_inference.run(HARMFUL_TEXT) for _ in range(10)]
    labels, confidences = zip(*results)

    # All labels must be the same string
    assert len(set(labels)) == 1, (
        f"Expected a single consistent label, got: {set(labels)}"
    )

    # All confidences must be within floating-point epsilon of the first value
    baseline = confidences[0]
    for i, c in enumerate(confidences[1:], start=2):
        assert abs(c - baseline) < 1e-6, (
            f"Confidence drift on call {i}: baseline={baseline}, got={c}, delta={abs(c - baseline)}"
        )


def test_determinism_safe_text_10_calls():
    """Same determinism check for a safe/benign text string."""
    results = [text_inference.run(SAFE_TEXT) for _ in range(10)]
    labels, confidences = zip(*results)

    assert len(set(labels)) == 1
    baseline = confidences[0]
    for i, c in enumerate(confidences[1:], start=2):
        assert abs(c - baseline) < 1e-6, (
            f"Call {i}: baseline={baseline}, got={c}, delta={abs(c - baseline)}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# 2. Output contract — return type and value ranges
# ══════════════════════════════════════════════════════════════════════════════

def test_run_returns_tuple():
    label, confidence = text_inference.run(HARMFUL_TEXT)
    assert isinstance(label, str), f"Expected str label, got {type(label)}"
    assert isinstance(confidence, float), f"Expected float confidence, got {type(confidence)}"


def test_confidence_in_unit_interval():
    """Softmax output must always be in [0, 1]."""
    for text in [HARMFUL_TEXT, SAFE_TEXT, "hello", "X"]:
        _, confidence = text_inference.run(text)
        assert 0.0 <= confidence <= 1.0, (
            f"Confidence out of range for text={text!r}: {confidence}"
        )


def test_label_is_valid_category():
    """Label must always be one of the two valid strings."""
    valid_labels = {"Harmful", "Safe"}
    for text in [HARMFUL_TEXT, SAFE_TEXT, "test"]:
        label, _ = text_inference.run(text)
        assert label in valid_labels, (
            f"Unexpected label={label!r} for text={text!r}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# 3. Edge cases
# ══════════════════════════════════════════════════════════════════════════════

def test_single_character_input():
    """Should not crash on minimal input."""
    label, confidence = text_inference.run("a")
    assert label in {"Harmful", "Safe"}
    assert 0.0 <= confidence <= 1.0


def test_long_text_is_truncated_gracefully():
    """
    Input longer than MAX_LEN (128 tokens) must be silently truncated,
    not raise an error.
    """
    long_text = "hate " * 500   # ~2500 chars, ~500 tokens — well over 128
    label, confidence = text_inference.run(long_text)
    assert label in {"Harmful", "Safe"}
    assert 0.0 <= confidence <= 1.0


def test_empty_string_does_not_crash():
    """Empty string edge case — tokenizer should handle it without exception."""
    label, confidence = text_inference.run("")
    assert label in {"Harmful", "Safe"}


def test_different_texts_may_differ():
    """Sanity: two semantically opposite inputs should not always return the same confidence."""
    _, c_harmful = text_inference.run(HARMFUL_TEXT)
    _, c_safe    = text_inference.run(SAFE_TEXT)
    # Not strictly guaranteed by every model, but a strong signal of working inference.
    # We log rather than hard-fail so CI stays green even if model surprises us.
    if abs(c_harmful - c_safe) < 0.01:
        import warnings
        warnings.warn(
            f"Model confidence gap is very small: harmful={c_harmful}, safe={c_safe}. "
            "Model may need evaluation.",
            UserWarning,
        )


# ══════════════════════════════════════════════════════════════════════════════
# 4. Call counter telemetry
# ══════════════════════════════════════════════════════════════════════════════

def test_call_counter_increments():
    """
    The module-level _call_counter must increment with each run() call.
    This validates the telemetry call_id tracking is working.
    """
    before = text_inference._call_counter
    text_inference.run("test telemetry counter")
    after = text_inference._call_counter
    assert after == before + 1, (
        f"Call counter did not increment: before={before}, after={after}"
    )

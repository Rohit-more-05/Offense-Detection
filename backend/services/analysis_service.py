"""One inference policy shared by both upload endpoints.

Class labels, the raw local-model score, automated actions and human verdicts
are separate concepts. No filename, test label or moderator verdict enters ML.
"""
from dataclasses import dataclass, field
import logging

from core.config import get_settings
from services import decision_router, model_service, ocr_service

logger = logging.getLogger(__name__)


@dataclass
class Analysis:
    label: str = "Needs review"
    harmful_probability: float | None = None
    baseline_label: str | None = None
    moderation_decision: str = "HUMAN_REVIEW"
    content_type: str = "unknown"
    extracted_text: str = ""
    ocr_source: str = "unavailable"
    ocr_status: str = "error"
    decision_source: str = "abstained"
    reason: str = "Insufficient evidence for an automated decision."
    model_version: str | None = None
    warnings: list[str] = field(default_factory=list)
    diagnostics: dict = field(default_factory=dict)


def analyze(image_path: str, manual_text: str | None = None) -> Analysis:
    ocr = ocr_service.analyze_image(image_path)
    assessment = ocr.assessment
    result = Analysis(
        extracted_text=ocr.text, ocr_status=ocr.status, ocr_source=ocr.source,
        warnings=list(ocr.warnings),
    )
    if assessment:
        result.content_type = assessment.content_type
        result.diagnostics["context_assessment"] = assessment.model_dump(exclude={"extracted_text"})
        result.diagnostics["context_provider"] = ocr.context_source
        if assessment.content_type in {"document", "screenshot", "photograph"} and assessment.certainty != "low":
            result.label = "Not a meme"
            result.decision_source = "input_scope"
            result.reason = "This appears to be a " + assessment.content_type + ". Meme classification does not apply; this is not a safety verdict."
            return result

    override = bool(manual_text and manual_text.strip())
    if override:
        result.extracted_text = manual_text.strip()
        result.ocr_source = "manual_override"
        result.ocr_status = "ok"
        result.warnings.append("A supplied transcription was used. A moderator should verify it against the image.")
    if result.ocr_status == "error" or not result.extracted_text.strip():
        result.reason = "Text could not be read reliably. No automatic safe/harmful verdict was made."
        return result
    if not override and ocr.local_confidence is not None and ocr.local_confidence < 0.6 and not assessment:
        result.reason = "Text recognition quality is low. Review or supply a clearer image."
        return result

    try:
        probability = model_service.predict(image_path, result.extracted_text)
        result.harmful_probability = probability
        result.baseline_label = "Harmful" if probability > 0.5 else "Safe"
        result.model_version = model_service.MODEL_VERSION
        result.diagnostics.update(model_service.text_diagnostics(result.extracted_text))
    except Exception:
        logger.exception("Local multimodal inference failed")
        result.reason = "The local model could not complete inference. Please retry or review manually."
        result.warnings.append("Local model inference failed.")
        return result

    result.label = result.baseline_label
    result.decision_source = "baseline"
    result.reason = "Local multimodal model prediction; its score has not been calibrated on this input domain."
    result.moderation_decision = decision_router.route(probability)

    if get_settings().context_verification_enabled:
        if not assessment or assessment.content_type != "meme" or not assessment.text_readable:
            result.label = "Needs review"
            result.decision_source = "abstained"
            result.reason = "Meme context or text legibility could not be verified. The local score is shown for inspection only."
            result.moderation_decision = "HUMAN_REVIEW"
        elif assessment.verdict in {"uncertain", "not_applicable"} or assessment.certainty == "low":
            result.label = "Needs review"
            result.decision_source = "abstained"
            result.reason = assessment.reason
            result.moderation_decision = "HUMAN_REVIEW"
        elif not override:
            result.label = "Harmful" if assessment.verdict == "harmful" else "Safe"
            result.decision_source = "context_verifier"
            result.reason = assessment.reason
            # A contextual label is not a new calibrated probability. Disagreement
            # or less-than-high certainty always needs human review.
            if result.label != result.baseline_label:
                result.warnings.append("The local model and contextual verifier disagree.")
                result.moderation_decision = "HUMAN_REVIEW"
            if assessment.certainty != "high":
                result.moderation_decision = "HUMAN_REVIEW"

    if override or result.diagnostics.get("text_may_be_truncated") or result.diagnostics.get("unknown_token_fraction", 0) > 0.5:
        result.moderation_decision = "HUMAN_REVIEW"
        if result.diagnostics.get("text_may_be_truncated"):
            result.warnings.append("The local model only reads its first 64 text tokens.")
        if result.diagnostics.get("unknown_token_fraction", 0) > 0.5:
            result.warnings.append("Most text tokens are outside the local model's vocabulary.")
    return result

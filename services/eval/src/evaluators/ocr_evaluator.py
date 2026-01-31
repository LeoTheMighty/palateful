"""OCR evaluator for image-to-text extraction."""

from pathlib import Path

from PIL import Image

from src.config import EvalConfig
from src.evaluators.base import BaseEvaluator, EvalCase, EvalResult
from src.metrics.text_metrics import TextMetrics


class OCREvaluator(BaseEvaluator):
    """Evaluates OCR model performance on image inputs."""

    name = "ocr"

    def __init__(self, config: EvalConfig):
        super().__init__(config)
        self._model_loaded = False

    def load_cases(self) -> list[EvalCase]:
        """Load OCR test cases from manifest."""
        manifest = self.load_manifest()
        cases = []

        for case_data in manifest.get("cases") or []:
            case_id = case_data["id"]
            image_path = self.suite_dir / case_data.get("image", f"images/{case_id}.jpg")
            expected_path = self.suite_dir / case_data.get("expected", f"expected/{case_id}.md")

            # Load expected text if available
            expected_text = None
            if expected_path.exists():
                expected_text = expected_path.read_text(encoding="utf-8")

            cases.append(EvalCase(
                id=case_id,
                input_path=image_path,
                expected_path=expected_path,
                expected_data=expected_text,
                tags=case_data.get("tags", []),
                metadata=case_data.get("metadata", {}),
            ))

        return cases

    def evaluate(self, case: EvalCase) -> EvalResult:
        """Evaluate OCR on a single image."""
        result = EvalResult(case_id=case.id)

        # Check if input exists
        if not case.input_path or not case.input_path.exists():
            result.error = f"Image not found: {case.input_path}"
            return result

        # Check cache first
        cache_key = case.get_cache_key()
        cached = self.get_cached_response(cache_key)
        if cached is not None:
            result.actual_output = cached.get("text", "")
            result.cache_hit = True
        else:
            # Run OCR
            try:
                text, duration_ms = self._run_ocr(case.input_path)
                result.actual_output = text
                result.duration_ms = duration_ms

                # Cache the response
                self.save_cached_response(cache_key, {"text": text})
            except Exception as e:
                result.error = str(e)
                return result

        # If no expected output, just return the actual output
        if case.expected_data is None:
            result.passed = True
            result.metrics["note"] = "No expected output to compare"
            return result

        result.expected_output = case.expected_data

        # Calculate metrics
        metrics = TextMetrics.calculate_all(
            actual=result.actual_output,
            expected=case.expected_data,
        )
        result.metrics = metrics

        # Determine pass/fail based on character accuracy
        char_accuracy = metrics.get("character_accuracy", 0)
        result.passed = char_accuracy >= self.config.thresholds.ocr_character_accuracy

        return result

    def _run_ocr(self, image_path: Path) -> tuple[str, float]:
        """Run OCR on an image file.

        Returns:
            Tuple of (extracted_text, duration_ms)
        """
        if self.config.ocr_mode == "mock":
            # Return empty string in mock mode if no cache
            return "", 0.0

        # Import and run the production OCR code

        # Lazy import to avoid loading heavy dependencies unless needed
        from services.ocr.src.model import run_ocr

        image = Image.open(image_path)

        text, duration = self.timed_execution(run_ocr, image)

        return text, duration

    def _load_model(self) -> None:
        """Pre-load the OCR model if not already loaded."""
        if self._model_loaded:
            return

        if self.config.ocr_mode != "mock":
            try:
                from services.ocr.src.model import load_model
                load_model()
                self._model_loaded = True
            except ImportError:
                pass  # Model loading is optional

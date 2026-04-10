"""Tests for the strategies module."""

import pytest

from src.strategies import (
    STRATEGIES,
    get_strategy_function,
    list_strategies,
    run_ocr_then_text,
    run_text_extraction,
    run_vision_extraction,
)


class TestStrategyRegistry:
    def test_all_strategies_defined(self):
        assert "text_extractor" in STRATEGIES
        assert "vision_extractor" in STRATEGIES
        assert "ocr_then_text" in STRATEGIES

    def test_strategy_has_required_keys(self):
        for key, entry in STRATEGIES.items():
            assert "name" in entry, f"Strategy '{key}' missing 'name'"
            assert "description" in entry, f"Strategy '{key}' missing 'description'"
            assert "function" in entry, f"Strategy '{key}' missing 'function'"
            assert "input_types" in entry, f"Strategy '{key}' missing 'input_types'"

    def test_input_types_are_valid(self):
        valid_types = {"text", "image", "url"}
        for key, entry in STRATEGIES.items():
            for itype in entry["input_types"]:
                assert itype in valid_types, (
                    f"Strategy '{key}' has invalid input type: '{itype}'"
                )


class TestGetStrategyFunction:
    def test_valid_strategy(self):
        func = get_strategy_function("text_extractor")
        assert callable(func)
        assert func is run_text_extraction

    def test_invalid_strategy(self):
        with pytest.raises(ValueError, match="Unknown strategy"):
            get_strategy_function("nonexistent_strategy")


class TestListStrategies:
    def test_returns_list(self):
        result = list_strategies()
        assert isinstance(result, list)
        assert len(result) == len(STRATEGIES)

    def test_entries_have_key(self):
        result = list_strategies()
        for entry in result:
            assert "key" in entry
            assert "name" in entry


class TestVisionExtraction:
    def test_raises_file_not_found_for_missing_image(self):
        with pytest.raises(FileNotFoundError, match="Image file not found"):
            run_vision_extraction("nonexistent_image.jpg")


class TestOcrThenText:
    def test_raises_file_not_found_for_missing_sidecar(self, tmp_path):
        # Create an image file but no sidecar
        img_path = tmp_path / "test_recipe.jpg"
        img_path.write_bytes(b"fake image data")
        with pytest.raises(FileNotFoundError, match="OCR sidecar not found"):
            run_ocr_then_text(str(img_path))

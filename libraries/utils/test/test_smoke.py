"""Smoke tests for utils library."""


def test_import_utils():
    """Verify the utils package can be imported."""
    import utils
    assert utils is not None


def test_import_models():
    """Verify model modules can be imported."""
    from utils.models import user, recipe, recipe_book
    assert user is not None
    assert recipe is not None
    assert recipe_book is not None


def test_error_codes():
    """Verify ErrorCode enum is accessible."""
    from utils.classes.error_code import ErrorCode
    assert hasattr(ErrorCode, "INTERNAL_ERROR")

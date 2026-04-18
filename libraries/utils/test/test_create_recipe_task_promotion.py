"""Tests for source-photo promotion in create_recipe_task (bugs-imp-pho-4).

The helper `_maybe_promote_source_photo` runs after the Recipe row is
committed and covers the FR87 happy path (extractor-supplied hero is
missing, s3_keys are present) plus every skip/failure branch. We
exercise the helper directly to keep the tests narrow — end-to-end
create_recipe_task coverage lives elsewhere.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from utils.models.import_item import ImportItem
from utils.models.import_job import ImportJob
from utils.tasks.import_tasks.create_recipe_task import CreateRecipeTask


def _make_task() -> CreateRecipeTask:
    task = CreateRecipeTask()
    database = MagicMock()
    database.db = MagicMock()
    database.db.commit = MagicMock()
    task.database = database
    task.user_id = uuid.uuid4()
    return task


def _make_recipe(image_url=None) -> SimpleNamespace:
    return SimpleNamespace(id=uuid.uuid4(), image_url=image_url)


def _make_item(s3_keys=None) -> SimpleNamespace:
    item = SimpleNamespace(
        id=uuid.uuid4(),
        raw_data={"s3_keys": s3_keys} if s3_keys is not None else {},
    )
    # Pretend it's a real ImportItem for isinstance checks; the task only
    # reads raw_data off it so SimpleNamespace is fine in practice.
    return item


def _make_job() -> SimpleNamespace:
    return SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4())


# ---------- happy path ----------


def test_promotes_when_image_url_empty_and_s3_keys_present():
    task = _make_task()
    recipe = _make_recipe(image_url=None)
    item = _make_item(s3_keys=["uploads/u1/photo.jpg"])
    job = _make_job()

    with patch(
        "utils.tasks.import_tasks.create_recipe_task.promote_source_photo",
        return_value="https://bucket.s3.us-east-1.amazonaws.com/recipe-photos/x/y/source-20260417T000000.jpg",
    ) as promote, patch(
        "utils.tasks.import_tasks.create_recipe_task._get_aws_service"
    ) as get_aws:
        get_aws.return_value = MagicMock()
        task._maybe_promote_source_photo(recipe, item, job)

    promote.assert_called_once()
    assert recipe.image_url.startswith("https://bucket.s3.us-east-1.amazonaws.com/")
    task.database.db.commit.assert_called_once()


# ---------- skip branches ----------


def test_skips_when_image_url_already_set():
    task = _make_task()
    recipe = _make_recipe(image_url="https://extractor-supplied-image.png")
    item = _make_item(s3_keys=["uploads/u1/photo.jpg"])
    job = _make_job()

    with patch(
        "utils.tasks.import_tasks.create_recipe_task.promote_source_photo"
    ) as promote:
        task._maybe_promote_source_photo(recipe, item, job)

    promote.assert_not_called()
    assert recipe.image_url == "https://extractor-supplied-image.png"


def test_skips_when_s3_keys_missing():
    task = _make_task()
    recipe = _make_recipe(image_url=None)
    item = _make_item(s3_keys=None)  # e.g. URL import
    job = _make_job()

    with patch(
        "utils.tasks.import_tasks.create_recipe_task.promote_source_photo"
    ) as promote:
        task._maybe_promote_source_photo(recipe, item, job)

    promote.assert_not_called()
    assert recipe.image_url is None


def test_skips_when_s3_keys_empty():
    task = _make_task()
    recipe = _make_recipe(image_url=None)
    item = _make_item(s3_keys=[])
    job = _make_job()

    with patch(
        "utils.tasks.import_tasks.create_recipe_task.promote_source_photo"
    ) as promote:
        task._maybe_promote_source_photo(recipe, item, job)

    promote.assert_not_called()


def test_skips_when_image_url_empty_string():
    """Empty-string image_url is treated like None."""
    task = _make_task()
    recipe = _make_recipe(image_url="")
    item = _make_item(s3_keys=["uploads/u1/photo.jpg"])
    job = _make_job()

    with patch(
        "utils.tasks.import_tasks.create_recipe_task.promote_source_photo",
        return_value="https://bucket/promoted.jpg",
    ) as promote, patch(
        "utils.tasks.import_tasks.create_recipe_task._get_aws_service"
    ):
        task._maybe_promote_source_photo(recipe, item, job)

    promote.assert_called_once()
    assert recipe.image_url == "https://bucket/promoted.jpg"


# ---------- promotion failure branches ----------


def test_returns_none_leaves_recipe_image_url_unchanged():
    """When promote_source_photo returns None (S3 failure), image_url stays None."""
    task = _make_task()
    recipe = _make_recipe(image_url=None)
    item = _make_item(s3_keys=["uploads/u1/photo.jpg"])
    job = _make_job()

    with patch(
        "utils.tasks.import_tasks.create_recipe_task.promote_source_photo",
        return_value=None,
    ), patch(
        "utils.tasks.import_tasks.create_recipe_task._get_aws_service"
    ):
        task._maybe_promote_source_photo(recipe, item, job)

    assert recipe.image_url is None
    task.database.db.commit.assert_not_called()


def test_unexpected_raise_does_not_propagate():
    """An exception inside the promotion path must not fail recipe creation."""
    task = _make_task()
    recipe = _make_recipe(image_url=None)
    item = _make_item(s3_keys=["uploads/u1/photo.jpg"])
    job = _make_job()

    with patch(
        "utils.tasks.import_tasks.create_recipe_task._get_aws_service",
        side_effect=RuntimeError("boto3 blew up"),
    ):
        # Must not raise
        task._maybe_promote_source_photo(recipe, item, job)

    assert recipe.image_url is None


# ---------- first key wins ----------


def test_uses_first_s3_key_for_multi_page():
    task = _make_task()
    recipe = _make_recipe(image_url=None)
    item = _make_item(s3_keys=["uploads/page1.jpg", "uploads/page2.jpg"])
    job = _make_job()

    with patch(
        "utils.tasks.import_tasks.create_recipe_task.promote_source_photo",
        return_value="https://bucket/x.jpg",
    ) as promote, patch(
        "utils.tasks.import_tasks.create_recipe_task._get_aws_service"
    ):
        task._maybe_promote_source_photo(recipe, item, job)

    kwargs = promote.call_args.kwargs
    assert kwargs["source_s3_key"] == "uploads/page1.jpg"
    assert kwargs["user_id"] == job.user_id
    assert kwargs["recipe_id"] == recipe.id

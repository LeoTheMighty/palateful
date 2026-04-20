"""cmt-2 — timer clamp + independent audit in create_recipe_task.

Covers the `_clamp_timers` pure function directly plus the
`_log_timer_clamp` helper's independent-commit contract (audit row
persists across main-txn rollback).
"""

from unittest.mock import MagicMock, patch

from utils.tasks.import_tasks.create_recipe_task import (
    _TIMER_LABEL_MAX_LEN,
    _TIMER_MAX_PER_STEP,
    _clamp_timers,
    _log_timer_clamp,
)


# ---------------------------------------------------------------------
# _clamp_timers
# ---------------------------------------------------------------------


def test_clamp_happy_path_preserves_exact_list():
    clean, dropped = _clamp_timers(
        [{"duration_minutes": 15, "label": "simmer"}]
    )
    assert clean == [{"duration_minutes": 15, "label": "simmer"}]
    assert dropped == 0


def test_clamp_non_list_returns_empty_zero_dropped():
    # Null / missing keys / wrong type all coerce to empty, no drop.
    assert _clamp_timers(None) == ([], 0)
    assert _clamp_timers("not a list") == ([], 0)
    assert _clamp_timers({"duration_minutes": 15}) == ([], 0)


def test_clamp_rejects_string_duration():
    clean, dropped = _clamp_timers(
        [{"duration_minutes": "25", "label": "bake"}]
    )
    assert clean == []
    assert dropped == 1


def test_clamp_rejects_bool_duration():
    # isinstance(True, int) is True in Python — guard explicitly.
    clean, dropped = _clamp_timers(
        [{"duration_minutes": True, "label": "x"}]
    )
    assert clean == []
    assert dropped == 1


def test_clamp_rejects_out_of_range_duration():
    clean, dropped = _clamp_timers(
        [
            {"duration_minutes": 0, "label": "zero"},
            {"duration_minutes": 361, "label": "too long"},
            {"duration_minutes": -5, "label": "negative"},
        ]
    )
    assert clean == []
    assert dropped == 3


def test_clamp_default_label_when_empty():
    clean, _ = _clamp_timers([{"duration_minutes": 5, "label": ""}])
    assert clean == [{"duration_minutes": 5, "label": "timer"}]


def test_clamp_default_label_when_missing():
    clean, _ = _clamp_timers([{"duration_minutes": 5}])
    assert clean == [{"duration_minutes": 5, "label": "timer"}]


def test_clamp_default_label_when_non_string():
    clean, _ = _clamp_timers([{"duration_minutes": 5, "label": 42}])
    assert clean == [{"duration_minutes": 5, "label": "timer"}]


def test_clamp_label_truncated_to_40_chars_and_stripped():
    long_label = "   " + "a" * 80 + "   "
    clean, _ = _clamp_timers([{"duration_minutes": 5, "label": long_label}])
    assert clean[0]["label"] == "a" * _TIMER_LABEL_MAX_LEN


def test_clamp_non_dict_entries_dropped():
    clean, dropped = _clamp_timers(["not a dict", 42, None])
    assert clean == []
    assert dropped == 3


def test_clamp_cap_at_10_and_overflow_counted():
    raw = [
        {"duration_minutes": i, "label": f"t{i}"} for i in range(1, 13)
    ]  # 12 entries
    clean, dropped = _clamp_timers(raw)
    assert len(clean) == _TIMER_MAX_PER_STEP  # kept the first 10
    assert clean[0]["duration_minutes"] == 1
    assert clean[-1]["duration_minutes"] == 10
    assert dropped == 2  # overflow


def test_clamp_ac5_twelve_with_two_bad_in_cap_and_two_overflow():
    """AC5: 12 entries including 2 out-of-range and 2 wrong-type.
    Keep 10 within the cap; of those 10 the 4 bad ones drop -> 6 kept.
    Plus 2 overflow drops. Total dropped == 4 + 2 == 6."""
    raw = [
        {"duration_minutes": 5, "label": "ok1"},
        {"duration_minutes": "bad", "label": "str dur"},  # wrong type
        {"duration_minutes": 10, "label": "ok2"},
        {"duration_minutes": 400, "label": "too long"},  # out of range
        {"duration_minutes": 15, "label": "ok3"},
        {"duration_minutes": True, "label": "bool"},  # wrong type
        {"duration_minutes": 20, "label": "ok4"},
        {"duration_minutes": 0, "label": "too short"},  # out of range
        {"duration_minutes": 25, "label": "ok5"},
        {"duration_minutes": 30, "label": "ok6"},
        {"duration_minutes": 35, "label": "overflow1"},
        {"duration_minutes": 40, "label": "overflow2"},
    ]
    clean, dropped = _clamp_timers(raw)
    assert len(clean) == 6
    assert dropped == 6  # 4 within the cap + 2 overflow


# ---------------------------------------------------------------------
# _log_timer_clamp — independent-commit contract
# ---------------------------------------------------------------------


def test_log_timer_clamp_writes_error_log_row():
    db = MagicMock()
    _log_timer_clamp(
        db,
        recipe_name="R",
        step_order=2,
        dropped_count=3,
        raw_input=[{"duration_minutes": 999}],
    )
    db.add.assert_called_once()
    # The ErrorLog row has service/error_type/error_message populated.
    (entry,) = db.add.call_args.args
    assert entry.service == "worker"
    assert entry.error_type == "TimerClamp"
    assert "dropped=3" in entry.error_message
    db.commit.assert_called_once()


def test_log_timer_clamp_suppresses_commit_errors():
    """AC7: audit write is best-effort — it must NOT raise even when
    the DB commit blows up. Otherwise the main transaction would get
    surprise-aborted."""
    db = MagicMock()
    db.commit.side_effect = RuntimeError("db gone")
    # No exception escapes.
    _log_timer_clamp(
        db,
        recipe_name="R",
        step_order=1,
        dropped_count=1,
        raw_input=None,
    )


# ---------------------------------------------------------------------
# Integration: create_recipe_task.execute persists timers
# ---------------------------------------------------------------------


def test_create_recipe_task_passes_timers_to_recipe_step():
    """AC4: clean timer list flows onto RecipeStep(timers=...)."""
    import uuid
    from types import SimpleNamespace

    from utils.tasks.import_tasks.create_recipe_task import CreateRecipeTask

    task = CreateRecipeTask()
    database = MagicMock()

    recipe_row_holder: dict = {}
    step_rows: list = []

    def create(obj):
        # Recipe or RecipeStep
        if obj.__class__.__name__ == "Recipe":
            obj.id = uuid.uuid4()
            recipe_row_holder["recipe"] = obj
        elif obj.__class__.__name__ == "RecipeStep":
            step_rows.append(obj)
        return obj

    database.create.side_effect = create

    def refresh(obj):
        return obj

    database.refresh = refresh

    job = SimpleNamespace(
        id=uuid.uuid4(),
        recipe_book_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        total_items=1,
        processed_items=0,
        failed_items=0,
        succeeded_items=0,
        pending_review_items=0,
        status="processing",
        total_ai_cost_cents=0,
    )

    item = SimpleNamespace(
        id=uuid.uuid4(),
        import_job_id=job.id,
        status="approved",
        user_edits=None,
        parsed_recipe={
            "name": "Pasta",
            "ingredients": [],
            "steps": [
                {
                    "order": 1,
                    "instruction": "Simmer",
                    "timers": [{"duration_minutes": 15, "label": "simmer"}],
                }
            ],
        },
        raw_data={},
        source_url=None,
        created_recipe_id=None,
        error_message=None,
        error_code=None,
    )

    def find_by(model, **_):
        from utils.models.import_item import ImportItem as _II
        from utils.models.import_job import ImportJob as _IJ
        if model is _II:
            return item
        if model is _IJ:
            return job
        return None

    database.find_by.side_effect = find_by
    database.db = MagicMock()
    database.db.commit = MagicMock()
    database.db.query.return_value.filter.return_value.group_by.return_value.all.return_value = [
        ("completed", 1)
    ]

    task.database = database

    with patch.object(task, "_maybe_promote_source_photo"):
        task.execute(str(item.id))

    assert item.status == "completed"
    assert len(step_rows) == 1
    assert step_rows[0].timers == [{"duration_minutes": 15, "label": "simmer"}]
    assert step_rows[0].instruction == "Simmer"


def test_create_recipe_task_all_invalid_timers_empty_and_audit():
    """AC6: all-invalid timers -> persisted [] + single audit row;
    item still completes."""
    import uuid
    from types import SimpleNamespace

    from utils.tasks.import_tasks.create_recipe_task import CreateRecipeTask

    task = CreateRecipeTask()
    database = MagicMock()

    step_rows: list = []
    audit_rows: list = []

    def create(obj):
        if obj.__class__.__name__ == "Recipe":
            obj.id = uuid.uuid4()
        elif obj.__class__.__name__ == "RecipeStep":
            step_rows.append(obj)
        return obj

    database.create.side_effect = create

    def add(obj):
        if obj.__class__.__name__ == "ErrorLog":
            audit_rows.append(obj)

    database.db = MagicMock()
    database.db.add = add
    database.db.commit = MagicMock()
    database.db.query.return_value.filter.return_value.group_by.return_value.all.return_value = [
        ("completed", 1)
    ]

    def refresh(obj):
        return obj

    database.refresh = refresh

    job = SimpleNamespace(
        id=uuid.uuid4(),
        recipe_book_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        total_items=1,
        processed_items=0,
        failed_items=0,
        succeeded_items=0,
        pending_review_items=0,
        status="processing",
        total_ai_cost_cents=0,
    )

    item = SimpleNamespace(
        id=uuid.uuid4(),
        import_job_id=job.id,
        status="approved",
        user_edits=None,
        parsed_recipe={
            "name": "R",
            "ingredients": [],
            "steps": [
                {
                    "order": 1,
                    "instruction": "Step 1",
                    "timers": [
                        {"duration_minutes": "bad"},
                        {"duration_minutes": 500},
                        "not a dict",
                    ],
                }
            ],
        },
        raw_data={},
        source_url=None,
        created_recipe_id=None,
        error_message=None,
        error_code=None,
    )

    def find_by(model, **_):
        from utils.models.import_item import ImportItem as _II
        from utils.models.import_job import ImportJob as _IJ
        if model is _II:
            return item
        if model is _IJ:
            return job
        return None

    database.find_by.side_effect = find_by
    task.database = database

    with patch.object(task, "_maybe_promote_source_photo"):
        task.execute(str(item.id))

    assert item.status == "completed"
    assert len(step_rows) == 1
    assert step_rows[0].timers == []
    assert len(audit_rows) == 1
    assert audit_rows[0].error_type == "TimerClamp"

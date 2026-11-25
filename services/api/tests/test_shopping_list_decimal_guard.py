"""Guard: no cart RESPONSE model may declare a bare `Decimal` field.

The contract tests in test_shopping_list_json_contract.py pin the ten cart
endpoints that exist today. This guard covers the next one: any response model
added under `api/v1/shopping_list/` (or the two meal routes that write to a
cart) with a bare `Decimal` fails here, at the moment it is written, rather
than in a user's app months later.

It is an AST check on field TYPES, deliberately narrow:
  - only classes whose name contains "Response" — a `Decimal` in a REQUEST
    model is fine, Pydantic parses a JSON number into it;
  - only the cart — NOT all of api/v1. Recipe endpoints return bare
    `Decimal`s on purpose: the recipe screen reads them with `as String?`,
    so forcing JsonDecimal there would break recipes the way the cart broke.
    Each client has its own wire contract; this guard encodes the cart's.

Use `schemas.json_types.JsonDecimal` instead.
"""

import ast
import pathlib

API_V1 = pathlib.Path(__file__).resolve().parents[1] / "src" / "api" / "v1"
CART_FILES = sorted(
    [
        *(API_V1 / "shopping_list").rglob("*.py"),
        API_V1 / "meal" / "add_meal_to_shopping_list.py",
        API_V1 / "meal_event" / "add_to_shopping_list.py",
    ]
)


def bare_decimal_response_fields(source: str) -> list[str]:
    """`Class.field` for every bare `Decimal` annotation inside a *Response* class."""
    hits = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ClassDef) and "Response" in node.name:
            for stmt in node.body:
                if isinstance(stmt, ast.AnnAssign):
                    names = {n.id for n in ast.walk(stmt.annotation) if isinstance(n, ast.Name)}
                    if "Decimal" in names:
                        hits.append(f"{node.name}.{stmt.target.id}")
    return hits


def test_the_guard_can_fail():
    """A guard that cannot fail reports clean forever. Pin it against the exact
    shape that caused the outage, and against the fix."""
    broken = "class ItemResponse(BaseModel):\n    quantity: Decimal | None = None\n"
    fixed = "class ItemResponse(BaseModel):\n    quantity: JsonDecimal | None = None\n"
    request_model = "class Params(BaseModel):\n    quantity: Decimal | None = None\n"
    assert bare_decimal_response_fields(broken) == ["ItemResponse.quantity"]
    assert bare_decimal_response_fields(fixed) == []
    assert bare_decimal_response_fields(request_model) == []


def test_the_guard_covers_every_cart_endpoint():
    # Not vacuous: it must actually be looking at the ten endpoints.
    names = {p.name for p in CART_FILES}
    for expected in (
        "get_shopping_list.py", "add_item.py", "update_item.py", "create_shopping_list.py",
        "update_shopping_list.py", "get_deadlines.py", "populate_from_recipe.py",
        "generate_from_meal_event.py", "add_meal_to_shopping_list.py", "add_to_shopping_list.py",
    ):
        assert expected in names, f"guard is not scanning {expected}"


def test_no_cart_response_model_declares_a_bare_decimal():
    offenders = {
        str(p.relative_to(API_V1)): bare_decimal_response_fields(p.read_text())
        for p in CART_FILES
    }
    offenders = {k: v for k, v in offenders.items() if v}
    assert not offenders, (
        "Cart response models must use schemas.json_types.JsonDecimal, not Decimal — "
        "Pydantic v2 serializes Decimal as a JSON string and the app's `as num?` "
        f"throws on it (the 2026-04..09 cart outage): {offenders}"
    )

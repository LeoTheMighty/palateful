"""Wire types for API response models.

`JsonDecimal` is a `Decimal` that serializes as a JSON **number** (in JSON mode
only — Python-side `model_dump()` still returns a real `Decimal`, so arithmetic
on it is unaffected).

Why it exists: Pydantic v2 renders a bare `Decimal` as a JSON *string*. The
shopping cart's Dart models read quantities with `json['quantity'] as num?`,
so every cart response that carried a quantity crashed the app's parser —
`_TypeError: type 'String' is not a subtype of type 'num?'` (area
shopping.cart, operation loadList) — while the server returned HTTP 200 and
logged nothing. The cart was unusable from at least 2026-04 to 2026-09.

A fix in May (a5c84386) put a serializer on `schemas/shopping_list.py::
ShoppingListItemResponse`, a class no endpoint used (the whole module was dead, and was deleted with this fix); every endpoint builds its
own local response model, so the fix changed nothing. Declaring the field TYPE
here, and using it in each response model, is what makes the fix land where
the response is actually built.

**This is a per-client contract, not an API-wide rule.** Recipe endpoints also
return bare `Decimal`s, and the recipe screen reads them with
`as String?` — switching those to `JsonDecimal` would break recipes exactly the
way the cart was broken. Use this type only where the consuming client parses
a number. `tests/test_shopping_list_json_contract.py` pins the cart's side of
that contract against the real endpoints' JSON.
"""

from decimal import Decimal
from typing import Annotated

from pydantic import PlainSerializer

JsonDecimal = Annotated[
    Decimal,
    PlainSerializer(float, return_type=float, when_used="json"),
]

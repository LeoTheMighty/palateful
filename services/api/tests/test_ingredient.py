"""Tests for ingredient endpoints."""

from conftest import MockExecuteResult, MockIngredient, MockQuery


class TestSearchIngredients:
    """Tests for GET /v1/ingredients/search."""

    def test_search_ingredients_success(self, client, mock_db):
        """Test searching for ingredients."""
        # Mock the raw SQL result
        class Row:
            def __init__(self):
                self.id = "ing-1"
                self.canonical_name = "flour"
                self.category = "baking"
                self.similarity = 0.95

        mock_db.db.execute.return_value = [Row()]

        response = client.get("/v1/ingredients/search?q=flour")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data

    def test_search_ingredients_no_results(self, client, mock_db):
        """Test searching with no matches."""
        mock_db.db.execute.return_value = []
        response = client.get("/v1/ingredients/search?q=zzzzz")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []


class TestGetIngredient:
    """Tests for GET /v1/ingredients/{id}."""

    def test_get_ingredient_success(self, client, mock_db):
        """Test getting an ingredient by ID."""
        ing_id = "test-ingredient-id"
        ingredient = MockIngredient(id=ing_id, canonical_name="flour")

        from utils.models.ingredient import Ingredient

        mock_db.set_find_by(Ingredient, ingredient, id=ing_id)

        response = client.get(f"/v1/ingredients/{ing_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == ing_id
        assert data["canonical_name"] == "flour"

    def test_get_ingredient_not_found(self, client, mock_db):
        """Test getting a nonexistent ingredient."""
        response = client.get("/v1/ingredients/nonexistent")
        assert response.status_code == 404


class TestCreateIngredient:
    """Tests for POST /v1/ingredients."""

    def test_create_ingredient_success(self, client, mock_db, mock_user):
        """Test creating a new ingredient."""
        response = client.post(
            "/v1/ingredients",
            json={
                "canonical_name": "cardamom",
                "category": "spice",
                "default_unit": "tsp",
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert data["canonical_name"] == "cardamom"
        assert data["pending_review"] is True

    def test_create_ingredient_duplicate(self, client, mock_db, mock_user):
        """Test creating a duplicate ingredient fails."""
        existing = MockIngredient(canonical_name="flour")

        from utils.models.ingredient import Ingredient

        mock_db.set_find_by(Ingredient, existing, canonical_name="flour")

        response = client.post(
            "/v1/ingredients",
            json={"canonical_name": "flour"}
        )
        assert response.status_code == 400

    def test_create_ingredient_minimal(self, client, mock_db, mock_user):
        """Test creating an ingredient with only required fields."""
        response = client.post(
            "/v1/ingredients",
            json={"canonical_name": "newspice"}
        )
        assert response.status_code == 201

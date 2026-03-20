"""Tests for recipe book member management endpoints and RBAC."""

import uuid

from conftest import (
    MockQuery,
    MockRecipeBook,
    MockRecipeBookUser,
    MockUser,
)

from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User


BOOK_ID = "10000000-0000-0000-0000-000000000001"
TARGET_USER_ID = "a0000000-0000-0000-0000-000000000002"


# ---------------------------------------------------------------------------
# POST /v1/recipe-books/{id}/members
# ---------------------------------------------------------------------------

class TestAddRecipeBookMember:
    """Tests for POST /v1/recipe-books/{book_id}/members."""

    def test_owner_can_add_editor(self, client, mock_db, mock_user):
        """Owner successfully adds an editor."""
        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.user import User

        target_user = MockUser(id=TARGET_USER_ID, name="Jane Smith")
        owner_membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=BOOK_ID,
            role="owner",
        )
        mock_db.set_find_by(RecipeBookUser, owner_membership,
                            user_id=str(mock_user.id), recipe_book_id=BOOK_ID)
        mock_db.set_find_by(User, target_user, id=TARGET_USER_ID)
        # No existing membership (default None)

        response = client.post(
            f"/v1/recipe-books/{BOOK_ID}/members",
            json={"user_id": TARGET_USER_ID, "role": "editor"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "editor"
        assert data["user_id"] == TARGET_USER_ID

    def test_owner_can_add_viewer(self, client, mock_db, mock_user):
        """Owner successfully adds a viewer."""
        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.user import User

        target_user = MockUser(id=TARGET_USER_ID, name="Bob")
        owner_membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=BOOK_ID,
            role="owner",
        )
        mock_db.set_find_by(RecipeBookUser, owner_membership,
                            user_id=str(mock_user.id), recipe_book_id=BOOK_ID)
        mock_db.set_find_by(User, target_user, id=TARGET_USER_ID)

        response = client.post(
            f"/v1/recipe-books/{BOOK_ID}/members",
            json={"user_id": TARGET_USER_ID, "role": "viewer"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "viewer"

    def test_editor_cannot_add_member(self, client, mock_db, mock_user):
        """Editor is denied adding a member (403)."""
        from utils.models.recipe_book_user import RecipeBookUser

        editor_membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=BOOK_ID,
            role="editor",
        )
        mock_db.set_find_by(RecipeBookUser, editor_membership,
                            user_id=str(mock_user.id), recipe_book_id=BOOK_ID)

        response = client.post(
            f"/v1/recipe-books/{BOOK_ID}/members",
            json={"user_id": TARGET_USER_ID, "role": "editor"},
        )

        assert response.status_code == 403

    def test_viewer_cannot_add_member(self, client, mock_db, mock_user):
        """Viewer is denied adding a member (403)."""
        from utils.models.recipe_book_user import RecipeBookUser

        viewer_membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=BOOK_ID,
            role="viewer",
        )
        mock_db.set_find_by(RecipeBookUser, viewer_membership,
                            user_id=str(mock_user.id), recipe_book_id=BOOK_ID)

        response = client.post(
            f"/v1/recipe-books/{BOOK_ID}/members",
            json={"user_id": TARGET_USER_ID, "role": "viewer"},
        )

        assert response.status_code == 403

    def test_invalid_role_rejected(self, client, mock_db, mock_user):
        """Role 'owner' is rejected with 422."""
        from utils.models.recipe_book_user import RecipeBookUser

        owner_membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=BOOK_ID,
            role="owner",
        )
        mock_db.set_find_by(RecipeBookUser, owner_membership,
                            user_id=str(mock_user.id), recipe_book_id=BOOK_ID)

        response = client.post(
            f"/v1/recipe-books/{BOOK_ID}/members",
            json={"user_id": TARGET_USER_ID, "role": "owner"},
        )

        assert response.status_code == 422

    def test_no_access_returns_403(self, client, mock_db, mock_user):
        """No membership at all returns 403."""
        response = client.post(
            f"/v1/recipe-books/{BOOK_ID}/members",
            json={"user_id": TARGET_USER_ID, "role": "editor"},
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# DELETE /v1/recipe-books/{id}/members/{target_user_id}
# ---------------------------------------------------------------------------

class TestRemoveRecipeBookMember:
    """Tests for DELETE /v1/recipe-books/{book_id}/members/{user_id}."""

    def test_owner_can_remove_member(self, client, mock_db, mock_user):
        """Owner successfully removes another member."""
        from utils.models.recipe_book_user import RecipeBookUser

        owner_membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=BOOK_ID,
            role="owner",
        )
        target_membership = MockRecipeBookUser(
            user_id=TARGET_USER_ID,
            recipe_book_id=BOOK_ID,
            role="editor",
        )
        mock_db.set_find_by(RecipeBookUser, owner_membership,
                            user_id=str(mock_user.id), recipe_book_id=BOOK_ID)
        mock_db.set_find_by(RecipeBookUser, target_membership,
                            user_id=TARGET_USER_ID, recipe_book_id=BOOK_ID)

        response = client.delete(f"/v1/recipe-books/{BOOK_ID}/members/{TARGET_USER_ID}")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_editor_cannot_remove_member(self, client, mock_db, mock_user):
        """Editor is denied removing a member (403)."""
        from utils.models.recipe_book_user import RecipeBookUser

        editor_membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=BOOK_ID,
            role="editor",
        )
        mock_db.set_find_by(RecipeBookUser, editor_membership,
                            user_id=str(mock_user.id), recipe_book_id=BOOK_ID)

        response = client.delete(f"/v1/recipe-books/{BOOK_ID}/members/{TARGET_USER_ID}")

        assert response.status_code == 403

    def test_owner_cannot_remove_self(self, client, mock_db, mock_user):
        """Owner cannot remove themselves (400)."""
        from utils.models.recipe_book_user import RecipeBookUser

        owner_membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=BOOK_ID,
            role="owner",
        )
        mock_db.set_find_by(RecipeBookUser, owner_membership,
                            user_id=str(mock_user.id), recipe_book_id=BOOK_ID)

        response = client.delete(
            f"/v1/recipe-books/{BOOK_ID}/members/{mock_user.id}"
        )

        assert response.status_code == 400


# ---------------------------------------------------------------------------
# PATCH /v1/recipe-books/{id}/members/{target_user_id}
# ---------------------------------------------------------------------------

class TestUpdateRecipeBookMemberRole:
    """Tests for PATCH /v1/recipe-books/{book_id}/members/{user_id}."""

    def test_owner_can_update_role(self, client, mock_db, mock_user):
        """Owner successfully updates a member's role."""
        from utils.models.recipe_book_user import RecipeBookUser

        owner_membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=BOOK_ID,
            role="owner",
        )
        target_membership = MockRecipeBookUser(
            user_id=TARGET_USER_ID,
            recipe_book_id=BOOK_ID,
            role="editor",
        )
        mock_db.set_find_by(RecipeBookUser, owner_membership,
                            user_id=str(mock_user.id), recipe_book_id=BOOK_ID)
        mock_db.set_find_by(RecipeBookUser, target_membership,
                            user_id=TARGET_USER_ID, recipe_book_id=BOOK_ID)

        response = client.patch(
            f"/v1/recipe-books/{BOOK_ID}/members/{TARGET_USER_ID}",
            json={"role": "viewer"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "viewer"

    def test_editor_cannot_update_role(self, client, mock_db, mock_user):
        """Editor is denied updating a role (403)."""
        from utils.models.recipe_book_user import RecipeBookUser

        editor_membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=BOOK_ID,
            role="editor",
        )
        mock_db.set_find_by(RecipeBookUser, editor_membership,
                            user_id=str(mock_user.id), recipe_book_id=BOOK_ID)

        response = client.patch(
            f"/v1/recipe-books/{BOOK_ID}/members/{TARGET_USER_ID}",
            json={"role": "viewer"},
        )

        assert response.status_code == 403

    def test_invalid_role_rejected(self, client, mock_db, mock_user):
        """Role 'owner' in PATCH is rejected with 422."""
        from utils.models.recipe_book_user import RecipeBookUser

        owner_membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=BOOK_ID,
            role="owner",
        )
        mock_db.set_find_by(RecipeBookUser, owner_membership,
                            user_id=str(mock_user.id), recipe_book_id=BOOK_ID)

        response = client.patch(
            f"/v1/recipe-books/{BOOK_ID}/members/{TARGET_USER_ID}",
            json={"role": "owner"},
        )

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /v1/recipe-books — list includes user_role and is_shared
# ---------------------------------------------------------------------------

class TestListRecipeBooksRoleInfo:
    """Tests that GET /v1/recipe-books returns user_role and is_shared."""

    def test_list_includes_user_role_and_is_shared(self, client, mock_db, mock_user):
        """GET /v1/recipe-books returns items with user_role and is_shared fields."""
        mock_db.db.query.return_value = MockQuery([])

        response = client.get("/v1/recipe-books")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["items"] == []

    def test_list_with_shared_book(self, client, mock_db, mock_user):
        """GET /v1/recipe-books with a shared book returns is_shared=True and user_role."""
        book = MockRecipeBook(name="Shared Book", is_shared=True)
        # 4-tuple: (RecipeBook, recipe_count, user_role, member_count)
        mock_db.db.query.return_value = MockQuery([(book, 2, "editor", 3)])

        response = client.get("/v1/recipe-books")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["is_shared"] is True
        assert data["items"][0]["user_role"] == "editor"
        assert data["items"][0]["member_count"] == 3


# ---------------------------------------------------------------------------
# GET /v1/recipe-books/{id} — get includes user_role and members
# ---------------------------------------------------------------------------

class TestGetRecipeBookRoleInfo:
    """Tests that GET /v1/recipe-books/{id} returns user_role and members."""

    def test_get_includes_user_role_and_members(self, client, mock_db, mock_user):
        """GET /v1/recipe-books/{id} returns user_role and members list."""
        from utils.models.recipe_book import RecipeBook
        from utils.models.recipe_book_user import RecipeBookUser

        book = MockRecipeBook(id=BOOK_ID)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=BOOK_ID,
            role="owner",
        )
        mock_db.set_find_by(RecipeBookUser, membership,
                            user_id=str(mock_user.id), recipe_book_id=BOOK_ID)
        mock_db.set_find_by(RecipeBook, book, id=BOOK_ID)
        # Two db.query calls: recipes then members — both return empty
        mock_db.db.query.side_effect = [MockQuery([]), MockQuery([])]

        response = client.get(f"/v1/recipe-books/{BOOK_ID}")

        assert response.status_code == 200
        data = response.json()
        assert "user_role" in data
        assert data["user_role"] == "owner"
        assert "members" in data
        assert isinstance(data["members"], list)
        assert "is_shared" in data

    def test_get_no_access_returns_403(self, client, mock_db, mock_user):
        """GET /v1/recipe-books/{id} with no membership returns 403."""
        response = client.get(f"/v1/recipe-books/{BOOK_ID}")
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Missing branch coverage for add_recipe_book_member.py
# ---------------------------------------------------------------------------

class TestAddRecipeBookMemberMissingBranches:
    """Tests for missing branches in add_recipe_book_member.py."""

    def test_add_member_user_not_found(self, client, mock_db, mock_user):
        """Test adding a nonexistent user returns 404 (line 31-36)."""
        owner_membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=BOOK_ID,
            role="owner",
        )
        mock_db.set_find_by(RecipeBookUser, owner_membership,
                            user_id=str(mock_user.id), recipe_book_id=BOOK_ID)
        # User not found -> find_by returns None -> 404

        response = client.post(
            f"/v1/recipe-books/{BOOK_ID}/members",
            json={"user_id": TARGET_USER_ID, "role": "editor"},
        )
        assert response.status_code == 404

    def test_add_member_already_exists(self, client, mock_db, mock_user):
        """Test adding a user who is already a member returns 409 (line 44-49)."""
        target_user = MockUser(id=TARGET_USER_ID, name="Jane")
        owner_membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=BOOK_ID,
            role="owner",
        )
        existing_membership = MockRecipeBookUser(
            user_id=TARGET_USER_ID,
            recipe_book_id=BOOK_ID,
            role="viewer",
        )
        mock_db.set_find_by(RecipeBookUser, owner_membership,
                            user_id=str(mock_user.id), recipe_book_id=BOOK_ID)
        mock_db.set_find_by(User, target_user, id=TARGET_USER_ID)
        mock_db.set_find_by(RecipeBookUser, existing_membership,
                            user_id=TARGET_USER_ID, recipe_book_id=BOOK_ID)

        response = client.post(
            f"/v1/recipe-books/{BOOK_ID}/members",
            json={"user_id": TARGET_USER_ID, "role": "editor"},
        )
        assert response.status_code == 409


# ---------------------------------------------------------------------------
# Missing branch coverage for remove_recipe_book_member.py
# ---------------------------------------------------------------------------

class TestRemoveRecipeBookMemberMissingBranches:
    """Tests for missing branches in remove_recipe_book_member.py."""

    def test_remove_member_not_found(self, client, mock_db, mock_user):
        """Test removing a nonexistent member returns 404 (line 43-48)."""
        owner_membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=BOOK_ID,
            role="owner",
        )
        mock_db.set_find_by(RecipeBookUser, owner_membership,
                            user_id=str(mock_user.id), recipe_book_id=BOOK_ID)
        # Target membership not configured -> find_by returns None -> 404

        response = client.delete(f"/v1/recipe-books/{BOOK_ID}/members/{TARGET_USER_ID}")
        assert response.status_code == 404

    def test_remove_member_no_access(self, client, mock_db, mock_user):
        """Test removing without any membership returns 403."""
        response = client.delete(f"/v1/recipe-books/{BOOK_ID}/members/{TARGET_USER_ID}")
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Missing branch coverage for update_recipe_book_member_role.py
# ---------------------------------------------------------------------------

class TestUpdateRecipeBookMemberRoleMissingBranches:
    """Tests for missing branches in update_recipe_book_member_role.py."""

    def test_owner_cannot_change_own_role(self, client, mock_db, mock_user):
        """Test that owner cannot change their own role (line 35-40)."""
        owner_membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=BOOK_ID,
            role="owner",
        )
        mock_db.set_find_by(RecipeBookUser, owner_membership,
                            user_id=str(mock_user.id), recipe_book_id=BOOK_ID)

        response = client.patch(
            f"/v1/recipe-books/{BOOK_ID}/members/{mock_user.id}",
            json={"role": "editor"},
        )
        assert response.status_code == 400

    def test_update_role_member_not_found(self, client, mock_db, mock_user):
        """Test updating role for a nonexistent member returns 404 (line 48-53)."""
        owner_membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=BOOK_ID,
            role="owner",
        )
        mock_db.set_find_by(RecipeBookUser, owner_membership,
                            user_id=str(mock_user.id), recipe_book_id=BOOK_ID)
        # Target membership not configured -> find_by returns None -> 404

        response = client.patch(
            f"/v1/recipe-books/{BOOK_ID}/members/{TARGET_USER_ID}",
            json={"role": "viewer"},
        )
        assert response.status_code == 404

    def test_update_role_no_access(self, client, mock_db, mock_user):
        """Test updating role without any membership returns 403."""
        response = client.patch(
            f"/v1/recipe-books/{BOOK_ID}/members/{TARGET_USER_ID}",
            json={"role": "viewer"},
        )
        assert response.status_code == 403

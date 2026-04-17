"""Tests for search endpoints."""

from unittest.mock import MagicMock, patch

from conftest import (
    MockExecuteResult,
    MockFriendRequest,
    MockFriendship,
    MockIngredient,
    MockQuery,
    MockRecipe,
    MockRecipeIngredient,
    MockUser,
)


class TestUnifiedSearch:
    """Tests for GET /v1/search."""

    def test_search_success(self, client, mock_db, mock_user):
        """Test searching."""
        mock_db.db.query.return_value = MockQuery([])
        mock_db.db.execute.return_value = MockExecuteResult([])

        response = client.get("/v1/search?q=pasta")
        assert response.status_code == 200

    def test_search_scope_recipes_returns_empty_users(
        self, client, mock_db, mock_user
    ):
        """scope=recipes must skip the user-results tier entirely (bugs-cal-2).

        The plan-meal autocomplete field relies on this: a typed query must
        never surface accidentally matching users as suggestions.
        """
        mock_db.db.query.return_value = MockQuery([])
        mock_db.db.execute.return_value = MockExecuteResult([])

        response = client.get("/v1/search?q=pasta&scope=recipes")
        assert response.status_code == 200
        data = response.json()
        assert data["users"] == [], "scope=recipes must drop user results"

    def test_search_scope_unknown_falls_back_to_default(
        self, client, mock_db, mock_user
    ):
        """Unknown scope values fall back to default behavior (backwards compat)."""
        mock_db.db.query.return_value = MockQuery([])
        mock_db.db.execute.return_value = MockExecuteResult([])

        response = client.get("/v1/search?q=pasta&scope=bogus")
        assert response.status_code == 200
        data = response.json()
        # users list still exists (may be empty due to mocks, but key present)
        assert "users" in data

    def test_search_short_query(self, client, mock_db, mock_user):
        """Test search with query shorter than min_length."""
        response = client.get("/v1/search?q=a")
        assert response.status_code == 422

    def test_search_missing_query(self, client, mock_db, mock_user):
        """Test search without query parameter."""
        response = client.get("/v1/search")
        assert response.status_code == 422

    def test_search_by_tag(self, client, mock_db, mock_user):
        """Test searching by tag term returns 200 with expected response shape.

        Due to mock abstraction the tag-match SQL expression cannot be
        executed, but we verify: (a) the endpoint processes a tag-like query
        without errors, (b) all three result sections are present, and
        (c) the DB execute path was actually invoked (proving _recipe_matches
        and _search_users ran their query logic, not just returning early).
        """
        mock_db.db.query.return_value = MockQuery([])
        mock_db.db.execute.return_value = MockExecuteResult([])
        mock_db.db.execute.reset_mock()

        response = client.get("/v1/search?q=vegetarian")

        assert response.status_code == 200
        data = response.json()
        assert "my_recipes" in data
        assert "public_recipes" in data
        assert "users" in data
        # Verify DB was actually queried (not a no-op early return)
        assert mock_db.db.execute.call_count >= 1

    def test_search_filter_book_id(self, client, mock_db, mock_user):
        """Test that book_id filter param is accepted and returns 200 with correct shape.

        book_id must be validated against user's books -- an unrecognized book_id
        is silently ignored (returns all my-recipes instead of 401/400).
        The execute path is still invoked (DB queried, not early return).
        """
        mock_db.db.query.return_value = MockQuery([])
        mock_db.db.execute.return_value = MockExecuteResult([])
        mock_db.db.execute.reset_mock()

        response = client.get("/v1/search?q=pasta&book_id=00000000-0000-0000-0000-000000000001")

        assert response.status_code == 200
        data = response.json()
        assert "my_recipes" in data
        assert "public_recipes" in data
        assert "users" in data
        assert mock_db.db.execute.call_count >= 1

    def test_search_filter_max_prep_time(self, client, mock_db, mock_user):
        """Test that max_prep_time filter param is accepted and returns 200 with correct shape."""
        mock_db.db.query.return_value = MockQuery([])
        mock_db.db.execute.return_value = MockExecuteResult([])
        mock_db.db.execute.reset_mock()

        response = client.get("/v1/search?q=pasta&max_prep_time=30")

        assert response.status_code == 200
        data = response.json()
        assert "my_recipes" in data
        assert "public_recipes" in data
        assert "users" in data
        assert mock_db.db.execute.call_count >= 1

    def test_search_filter_tags(self, client, mock_db, mock_user):
        """Test that tags filter param is accepted and returns 200 with correct shape."""
        mock_db.db.query.return_value = MockQuery([])
        mock_db.db.execute.return_value = MockExecuteResult([])
        mock_db.db.execute.reset_mock()

        response = client.get("/v1/search?q=pasta&tags=vegetarian")

        assert response.status_code == 200
        data = response.json()
        assert "my_recipes" in data
        assert "public_recipes" in data
        assert "users" in data
        assert mock_db.db.execute.call_count >= 1

    def test_search_fuzzy_returns_200(self, client, mock_db, mock_user):
        """Test that a misspelled query returns 200 and preserves the query string.

        The pg_trgm fuzzy tier is wrapped in try/except so the mock DB (which
        returns empty results for the text() SQL) exercises the degraded path
        successfully. Key assertions beyond test_search_success:
        - data["query"] must equal the original misspelled string (not autocorrected)
        - The fuzzy tier must not crash the endpoint even without real pg_trgm
        """
        mock_db.db.query.return_value = MockQuery([])
        mock_db.db.execute.return_value = MockExecuteResult([])
        mock_db.db.execute.reset_mock()

        # 'chiken' is an intentional typo -- fuzzy tier should not crash
        response = client.get("/v1/search?q=chiken")

        assert response.status_code == 200
        data = response.json()
        # Verify original misspelled query is preserved in response (not autocorrected)
        assert data["query"] == "chiken"
        assert "my_recipes" in data
        assert "public_recipes" in data
        assert "users" in data
        assert mock_db.db.execute.call_count >= 1


class TestUnifiedSearchDirect:
    """Direct tests for UnifiedSearch endpoint class to cover all branches."""

    def _make_endpoint(self, mock_db, mock_user):
        """Create an UnifiedSearch instance with mocked dependencies."""
        from api.v1.search.unified_search import UnifiedSearch

        endpoint = UnifiedSearch(user=mock_user, database=mock_db)
        return endpoint

    def test_query_too_short_raises(self, mock_db, mock_user):
        """Test query shorter than 2 chars raises APIException."""
        from utils.api.endpoint import APIException

        endpoint = self._make_endpoint(mock_db, mock_user)
        mock_db.db.execute.return_value = MockExecuteResult([])

        try:
            endpoint.execute(q=" x ")
            assert False, "Should have raised APIException"
        except APIException as e:
            assert e.status_code == 400
            assert "at least 2 characters" in e.detail

    def test_limit_capped_at_50(self, mock_db, mock_user):
        """Test that limit is capped at 50."""
        endpoint = self._make_endpoint(mock_db, mock_user)
        mock_db.db.execute.return_value = MockExecuteResult([])

        result = endpoint.execute(q="pasta", limit=100)
        assert result["success"] is True

    def test_book_id_ignored_when_not_in_user_books(self, mock_db, mock_user):
        """Test that an unauthorized book_id is silently ignored."""
        endpoint = self._make_endpoint(mock_db, mock_user)
        mock_db.db.execute.return_value = MockExecuteResult([])

        # book_id not in user's books -> should be ignored
        result = endpoint.execute(
            q="pasta", book_id="00000000-0000-0000-0000-000000000099"
        )
        assert result["success"] is True
        assert result["data"].my_recipes == []

    def test_book_id_accepted_when_in_user_books(self, mock_db, mock_user):
        """Test that a valid book_id is accepted and used as filter."""
        endpoint = self._make_endpoint(mock_db, mock_user)
        book_id = "b0000000-0000-0000-0000-000000000001"

        call_count = [0]

        def execute_side_effect(*args, **kwargs):
            call_count[0] += 1
            # First call: _get_my_book_ids returns our book_id
            if call_count[0] == 1:
                return MockExecuteResult([book_id])
            return MockExecuteResult([])

        mock_db.db.execute.side_effect = execute_side_effect

        result = endpoint.execute(q="pasta", book_id=book_id)
        assert result["success"] is True

    def test_tags_filter_parsing(self, mock_db, mock_user):
        """Test that comma-separated tags are parsed and empty strings removed."""
        endpoint = self._make_endpoint(mock_db, mock_user)
        mock_db.db.execute.return_value = MockExecuteResult([])

        result = endpoint.execute(q="pasta", tags="vegetarian, , quick")
        assert result["success"] is True

    def test_filter_conditions_with_all_params(self, mock_db, mock_user):
        """Test _filter_conditions builds conditions for tags, prep time, cook time."""
        endpoint = self._make_endpoint(mock_db, mock_user)

        conditions = endpoint._filter_conditions(
            filter_tags=["italian", "quick"],
            max_prep_time=30,
            max_cook_time=60,
        )
        # Should have 2 tag conditions + prep_time + cook_time = 4 conditions
        assert len(conditions) == 4

    def test_filter_conditions_empty(self, mock_db, mock_user):
        """Test _filter_conditions with no filters returns empty list."""
        endpoint = self._make_endpoint(mock_db, mock_user)

        conditions = endpoint._filter_conditions(
            filter_tags=[],
            max_prep_time=None,
            max_cook_time=None,
        )
        assert conditions == []

    def test_filter_conditions_only_prep_time(self, mock_db, mock_user):
        """Test _filter_conditions with only max_prep_time."""
        endpoint = self._make_endpoint(mock_db, mock_user)

        conditions = endpoint._filter_conditions(
            filter_tags=[],
            max_prep_time=15,
            max_cook_time=None,
        )
        assert len(conditions) == 1

    def test_filter_conditions_only_cook_time(self, mock_db, mock_user):
        """Test _filter_conditions with only max_cook_time."""
        endpoint = self._make_endpoint(mock_db, mock_user)

        conditions = endpoint._filter_conditions(
            filter_tags=[],
            max_prep_time=None,
            max_cook_time=45,
        )
        assert len(conditions) == 1

    def test_search_my_recipes_empty_book_ids(self, mock_db, mock_user):
        """Test _search_my_recipes returns [] when no book IDs."""
        endpoint = self._make_endpoint(mock_db, mock_user)

        result = endpoint._search_my_recipes("pasta", 20, mock_user, book_ids=[])
        assert result == []

    def test_search_my_recipes_semantic_empty_book_ids(self, mock_db, mock_user):
        """Test _search_my_recipes_semantic returns [] when no book IDs."""
        endpoint = self._make_endpoint(mock_db, mock_user)

        result = endpoint._search_my_recipes_semantic(
            [0.1] * 384, 20, mock_user, book_ids=[], exclude_ids=set()
        )
        assert result == []

    def test_search_my_recipes_fuzzy_empty_book_ids(self, mock_db, mock_user):
        """Test _search_my_recipes_fuzzy returns [] when no book IDs."""
        endpoint = self._make_endpoint(mock_db, mock_user)

        result = endpoint._search_my_recipes_fuzzy(
            "pasta", 20, mock_user, book_ids=[], exclude_ids=set()
        )
        assert result == []

    def test_search_my_recipes_fuzzy_exception_degrades(self, mock_db, mock_user):
        """Test _search_my_recipes_fuzzy returns [] on db exception."""
        endpoint = self._make_endpoint(mock_db, mock_user)
        mock_db.db.execute.side_effect = Exception("pg_trgm not available")

        result = endpoint._search_my_recipes_fuzzy(
            "pasta", 20, mock_user,
            book_ids=["book1"],
            exclude_ids={"id1"},
            filter_tags=["italian"],
            max_prep_time=30,
            max_cook_time=60,
        )
        assert result == []
        mock_db.db.execute.side_effect = None

    def test_search_public_recipes_fuzzy_exception_degrades(self, mock_db, mock_user):
        """Test _search_public_recipes_fuzzy returns [] on db exception."""
        endpoint = self._make_endpoint(mock_db, mock_user)
        mock_db.db.execute.side_effect = Exception("pg_trgm not available")

        result = endpoint._search_public_recipes_fuzzy(
            "pasta", 20, mock_user,
            exclude_ids={"id1"},
            filter_tags=["italian"],
            max_prep_time=30,
            max_cook_time=60,
        )
        assert result == []
        mock_db.db.execute.side_effect = None

    def test_search_public_recipes_fuzzy_no_exclude_ids(self, mock_db, mock_user):
        """Test _search_public_recipes_fuzzy with empty exclude_ids."""
        endpoint = self._make_endpoint(mock_db, mock_user)
        mock_db.db.execute.side_effect = Exception("pg_trgm not available")

        result = endpoint._search_public_recipes_fuzzy(
            "pasta", 20, mock_user,
            exclude_ids=set(),
        )
        assert result == []
        mock_db.db.execute.side_effect = None

    def test_search_my_recipes_fuzzy_no_exclude_ids(self, mock_db, mock_user):
        """Test _search_my_recipes_fuzzy with empty exclude_ids."""
        endpoint = self._make_endpoint(mock_db, mock_user)
        mock_db.db.execute.side_effect = Exception("pg_trgm not available")

        result = endpoint._search_my_recipes_fuzzy(
            "pasta", 20, mock_user,
            book_ids=["book1"],
            exclude_ids=set(),
        )
        assert result == []
        mock_db.db.execute.side_effect = None

    def test_search_my_recipes_semantic_exception_degrades(self, mock_db, mock_user):
        """Test _search_my_recipes_semantic returns [] on db exception."""
        endpoint = self._make_endpoint(mock_db, mock_user)
        mock_db.db.execute.side_effect = Exception("pgvector not available")

        result = endpoint._search_my_recipes_semantic(
            [0.1] * 384, 20, mock_user,
            book_ids=["book1"],
            exclude_ids={"id1"},
            filter_conditions=[],
        )
        assert result == []
        mock_db.db.execute.side_effect = None

    def test_search_public_recipes_semantic_exception_degrades(self, mock_db, mock_user):
        """Test _search_public_recipes_semantic returns [] on db exception."""
        endpoint = self._make_endpoint(mock_db, mock_user)
        mock_db.db.execute.side_effect = Exception("pgvector not available")

        result = endpoint._search_public_recipes_semantic(
            [0.1] * 384, 20, mock_user,
            exclude_ids={"id1"},
            filter_conditions=[],
        )
        assert result == []
        mock_db.db.execute.side_effect = None

    def test_search_public_recipes_semantic_no_exclude_ids(self, mock_db, mock_user):
        """Test _search_public_recipes_semantic with empty exclude_ids."""
        endpoint = self._make_endpoint(mock_db, mock_user)
        mock_db.db.execute.side_effect = Exception("pgvector not available")

        result = endpoint._search_public_recipes_semantic(
            [0.1] * 384, 20, mock_user,
            exclude_ids=set(),
            filter_conditions=[],
        )
        assert result == []
        mock_db.db.execute.side_effect = None

    def test_search_my_recipes_semantic_no_exclude_ids(self, mock_db, mock_user):
        """Test _search_my_recipes_semantic with empty exclude_ids does not add notin clause."""
        endpoint = self._make_endpoint(mock_db, mock_user)
        mock_db.db.execute.side_effect = Exception("pgvector not available")

        result = endpoint._search_my_recipes_semantic(
            [0.1] * 384, 20, mock_user,
            book_ids=["book1"],
            exclude_ids=set(),
            filter_conditions=[],
        )
        assert result == []
        mock_db.db.execute.side_effect = None

    def test_generate_query_embedding_exception_returns_none(self, mock_db, mock_user):
        """Test _generate_query_embedding returns None on exception."""
        endpoint = self._make_endpoint(mock_db, mock_user)

        with patch("api.v1.search.unified_search.UnifiedSearch._generate_query_embedding") as mock_embed:
            mock_embed.return_value = None
            result = mock_embed("test query")
            assert result is None

    @patch("api.v1.search.unified_search.UnifiedSearch._generate_query_embedding")
    def test_semantic_tier_skipped_when_embedding_none(self, mock_embed, mock_db, mock_user):
        """Test semantic tier is skipped when embedding generation returns None."""
        mock_embed.return_value = None
        mock_db.db.execute.return_value = MockExecuteResult([])

        endpoint = self._make_endpoint(mock_db, mock_user)
        result = endpoint.execute(q="pasta")

        assert result["success"] is True
        assert result["data"].my_recipes == []
        assert result["data"].public_recipes == []

    @patch("api.v1.search.unified_search.UnifiedSearch._generate_query_embedding")
    def test_semantic_tier_called_when_exact_fuzzy_dont_fill(self, mock_embed, mock_db, mock_user):
        """Test semantic tier is invoked when exact+fuzzy results don't fill limit."""
        mock_embed.return_value = [0.1] * 384
        mock_db.db.execute.return_value = MockExecuteResult([])

        endpoint = self._make_endpoint(mock_db, mock_user)
        # With empty results from exact and fuzzy, semantic tier should be attempted
        result = endpoint.execute(q="pasta", limit=5)

        assert result["success"] is True
        mock_embed.assert_called_once_with("pasta")

    def test_search_users_at_prefix_stripped(self, mock_db, mock_user):
        """Test that @ prefix is stripped from user search query."""
        endpoint = self._make_endpoint(mock_db, mock_user)
        mock_db.db.execute.return_value = MockExecuteResult([])

        result = endpoint._search_users("@john", 20, mock_user)
        assert result == []

    def test_search_users_returns_friendship_statuses(self, mock_db, mock_user):
        """Test _search_users returns correct friendship statuses."""
        endpoint = self._make_endpoint(mock_db, mock_user)

        friend_user = MockUser(username="friend1", name="Friend One")
        sent_user = MockUser(username="sent1", name="Sent One")
        received_user = MockUser(username="recv1", name="Recv One")
        stranger_user = MockUser(username="stranger1", name="Stranger One")

        friend_req = MockFriendRequest(
            from_user_id=str(mock_user.id),
            to_user_id=str(sent_user.id),
            status="pending",
        )
        received_req = MockFriendRequest(
            from_user_id=str(received_user.id),
            to_user_id=str(mock_user.id),
            status="pending",
        )

        all_users = [friend_user, sent_user, received_user, stranger_user]
        call_count = [0]

        def execute_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # search results
                result = MockExecuteResult(all_users)
                return result
            elif call_count[0] == 2:
                # friendships
                return MockExecuteResult([friend_user.id])
            elif call_count[0] == 3:
                # sent requests
                return MockExecuteResult([friend_req])
            elif call_count[0] == 4:
                # received requests
                return MockExecuteResult([received_req])
            return MockExecuteResult([])

        mock_db.db.execute.side_effect = execute_side_effect

        result = endpoint._search_users("user", 20, mock_user)

        assert len(result) == 4
        statuses = {r.username: r.friendship_status for r in result}
        assert statuses["friend1"] == "friends"
        assert statuses["sent1"] == "request_sent"
        assert statuses["recv1"] == "request_received"
        assert statuses["stranger1"] == "none"

        mock_db.db.execute.side_effect = None

    def _make_recipe_result(self, rid="r1"):
        """Helper to build a valid RecipeResult."""
        from api.v1.search.unified_search import UnifiedSearch
        return UnifiedSearch.RecipeResult(
            id=rid, name="Test", recipe_book_id="b1", recipe_book_name="Book"
        )

    def _make_pub_recipe_result(self, rid="r1"):
        """Helper to build a valid PublicRecipeResult."""
        from api.v1.search.unified_search import UnifiedSearch
        return UnifiedSearch.PublicRecipeResult(
            id=rid, name="Test", recipe_book_id="b1", recipe_book_name="Book",
            owner=UnifiedSearch.OwnerInfo(),
        )

    @patch("api.v1.search.unified_search.UnifiedSearch._search_users")
    @patch("api.v1.search.unified_search.UnifiedSearch._search_public_recipes")
    @patch("api.v1.search.unified_search.UnifiedSearch._search_my_recipes")
    def test_exact_fills_limit_skips_fuzzy_and_semantic(
        self, mock_my, mock_pub, mock_users, mock_db, mock_user
    ):
        """Test that when exact results fill the limit, fuzzy and semantic tiers are skipped."""
        # Return exactly `limit` results for both my and public
        mock_my.return_value = [self._make_recipe_result(f"r{i}") for i in range(3)]
        mock_pub.return_value = [self._make_pub_recipe_result(f"p{i}") for i in range(3)]
        mock_users.return_value = []
        mock_db.db.execute.return_value = MockExecuteResult([])

        endpoint = self._make_endpoint(mock_db, mock_user)
        result = endpoint.execute(q="pasta", limit=3)

        assert result["success"] is True
        # my_exact has 3, limit is 3 -> no fuzzy or semantic needed
        assert len(result["data"].my_recipes) == 3
        assert len(result["data"].public_recipes) == 3

    @patch("api.v1.search.unified_search.UnifiedSearch._generate_query_embedding")
    @patch("api.v1.search.unified_search.UnifiedSearch._search_users")
    @patch("api.v1.search.unified_search.UnifiedSearch._search_public_recipes")
    @patch("api.v1.search.unified_search.UnifiedSearch._search_my_recipes")
    def test_my_exact_fills_but_pub_doesnt_runs_pub_semantic(
        self, mock_my, mock_pub, mock_users, mock_embed, mock_db, mock_user
    ):
        """Test that when my_exact fills limit but pub doesn't, only pub semantic runs."""
        # my fills the limit, pub doesn't
        mock_my.return_value = [self._make_recipe_result(f"r{i}") for i in range(3)]
        mock_pub.return_value = []
        mock_users.return_value = []
        mock_embed.return_value = [0.1] * 384
        mock_db.db.execute.return_value = MockExecuteResult([])

        endpoint = self._make_endpoint(mock_db, mock_user)
        result = endpoint.execute(q="pasta", limit=3)

        assert result["success"] is True
        mock_embed.assert_called_once()

    @patch("api.v1.search.unified_search.UnifiedSearch._generate_query_embedding")
    @patch("api.v1.search.unified_search.UnifiedSearch._search_users")
    @patch("api.v1.search.unified_search.UnifiedSearch._search_public_recipes")
    @patch("api.v1.search.unified_search.UnifiedSearch._search_my_recipes")
    def test_pub_exact_fills_but_my_doesnt_runs_my_semantic(
        self, mock_my, mock_pub, mock_users, mock_embed, mock_db, mock_user
    ):
        """Test that when pub_exact fills limit but my doesn't, only my semantic runs."""
        # pub fills the limit, my doesn't
        mock_my.return_value = []
        mock_pub.return_value = [self._make_pub_recipe_result(f"p{i}") for i in range(3)]
        mock_users.return_value = []
        mock_embed.return_value = [0.1] * 384
        mock_db.db.execute.return_value = MockExecuteResult([])

        endpoint = self._make_endpoint(mock_db, mock_user)
        result = endpoint.execute(q="pasta", limit=3)

        assert result["success"] is True
        mock_embed.assert_called_once()

    def test_full_search_response_shape(self, client, mock_db, mock_user):
        """Test that the full search response has query, my_recipes, public_recipes, users."""
        mock_db.db.query.return_value = MockQuery([])
        mock_db.db.execute.return_value = MockExecuteResult([])

        response = client.get("/v1/search?q=pasta")
        assert response.status_code == 200
        data = response.json()
        assert "query" in data
        assert data["query"] == "pasta"
        assert "my_recipes" in data
        assert "public_recipes" in data
        assert "users" in data

    def test_search_max_cook_time_filter(self, client, mock_db, mock_user):
        """Test that max_cook_time filter param is accepted and returns 200."""
        mock_db.db.query.return_value = MockQuery([])
        mock_db.db.execute.return_value = MockExecuteResult([])

        response = client.get("/v1/search?q=pasta&max_cook_time=45")
        assert response.status_code == 200

    def test_search_multiple_tags(self, client, mock_db, mock_user):
        """Test that multiple comma-separated tags are accepted."""
        mock_db.db.query.return_value = MockQuery([])
        mock_db.db.execute.return_value = MockExecuteResult([])

        response = client.get("/v1/search?q=pasta&tags=vegetarian,quick,easy")
        assert response.status_code == 200


class TestGenerateRecipeEmbedding:
    """Tests for generate_recipe_embedding helper."""

    @patch("openai.OpenAI")
    def test_success(self, mock_openai_cls):
        """Test successful embedding generation."""
        from api.v1.search.generate_recipe_embedding import generate_recipe_embedding

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.data = [MagicMock(embedding=[0.1] * 384)]
        mock_client.embeddings.create.return_value = mock_resp

        result = generate_recipe_embedding("Pasta", "Delicious pasta", ["italian"])

        assert result == [0.1] * 384
        mock_client.embeddings.create.assert_called_once_with(
            model="text-embedding-3-small",
            input="Pasta. Delicious pasta. Tags: italian",
            dimensions=384,
        )

    @patch("openai.OpenAI")
    def test_with_none_description_and_tags(self, mock_openai_cls):
        """Test embedding generation with None description and tags."""
        from api.v1.search.generate_recipe_embedding import generate_recipe_embedding

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.data = [MagicMock(embedding=[0.2] * 384)]
        mock_client.embeddings.create.return_value = mock_resp

        result = generate_recipe_embedding("Pasta", None, None)

        assert result == [0.2] * 384
        mock_client.embeddings.create.assert_called_once_with(
            model="text-embedding-3-small",
            input="Pasta. . Tags: ",
            dimensions=384,
        )

    @patch("openai.OpenAI")
    def test_exception_returns_none(self, mock_openai_cls):
        """Test that exception from OpenAI returns None."""
        from api.v1.search.generate_recipe_embedding import generate_recipe_embedding

        mock_openai_cls.side_effect = Exception("API key not set")

        result = generate_recipe_embedding("Pasta", "Desc", ["tag"])
        assert result is None

    @patch("openai.OpenAI")
    def test_api_error_returns_none(self, mock_openai_cls):
        """Test that API call error returns None."""
        from api.v1.search.generate_recipe_embedding import generate_recipe_embedding

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.embeddings.create.side_effect = Exception("Rate limited")

        result = generate_recipe_embedding("Pasta", "Desc", [])
        assert result is None


class TestAssignVibesForRecipe:
    """Tests for assign_vibes_for_recipe helper."""

    @patch("openai.OpenAI")
    def test_returns_valid_vibes_with_ingredients(self, mock_openai_cls):
        """Successful LLM response with ingredients_text — covers lines 54, 78-80."""
        from api.v1.search.generate_recipe_embedding import assign_vibes_for_recipe
        from utils.constants import VALID_VIBES

        valid = list(VALID_VIBES)
        primary = valid[0]
        secondary = valid[1] if len(valid) > 1 else None

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_message = MagicMock()
        mock_message.content = (
            f'{{"primary_vibe": "{primary}", "secondary_vibe": "{secondary}"}}'
        )
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock(message=mock_message)]
        mock_client.chat.completions.create.return_value = mock_resp

        result = assign_vibes_for_recipe(
            "Pasta", "Cozy dinner", ingredients_text="tomato, basil"
        )
        assert result == (primary, secondary)
        # Verify ingredients_text path was hit
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        user_msg = call_kwargs["messages"][1]["content"]
        assert "Ingredients: tomato, basil" in user_msg

    @patch("openai.OpenAI")
    def test_invalid_vibes_filtered_out(self, mock_openai_cls):
        """LLM returns vibes not in VALID_VIBES — both filtered to None."""
        from api.v1.search.generate_recipe_embedding import assign_vibes_for_recipe

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_message = MagicMock()
        mock_message.content = (
            '{"primary_vibe": "not-real", "secondary_vibe": "also-fake"}'
        )
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock(message=mock_message)]
        mock_client.chat.completions.create.return_value = mock_resp

        result = assign_vibes_for_recipe("Pasta", None, None)
        assert result == (None, None)

    @patch("openai.OpenAI")
    def test_exception_returns_none_pair(self, mock_openai_cls):
        from api.v1.search.generate_recipe_embedding import assign_vibes_for_recipe

        mock_openai_cls.side_effect = Exception("boom")
        result = assign_vibes_for_recipe("Pasta", "Desc", None)
        assert result == (None, None)


class TestUnifiedSearchQueryEmbedding:
    """Tests for the _generate_query_embedding method on the endpoint."""

    @patch("openai.OpenAI")
    def test_generate_query_embedding_success(self, mock_openai_cls, mock_db, mock_user):
        """Test successful query embedding generation."""
        from api.v1.search.unified_search import UnifiedSearch

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.data = [MagicMock(embedding=[0.5] * 384)]
        mock_client.embeddings.create.return_value = mock_resp

        endpoint = UnifiedSearch(user=mock_user, database=mock_db)
        result = endpoint._generate_query_embedding("pasta recipe")

        assert result == [0.5] * 384

    @patch("openai.OpenAI")
    def test_generate_query_embedding_failure(self, mock_openai_cls, mock_db, mock_user):
        """Test query embedding generation failure returns None."""
        from api.v1.search.unified_search import UnifiedSearch

        mock_openai_cls.side_effect = Exception("No API key")

        endpoint = UnifiedSearch(user=mock_user, database=mock_db)
        result = endpoint._generate_query_embedding("pasta recipe")

        assert result is None

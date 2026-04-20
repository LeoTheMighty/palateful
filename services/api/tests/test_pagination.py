"""Tests for the multi-key cursor helper (afh-1a)."""

import base64
import uuid

import pytest
from pagination import (
    InvalidCursorError,
    datetime_to_ms,
    decode_cursor,
    encode_cursor,
)


class TestEncodeDecodeRoundtrip:
    def test_roundtrip_with_archived_at(self):
        row_id = str(uuid.uuid4())
        cursor = encode_cursor(1_700_000_000_000, 1_699_000_000_000, row_id)
        arch_ms, created_ms, decoded_id = decode_cursor(cursor)
        assert arch_ms == 1_700_000_000_000
        assert created_ms == 1_699_000_000_000
        assert decoded_id == row_id

    def test_roundtrip_with_null_archived_at(self):
        row_id = str(uuid.uuid4())
        cursor = encode_cursor(None, 1_699_000_000_000, row_id)
        arch_ms, created_ms, decoded_id = decode_cursor(cursor)
        assert arch_ms is None
        assert created_ms == 1_699_000_000_000
        assert decoded_id == row_id

    def test_cursor_is_url_safe(self):
        row_id = str(uuid.uuid4())
        cursor = encode_cursor(None, 1_699_000_000_000, row_id)
        # base64url alphabet: A-Za-z0-9_- plus any padding we stripped
        assert all(c.isalnum() or c in "-_" for c in cursor)
        # sanity: stripped-padding format survives re-padding in decode
        assert not cursor.endswith("=")


class TestDecodeInvalidCursor:
    def test_empty_cursor_raises(self):
        with pytest.raises(InvalidCursorError):
            decode_cursor("")

    def test_non_string_cursor_raises(self):
        with pytest.raises(InvalidCursorError):
            decode_cursor(None)  # type: ignore[arg-type]

    def test_oversized_cursor_raises(self):
        with pytest.raises(InvalidCursorError):
            decode_cursor("a" * 300)

    def test_invalid_base64_raises(self):
        # "a" pads to "a===" which has an invalid data-char count (1).
        # urlsafe_b64decode raises binascii.Error which we re-raise.
        with pytest.raises(InvalidCursorError):
            decode_cursor("a")

    def test_non_utf8_payload_raises(self):
        raw = b"\xff\xfe\xfd"
        encoded = (
            base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
        )
        with pytest.raises(InvalidCursorError):
            decode_cursor(encoded)

    def test_wrong_field_count_raises(self):
        encoded = (
            base64.urlsafe_b64encode(b"only|two").decode("ascii").rstrip("=")
        )
        with pytest.raises(InvalidCursorError):
            decode_cursor(encoded)

    def test_non_numeric_archived_at_raises(self):
        row_id = str(uuid.uuid4())
        raw = f"notanumber|1699000000000|{row_id}".encode()
        encoded = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
        with pytest.raises(InvalidCursorError):
            decode_cursor(encoded)

    def test_non_numeric_created_at_raises(self):
        row_id = str(uuid.uuid4())
        raw = f"1699000000000|notanumber|{row_id}".encode()
        encoded = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
        with pytest.raises(InvalidCursorError):
            decode_cursor(encoded)

    def test_empty_row_id_raises(self):
        raw = b"1699000000000|1699000000000|"
        encoded = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
        with pytest.raises(InvalidCursorError):
            decode_cursor(encoded)


class TestDatetimeToMs:
    def test_none_input_returns_none(self):
        assert datetime_to_ms(None) is None

    def test_aware_datetime(self):
        from datetime import UTC, datetime

        dt = datetime(2025, 1, 1, tzinfo=UTC)
        result = datetime_to_ms(dt)
        assert result == int(dt.timestamp() * 1000)

    def test_naive_datetime_treated_as_utc(self):
        from datetime import UTC, datetime

        naive = datetime(2025, 1, 1)
        aware = naive.replace(tzinfo=UTC)
        assert datetime_to_ms(naive) == datetime_to_ms(aware)

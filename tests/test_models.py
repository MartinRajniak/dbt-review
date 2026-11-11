import pytest
from pydantic import ValidationError

from dbt_review.models import Finding


def finding_with(**overrides) -> Finding:
    fields = dict(
        check_id="check", source="rule", severity="warning", file="a.sql", line=1, message="m"
    )
    return Finding(**(fields | overrides))


def test_message_longer_than_300_characters_is_rejected():
    finding_with(message="x" * 300)
    with pytest.raises(ValidationError):
        finding_with(message="x" * 301)


def test_suggestion_longer_than_300_characters_is_rejected():
    finding_with(suggestion="x" * 300)
    with pytest.raises(ValidationError):
        finding_with(suggestion="x" * 301)

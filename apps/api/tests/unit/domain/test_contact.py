import pytest

from app.domain.value_objects import Email, PhoneNumber


def test_email_normalized_lowercase() -> None:
    assert Email(" Ana.Lopez@Example.COM ").value == "ana.lopez@example.com"


@pytest.mark.parametrize("raw", ["", "sin-arroba", "a@b", "a@@b.com", "a b@c.com"])
def test_invalid_email_rejected(raw: str) -> None:
    with pytest.raises(ValueError):
        Email(raw)


def test_email_masked_hides_local_part() -> None:
    masked = Email("ana.lopez@example.com").masked
    assert masked.endswith("@example.com")
    assert "lopez" not in masked


def test_phone_strips_separators() -> None:
    assert PhoneNumber("+34 611-22 33 44").value == "+34611223344"
    assert PhoneNumber("(600) 111.222").value == "600111222"


@pytest.mark.parametrize("raw", ["", "12345", "abcdefghi", "+" + "9" * 20])
def test_invalid_phone_rejected(raw: str) -> None:
    with pytest.raises(ValueError):
        PhoneNumber(raw)


def test_phone_masked_reveals_only_last_two_digits() -> None:
    masked = PhoneNumber("+34611223344").masked
    assert masked.endswith("44")
    assert "611" not in masked

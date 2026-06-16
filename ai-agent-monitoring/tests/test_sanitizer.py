"""Unit tests for output sanitizer."""

from security.sanitizer import sanitize, is_safe_output


def test_redacts_password():
    assert "***REDACTED***" in sanitize("password=supersecret123")
    assert "***REDACTED***" in sanitize("PASSWORD: abc123")


def test_redacts_token():
    assert "***REDACTED***" in sanitize("token=eyJhbGciOiJIUzI1NiJ9.abc")
    assert "***REDACTED***" in sanitize("Authorization: Bearer mytoken123")


def test_redacts_private_key():
    text = "-----BEGIN RSA PRIVATE KEY-----\nabc123\n-----END RSA PRIVATE KEY-----"
    assert "PRIVATE_KEY_REDACTED" in sanitize(text)


def test_redacts_connection_strings():
    assert "***@" in sanitize("postgresql://user:password@localhost/db")
    assert "***@" in sanitize("mysql://root:secret@db:3306/mydb")


def test_safe_text_unchanged():
    text = "df -h output: / 94% used"
    result = sanitize(text)
    assert "94%" in result


def test_blocked_dangerous_fragments():
    assert not is_safe_output("rm -rf / was executed")
    assert not is_safe_output("shutdown -h now")


def test_safe_output():
    assert is_safe_output("Filesystem / usage is 94%")
    assert is_safe_output("CPU usage: 92%")

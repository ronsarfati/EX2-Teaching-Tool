"""load_env_file with temporary files and plain dicts only."""
from app.env_file import load_env_file


def load(tmp_path, content, environ=None):
    path = tmp_path / ".env"
    path.write_text(content, encoding="utf-8")
    environ = {} if environ is None else environ
    load_env_file(path, environ)
    return environ


def test_reads_key_value_lines_ignoring_blanks_and_comments(tmp_path):
    assert load(tmp_path, "# note\n\nA=1\n  B = two  \nnot a pair\n") == {"A": "1", "B": "two"}


def test_strips_matching_quotes_only(tmp_path):
    env = load(tmp_path, "A=\"x y\"\nB='z'\nC=\"odd'\nD=\n")
    assert env == {"A": "x y", "B": "z", "C": "\"odd'", "D": ""}


def test_value_may_contain_equals(tmp_path):
    assert load(tmp_path, "URL=a=b=c\n") == {"URL": "a=b=c"}


def test_never_overrides_existing_variable(tmp_path):
    assert load(tmp_path, "A=file\nB=new\n", {"A": "real"}) == {"A": "real", "B": "new"}


def test_missing_file_does_nothing(tmp_path):
    environ = {"A": "1"}
    load_env_file(tmp_path / "absent.env", environ)
    assert environ == {"A": "1"}

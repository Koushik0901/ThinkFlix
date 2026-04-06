import os

from briefing.cli import _load_environment


def test_load_environment_reads_repo_dotenv(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("THINKFLIX_TEST_TOKEN", raising=False)
    (tmp_path / ".env").write_text("THINKFLIX_TEST_TOKEN=loaded\n", encoding="utf-8")

    _load_environment()

    assert os.environ["THINKFLIX_TEST_TOKEN"] == "loaded"


def test_load_environment_does_not_override_existing_values(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("THINKFLIX_TEST_TOKEN", "existing")
    (tmp_path / ".env").write_text("THINKFLIX_TEST_TOKEN=from_file\n", encoding="utf-8")

    _load_environment()

    assert os.environ["THINKFLIX_TEST_TOKEN"] == "existing"

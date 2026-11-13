from pathlib import Path
import pytest
from indian_equity_research.ingestion.xbrl_contexts import create_run_directory

def test_run_directory_is_isolated_and_preserves_existing_runs(tmp_path: Path):
    first = create_run_directory(tmp_path, "run-001")
    sentinel = first / "keep.txt"
    sentinel.write_text("known-good", encoding="utf-8")
    second = create_run_directory(tmp_path, "run-002")
    assert first != second
    assert sentinel.read_text(encoding="utf-8") == "known-good"
    assert second.is_dir()

def test_run_directory_refuses_to_reuse_existing_run_id(tmp_path: Path):
    first = create_run_directory(tmp_path, "run-001")
    sentinel = first / "keep.txt"
    sentinel.write_text("known-good", encoding="utf-8")
    with pytest.raises(FileExistsError):
        create_run_directory(tmp_path, "run-001")
    assert sentinel.read_text(encoding="utf-8") == "known-good"

@pytest.mark.parametrize("run_id", ["", "../escape", "name/child", "has space"])
def test_run_directory_rejects_unsafe_run_ids(tmp_path: Path, run_id: str):
    with pytest.raises(ValueError):
        create_run_directory(tmp_path, run_id)

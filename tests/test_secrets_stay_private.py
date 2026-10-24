"""Files that hold secrets must be ignored by git, so they can never be pushed by accident.

(A comment on the same line as a .gitignore rule silently breaks the rule; this
test caught that once.)
"""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = [".env", ".streamlit/secrets.toml", ".streamlit/secrets.cloud.toml", "data/app.sqlite"]


@pytest.mark.skipif(shutil.which("git") is None or not (ROOT / ".git").exists(), reason="not a git checkout")
@pytest.mark.parametrize("path", PRIVATE)
def test_private_files_are_ignored_and_untracked(path):
    ignored = subprocess.run(["git", "check-ignore", "-q", path], cwd=ROOT).returncode == 0
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", path], cwd=ROOT,
                             capture_output=True).returncode == 0
    assert ignored, f"{path} is not ignored by git"
    assert not tracked, f"{path} is tracked by git"

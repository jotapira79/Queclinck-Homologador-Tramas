from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path


def _cli_path() -> Path:
    return Path(__file__).resolve().parents[2] / "queclink_tramas.py"


def _fixture_path(name: str) -> Path:
    return Path(__file__).resolve().parents[2] / "tests" / "fixtures" / name


def test_cli_gtinf_min(tmp_path) -> None:
    script = _cli_path()
    input_file = _fixture_path("gv350ceu_gtinf_sample.txt")
    output_db = tmp_path / "out.db"

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--in",
            str(input_file),
            "--out",
            str(output_db),
            "--message",
            "GTINF",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0

    conn = sqlite3.connect(output_db)
    try:
        table_exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='gtinf_records'"
        ).fetchone()
        assert table_exists is not None, "gtinf_records table should exist"
        count = conn.execute("SELECT COUNT(*) FROM gtinf_records").fetchone()[0]
        assert count > 0, "Expected rows inserted into gtinf_records"
    finally:
        conn.close()

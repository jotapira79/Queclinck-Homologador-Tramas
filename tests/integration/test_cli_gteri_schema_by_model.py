import sqlite3
import subprocess
from pathlib import Path

import pytest

TABLE_BY_MODEL = {
    "gv350ceu": "gteri_gv350ceu",
    "gv58lau": "gteri_gv58lau",
    "gv310lau": "gteri_gv310lau",
}

MODEL_IMEI = {
    "gv350ceu": "86252406",
    "gv58lau": "86631406",
    "gv310lau": "86858906",
}


@pytest.mark.parametrize(
    "model,eri_mask,pos_mask",
    [
        ("gv350ceu", "00000002", "01"),
        ("gv58lau", "00000000", "00"),
        ("gv310lau", "00002000", "00"),
    ],
)
def test_schema_only_yaml_fields(model, eri_mask, pos_mask, tmp_path: Path):
    imei_prefix = MODEL_IMEI[model]
    text = (
        f"+RESP:GTERI,740904,{imei_prefix}012345,{model.upper()},"
        f"{eri_mask},13574,10,1,1,0.0,295,484.3,-70.297988,-23.739877,"
        "20251009132737,0730,0001,0836,002BEE06,"
        f"{pos_mask},8,799972.0,0000329:43:11,,,,100,111000,0,0,20251009133001,2B8B$\n"
    )
    in_file = tmp_path / "cases.txt"
    in_file.write_text(text)
    db_file = tmp_path / "out.db"
    subprocess.run(
        [
            "python",
            "queclink_tramas.py",
            "--in",
            str(in_file),
            "--out",
            str(db_file),
            "--message",
            "GTERI",
        ],
        check=True,
    )
    conn = sqlite3.connect(db_file)
    try:
        table = TABLE_BY_MODEL[model]
        cols = [column[1] for column in conn.execute(f"PRAGMA table_info({table})")]
    finally:
        conn.close()
    forbidden = {"raw_line", "is_buff", "prefix"}
    assert forbidden.isdisjoint(cols)
    must_have = {"imei", "lon", "lat", "send_time", "eri_mask"}
    assert must_have.issubset(set(cols))

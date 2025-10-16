"""Pruebas para el ingestor SQLite."""

from __future__ import annotations

from pathlib import Path

from queclink.ingestor_sqlite import bulk_ingest_from_file, init_db

GTERI_SAMPLE = (
    "+RESP:GTERI,6E1203,864696060004173,GV310LAU,00000100,,10,1,1,0.0,0,115.8,"
    "117.129356,31.839248,20230808061540,0460,0001,DF5C,05FE6667,03,15,,4.0,"
    "0000102:34:33,14549,42,11172,100,210000,0,1,0,06,12,0,001A42A2,0617,TMPS,"
    "08351B00043C,1,26,65,20231030085704,20231030085704,0017$"
)


def _write_lines(tmp_path: Path, filename: str, lines: list[str]) -> Path:
    path = tmp_path / filename
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def test_bulk_ingest_gteri(tmp_path: Path) -> None:
    conn = init_db(":memory:")

    gv310_path = _write_lines(
        tmp_path,
        "gv310_gteri.txt",
        [GTERI_SAMPLE, "INVALID", ""],
    )
    inserted = bulk_ingest_from_file(conn, "GV310LAU", "GTERI", gv310_path)
    assert inserted == 1
    cur = conn.execute("SELECT COUNT(*) FROM gv310lau_gteri")
    assert cur.fetchone()[0] == 1

    gv58_resp = GTERI_SAMPLE.replace("GV310LAU", "GV58LAU")
    gv58_buff = gv58_resp.replace("+RESP:", "+BUFF:", 1)
    gv58_path = _write_lines(tmp_path, "gv58_gteri.txt", [gv58_resp, gv58_buff])
    inserted = bulk_ingest_from_file(conn, "GV58LAU", "GTERI", gv58_path)
    assert inserted == 2
    cur = conn.execute("SELECT COUNT(*) FROM gv58lau_gteri")
    assert cur.fetchone()[0] == 2


def test_bulk_ingest_gtinf(tmp_path: Path) -> None:
    conn = init_db(":memory:")

    gtinf_resp = (
        "+RESP:GTINF,040201,864696060004173,GV350CEU,GV350CEU,GV350CEU,"
        "040201,20231030085704,0017$"
    )
    gtinf_buff = gtinf_resp.replace("+RESP:", "+BUFF:", 1)
    gtinf_path = _write_lines(
        tmp_path,
        "gv350_gtinf.txt",
        [gtinf_resp, gtinf_buff, "WRONG"],
    )
    inserted = bulk_ingest_from_file(conn, "GV350CEU", "GTINF", gtinf_path)
    assert inserted == 2
    cur = conn.execute("SELECT COUNT(*) FROM gtinf_gv350ceu")
    assert cur.fetchone()[0] == 2

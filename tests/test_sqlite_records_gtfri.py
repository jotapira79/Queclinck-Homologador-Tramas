from src.ingestors.sqlite_records import (
    ensure_db,
    ingest_lines,
    resolve_spec,
    spec_to_sql_columns,
)


GTFRI_LINES = [
    "+RESP:GTFRI,8020040900,866314061768998,GV58LAU,12714,50,1,1,0.0,235,2923.1,"\
    "-68.867600,-22.201688,20251016151536,0730,0001,0899,00542913,01,12,6537.2,"\
    "0000219:06:11,,,,100,220100,,,,20251016151537,591D$",
    "+BUFF:GTFRI,8020040703,866314061771471,GV58LAU,28204,10,1,1,29.9,25,142.2,"\
    "-71.586724,-33.590164,20251015190846,,,,,08,0.69,1.11,1.30,659946.1,"\
    "0001265:29:11,,,,100,220100,,,,20251015190847,868C$",
]


def test_ingest_lines_creates_gtfri_table_with_spec_columns():
    conn = ensure_db(":memory:")

    inserted = ingest_lines(conn, GTFRI_LINES, message="GTFRI")
    assert inserted == len(GTFRI_LINES)

    spec = resolve_spec("GTFRI", "GV58LAU")
    table_name = spec["spec"].table_name

    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    )
    assert cursor.fetchone() is not None

    info = conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
    columns = [row[1] for row in info]
    expected_columns = [name for name, _ in spec_to_sql_columns(spec)]
    assert columns == expected_columns

    rows = conn.execute(
        f'SELECT imei, hdop, vdop, pdop_or_acc_factor, tail FROM "{table_name}" '
        "ORDER BY send_time"
    ).fetchall()
    assert rows == [
        ("866314061771471", 0.69, 1.11, 1.3, "$"),
        ("866314061768998", None, None, None, "$"),
    ]

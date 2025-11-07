from src.ingestors.sqlite_records import (
    ensure_db,
    ingest_lines,
    resolve_spec,
    spec_to_sql_columns,
)


GTFRI_GV58LAU_LINES = [
    "+RESP:GTFRI,8020040900,866314061768998,GV58LAU,12714,50,1,1,0.0,235,2923.1,"\
    "-68.867600,-22.201688,20251016151536,0730,0001,0899,00542913,01,12,6537.2,"\
    "0000219:06:11,,,,100,220100,,,,20251016151537,591D$",
    "+BUFF:GTFRI,8020040703,866314061771471,GV58LAU,28204,10,1,1,29.9,25,142.2,"\
    "-71.586724,-33.590164,20251015190846,,,,,08,0.69,1.11,1.30,659946.1,"\
    "0001265:29:11,,,,100,220100,,,,20251015190847,868C$",
]


GTFRI_GV310LAU_LINES = [
    "+RESP:GTFRI,6E0C03,868589060693259,GV310LAU,25194,10,1,1,0.0,16,440.5,"\
    "-70.309823,-23.760673,20251016180342,0730,0002,00CE,0985D171,00,183603.6,"\
    "0000748:27:41,,,,100,210100,,,,20251016180343,28C2$",
    "+BUFF:GTFRI,6E0C03,868589060367029,GV310LAU,28177,10,1,1,87.9,83,791.2,"\
    "-70.089688,-23.450809,20251016180337,0730,0001,0837,002BED03,09,11,0.88,"\
    "1.29,1.56,89436.1,0001852:29:54,,,,100,220100,,,,20251016180339,A9B4$",
]


GTFRI_GV350CEU_LINES = [
    "+RESP:GTFRI,740904,862524060867948,GV350CEU,,10,1,1,89.5,169,672.9,"\
    "-70.292914,-23.949947,20251016184033,0730,0001,0836,002BEE06,01,12,"\
    "775824.1,0000439:30:29,,,,100,221102,,,,20251016184035,AA3C$",
    "+BUFF:GTFRI,740904,862524060867948,GV350CEU,,10,1,1,89.6,168,690.2,"\
    "-70.291068,-23.958760,20251016184113,0730,0001,0836,002BEE06,01,12,"\
    "775825.1,0000439:31:11,,,,100,221102,,,,20251016184115,AA41$",
]


GTFRI_GV75LAU_LINES = [
    "+RESP:GTFRI,80200C0300,866314060583471,GV75LAU,10,1,12,45.6,180,12.3,"\
    "-70.650123,-33.437200,20251029091530,0460,0000,1A2B,00FF,03,12,3,12345.6,"\
    "00012:35:07,,,,85,221102,,,,20251029091533,1A2B$",
    "+BUFF:GTFRI,80200C0300,866314060583471,GV75LAU,11,1,8,0.0,0,0.0,"\
    "-70.650100,-33.437100,20251029092000,0460,0000,1A2B,0003,03,10,1,13550.0,"\
    "00012:35:07,,,,100,210100,,,,20251029092002,3F7C$",
]


def test_ingest_lines_creates_gtfri_gv58lau_table_with_spec_columns():
    conn = ensure_db(":memory:")

    inserted = ingest_lines(conn, GTFRI_GV58LAU_LINES, message="GTFRI")
    assert inserted == len(GTFRI_GV58LAU_LINES)

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


def test_ingest_lines_creates_gtfri_gv310lau_table_with_spec_columns():
    conn = ensure_db(":memory:")

    inserted = ingest_lines(conn, GTFRI_GV310LAU_LINES, message="GTFRI")
    assert inserted == len(GTFRI_GV310LAU_LINES)

    spec = resolve_spec("GTFRI", "GV310LAU")
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
        f'SELECT unique_id, satellites_in_use, horizontal_gnss_accuracy, '
        f'vertical_gnss_accuracy, gnss_3d_accuracy, backup_battery_percentage, '
        f'tail FROM "{table_name}" ORDER BY count_number'
    ).fetchall()
    assert rows == [
        ("868589060693259", None, None, None, None, 100, "$"),
        ("868589060367029", 11, 0.88, 1.29, 1.56, 100, "$"),
    ]


def test_ingest_lines_creates_gtfri_gv350ceu_table_with_spec_columns():
    conn = ensure_db(":memory:")

    inserted = ingest_lines(conn, GTFRI_GV350CEU_LINES, message="GTFRI")
    assert inserted == len(GTFRI_GV350CEU_LINES)

    spec = resolve_spec("GTFRI", "GV350CEU")
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
        f'SELECT unique_id, position_append_mask, satellites_in_use, '
        f'analog_in_1, backup_battery_percentage, device_status, tail '
        f'FROM "{table_name}" ORDER BY send_time'
    ).fetchall()
    assert rows == [
        ("862524060867948", "01", 12, None, 100, "221102", "$"),
        ("862524060867948", "01", 12, None, 100, "221102", "$"),
    ]


def test_ingest_lines_creates_gtfri_gv75lau_table_with_spec_columns():
    conn = ensure_db(":memory:")

    inserted = ingest_lines(conn, GTFRI_GV75LAU_LINES, message="GTFRI")
    assert inserted == len(GTFRI_GV75LAU_LINES)

    spec = resolve_spec("GTFRI", "GV75LAU")
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
        f'SELECT cell_id, position_append_mask, satellites_used, '
        f'gnss_trigger_type, mileage_km, backup_battery_percentage, '
        f'device_status, count_hex FROM "{table_name}" ORDER BY send_time'
    ).fetchall()
    assert rows == [
        ("00FF", "03", 12, 3, 12345.6, 85, "221102", "1A2B"),
        ("0003", "03", 10, 1, 13550.0, 100, "210100", "3F7C"),
    ]

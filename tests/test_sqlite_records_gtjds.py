"""SQLite ingestion tests for GTJDS records across supported models."""

from src.ingestors.sqlite_records import (
    ensure_db,
    ingest_lines,
    resolve_spec,
    spec_to_sql_columns,
)


GTJDS_LINES = [
    "+RESP:GTJDS,6E0C03,868589060379784,GV310LAU,1,3,1,85.7,350,1206.3,"
    "-69.972567,-28.038460,20251016202522,0730,0001,0C82,00550412,00,"
    "20251016202522,8170$",
    "+RESP:GTJDS,6E0C03,868589060255190,GV310LAU,1,3,0,126.8,339,759.7,"
    "-70.625297,-33.348113,20251016202239,0730,0002,0517,00103625,0F,10,"
    "0.75,1.10,1.80,20251016202301,837A$",
    "+BUFF:GTJDS,6E0201,868589060248765,GV310LAU,2,3,0,29.1,64,472.4,"
    "-72.157288,-38.322191,20251016201851,,,,,00,20251016201851,80DE$",
]


def test_ingest_lines_creates_gtjds_gv310lau_table_with_spec_columns():
    conn = ensure_db(":memory:")

    inserted = ingest_lines(conn, GTJDS_LINES, message="GTJDS")
    assert inserted == len(GTJDS_LINES)

    spec = resolve_spec("GTJDS", "GV310LAU")
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
        f'SELECT unique_id, jamming_state, jamming_net, position_append_mask, '
        f'satellites_in_use, horizontal_gnss_accuracy, vertical_gnss_accuracy, '
        f'gnss_3d_accuracy, mcc, mnc, lac_hex, cell_id_hex '
        f'FROM "{table_name}" ORDER BY send_time'
    ).fetchall()

    assert rows == [
        (
            "868589060248765",
            2,
            3,
            "00",
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
        ),
        (
            "868589060255190",
            1,
            3,
            "0F",
            10,
            0.75,
            1.10,
            1.80,
            "0730",
            "0002",
            "0517",
            "00103625",
        ),
        (
            "868589060379784",
            1,
            3,
            "00",
            None,
            None,
            None,
            None,
            "0730",
            "0001",
            "0C82",
            "00550412",
        ),
    ]


GTJDS_GV75LAU_LINES = [
    "+RESP:GTJDS,80200C0300,135790246811220,GV75LAU,1,3,0,4.3,92,70.0,121.354335,31.222073,20230214013254,0460,0000,18d8,6141,05,1,220100,20230214093254,11F0$",
    "+BUFF:GTJDS,80200C0300,135790246811220,GV75LAU,2,3,0,0.0,0,0.0,-, -,20230214013254,,,,,00,20230214013254,11F1$",
]


def test_ingest_lines_creates_gtjds_gv75lau_table_with_spec_columns():
    conn = ensure_db(":memory:")

    inserted = ingest_lines(conn, GTJDS_GV75LAU_LINES, message="GTJDS")
    assert inserted == len(GTJDS_GV75LAU_LINES)

    spec = resolve_spec("GTJDS", "GV75LAU")
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
        f'SELECT unique_id, jamming_status, jamming_net, position_append_mask, '
        f'satellites_in_use, device_status, longitude_deg, latitude_deg '
        f'FROM "{table_name}" ORDER BY send_time'
    ).fetchall()

    assert rows == [
        (
            "135790246811220",
            2,
            3,
            "00",
            None,
            None,
            None,
            None,
        ),
        (
            "135790246811220",
            1,
            3,
            "05",
            1,
            "220100",
            121.354335,
            31.222073,
        ),
    ]

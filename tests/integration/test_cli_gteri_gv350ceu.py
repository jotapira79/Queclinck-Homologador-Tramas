import sqlite3
import subprocess
import sys
from pathlib import Path


def _cli_path() -> Path:
    return Path(__file__).resolve().parents[2] / "queclink_tramas.py"


def _fixture_path() -> Path:
    return Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "gv350ceu" / "gteri" / "resp_gteri.txt"


def test_cli_gteri_creates_expected_schema(tmp_path) -> None:
    script = _cli_path()
    input_file = _fixture_path()
    output_db = tmp_path / "gteri.db"

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--in",
            str(input_file),
            "--out",
            str(output_db),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert output_db.exists(), "The CLI must create the SQLite database"
    assert "[OK]" in result.stdout

    conn = sqlite3.connect(output_db)
    try:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(gteri_gv350ceu)")]
        assert {"raw_line", "is_buff", "prefix"}.isdisjoint(columns)
        expected_columns = [
            "header",
            "message",
            "full_protocol_version",
            "imei",
            "device_name",
            "eri_mask",
            "external_power_mv",
            "report_type",
            "number",
            "gnss_accuracy",
            "speed_kmh",
            "azimuth_deg",
            "altitude_m",
            "lon",
            "lat",
            "gnss_utc_time",
            "mcc",
            "mnc",
            "lac_hex",
            "cell_id_hex",
            "position_append_mask",
            "satellites_in_use",
            "hdop",
            "vdop",
            "pdop",
            "gnss_trigger_type",
            "gnss_jamming_state",
            "mileage_km",
            "hour_meter",
            "analog_in_1",
            "analog_in_2",
            "analog_in_3",
            "backup_batt_percent",
            "device_status",
            "uart_device_type",
            "ble_count",
            "ble_accessories",
            "rat",
            "band",
            "send_time",
            "count_hex",
        ]
        assert columns == expected_columns

        rows = conn.execute(
            """
            SELECT imei, lon, lat, gnss_utc_time, send_time, eri_mask, position_append_mask
            FROM gteri_gv350ceu
            """
        ).fetchall()
        assert rows, "Expected parsed rows in gteri_gv350ceu"
        for imei, lon, lat, gnss_utc_time, send_time, eri_mask, pos_mask in rows:
            assert imei
            assert lon is not None
            assert lat is not None
            assert gnss_utc_time
            assert send_time
            assert eri_mask
            assert pos_mask
    finally:
        conn.close()

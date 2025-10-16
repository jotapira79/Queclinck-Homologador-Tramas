from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from queclink.specs.loader import get_spec_columns


SAMPLES = [
    # GV310LAU
    "+RESP:GTINF,6E0C03,868589060361840,Unidad-01,11,89999112400719079703,32,0,0,0,3,3.81,0,1,2,0,20251007214015,3,,0,,00,00,+0000,0,20251007215025,BD2C$",
    "+BUFF:GTINF,6E0C03,868589060716712,GV310LAU,21,89999112400719021127,15,0,1,27999,2,4.16,0,1,2,0,20251007194843,3,,0,,01,00,+0000,0,20251007194845,32B0$",
    # GV58LAU
    "+RESP:GTINF,8020040900,866314061635635,Camion58,11,89999202003110001341,58,0,1,12943,3,4.15,0,1,,,20251007213819,0,,,,00,00,+0000,0,20251007215523,48D6$",
    "+BUFF:GTINF,8020040305,866314060965330,GV58LAU,22,89999112400719088191,26,0,1,13742,0,4.22,0,1,,,20250930110413,0,,,,01,00,+0000,0,20250930110413,ED27$",
    # GV350CEU
    "+RESP:GTINF,74040A,862524060748775,QK-350,11,89999112400719062394,37,0,1,13074,,4.19,0,1,,,20251007213710,,0,0,0,00,00,+0000,0,20251007213751,6B91$",
    "+BUFF:GTINF,740904,862524060876527,GV350CEU,22,8935711001088072340f,38,0,1,28018,3,4.11,0,1,,,20251007143611,,0,0,0,11,00,+0000,0,20251007143612,34DA$",
]


@pytest.mark.integration
def test_cli_ingests_gtinf_end_to_end(tmp_path: Path):
    # Archivos temporales
    datos = tmp_path / "datos.txt"
    outdb = tmp_path / "salida.db"

    # Escribir muestras
    datos.write_text("\n".join(SAMPLES) + "\n", encoding="utf-8")

    # Ruta del script CLI en el repo
    script = Path.cwd() / "queclink_tramas.py"
    assert script.exists(), f"No se encontró {script}; asegúrate de ejecutar desde la raíz del repo"

    # Ejecutar CLI
    completed = subprocess.run(
        [sys.executable, str(script), "--in", str(datos), "--out", str(outdb), "--message", "GTINF"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
        cwd=Path.cwd(),
    )

    # Salida estándar debe contener el resumen OK
    stdout = completed.stdout
    assert "[OK]" in stdout, f"Salida inesperada del CLI:\n{stdout}\nSTDERR:\n{completed.stderr}"

    # Validaciones en SQLite
    assert outdb.exists(), "No se generó el archivo SQLite de salida"

    conn = sqlite3.connect(str(outdb))
    cur = conn.cursor()

    # Validar tablas dinámicas por modelo
    for dev in ("GV310LAU", "GV58LAU", "GV350CEU"):
        table = f"gtinf_{dev.lower()}"
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
        assert cur.fetchone() is not None, f"No se creó la tabla {table}"

        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count, = cur.fetchone()
        assert count == 2, f"Se esperaban 2 filas GTINF para {dev}"

        cur.execute(f"PRAGMA table_info({table})")
        schema_columns = [row[1] for row in cur.fetchall()]
        assert schema_columns == get_spec_columns("GTINF", dev), "Columnas no coinciden con la spec"

        cur.execute(f"SELECT DISTINCT message FROM {table}")
        messages = {row[0] for row in cur.fetchall()}
        assert messages == {"INF"}

        cur.execute(f"SELECT DISTINCT header FROM {table}")
        headers = {row[0] for row in cur.fetchall()}
        assert headers == {"+RESP:GT", "+BUFF:GT"}

    conn.close()

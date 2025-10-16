# Feat: soporte completo para `+RESP:GTERI` (GV310LAU)

> **Contexto**
>
> Este PR implementa/mejora el parser para la trama **`+RESP:GTERI`** del dispositivo **GV310LAU** utilizando la especificación añadida en:
> - `docs/protocolo_gteri.md`
> - `spec/protocolo_gteri.yml`
>
> También agrega pruebas unitarias para validar campos base, presencia condicional (máscaras) y semántica de GNSS/HDOP/VDOP/PDOP.

---

## Checklist

- [ ] Leí `docs/protocolo_gteri.md` y `spec/protocolo_gteri.yml` y apliqué la estructura de campos.
- [ ] Implementé `parse_gteri(trama: str) -> dict` (o equivalente) con normalización de tipos y fechas.
- [ ] Soporté **`position_append_mask`** (bits 0–3 → sats/HDOP/VDOP/PDOP) y **`eri_mask`** (bits 0,1,2,10 para digital fuel / 1-wire / CAN / fuel).
- [ ] Parseé opcionales RF433/BLE y apliqué **Accessory Append Mask** en cada ítem BLE.
- [ ] Aseguré validaciones de rango/forma y errores claros (`ParseError` o similar).
- [ ] Añadí y pasé las pruebas de `tests/test_gteri_parser.py`.
- [ ] Documenté funciones nuevas con docstrings y ejemplos.
- [ ] (Opcional) Añadí `examples/parse_sample.py` leyendo `tests/samples_gteri.txt`.

---

## Resumen de cambios

- **Código**: (archivos y funciones claves)
- **Tests**: (archivos y casos)
- **Docs**: (actualizaciones, si aplica)

---

## Cómo probar

```bash
# entorno local
pytest -q

# o ejecutar sólo los tests de GTERI
pytest -q tests/test_gteri_parser.py::test_parse_gteri_campos_basicos

# Uso del CLI de visualización en Windows

Esta guía resume cómo ejecutar `viz.cli` en shells típicos de Windows. Los comandos generan un
mapa HTML y un GeoJSON por día local (`America/Santiago`).

## PowerShell

```powershell
py -m viz.cli --db salida.db --imei 864696060004173 --date 2023-08-01 `
  --provider "CartoDB Positron" --out mapas/gv310lau_2023-08-01
```

Notas:

- Usa `` ` `` (acentos graves) al final de la línea si deseas dividir el comando.
- `py` selecciona automáticamente la versión de Python instalada. Puedes reemplazarlo por la ruta
  completa si lo prefieres.

## Símbolo del sistema (CMD)

```cmd
py -m viz.cli ^
  --db salida.db ^
  --imei 864696060004173 ^
  --date 2023-08-01 ^
  --provider "CartoDB Positron" ^
  --out mapas\gv310lau_2023-08-01
```

Notas:

- Usa `^` como continuador de línea.
- Recuerda duplicar las barras en las rutas (`mapas\...`).

## Alternativas

- Ejecuta el comando en una sola línea si prefieres evitar continuadores.
- Si `py` no está disponible, usa la ruta a `python.exe`, por ejemplo `C:\Python311\python.exe`.
- Valida que las dependencias (`folium`, `pytz`, `python-dateutil`) estén instaladas en el entorno
  activo.

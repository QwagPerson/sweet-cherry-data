# Temperaturas 2026 V2

Desde la raíz de Sweet-Cherry:

```powershell
python sweet-cherry-data/scripts/transforma_consolida_temperaturas_2026_v2/main.py
python sweet-cherry-front/scripts/sync_silver_temperatures.py
```

El primer comando lee el histórico, Temperaturas 2026.xlsx y Temperaturas 2026 V2.xlsx. Resuelve los nombres mediante maestros/lugar.csv y los alias del consolidador original. Las mediciones válidas de V2 tienen prioridad por zona y hora; no se promedian con la versión anterior. Las filas sin fecha o temperatura finita se descartan, conservando la medición anterior si existe. Las zonas desconocidas y fechas fuera de 2026 generan un error.

Se conservan las zonas y fechas no cubiertas por V2. Dentro de una misma fuente, las lecturas de una hora se promedian. La continuidad horaria, imputación y archivos de salida reutilizan el consolidador original: data/silver/2026/temperaturas_horarias_por_lugar.csv, su resumen y archivos por zona. Silver distingue las mediciones observadas de las imputadas.

El segundo comando actualiza los CSV y Parquet en sweet-cherry-front/data/temperature_by_zone con los alias que usa el front. El sincronizador existente exporta la temperatura completa, incluidas las horas imputadas. Reinicia el proceso del front después de sincronizar para vaciar sus cachés de datos. Estos archivos de datos están excluidos de Git en el front y deben incluirse en el despliegue.

Pruebas:

```powershell
python -m pytest sweet-cherry-data/scripts/transforma_consolida_temperaturas_2026_v2/test_main.py -q
```

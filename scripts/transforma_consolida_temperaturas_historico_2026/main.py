from __future__ import annotations

import re
import unicodedata
from datetime import datetime, time
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BRONZE_2025_DIR = PROJECT_ROOT / "data" / "bronze" / "2025"
BRONZE_2026_DIR = PROJECT_ROOT / "data" / "bronze" / "2026"
SILVER_2026_DIR = PROJECT_ROOT / "data" / "silver" / "2026"
MAESTRO_LUGAR_PATH = PROJECT_ROOT / "maestros" / "lugar.csv"

HISTORICAL_TEMPERATURES_PATH = (
    BRONZE_2025_DIR / "Consolidado Temperatura Campos Completo.xlsx"
)
TEMPERATURES_2026_PATH = BRONZE_2026_DIR / "Temperaturas 2026.xlsx"

CONSOLIDATED_OUTPUT_PATH = SILVER_2026_DIR / "temperaturas_horarias_por_lugar.csv"
SUMMARY_OUTPUT_PATH = SILVER_2026_DIR / "temperaturas_horarias_por_lugar_resumen.csv"
PER_PLACE_OUTPUT_DIR = SILVER_2026_DIR / "temperaturas_horarias_por_lugar"

SHORT_GAP_LIMIT_HOURS = 6
LARGE_GAP_THRESHOLD_HOURS = 24
LARGE_GAPS_PER_ZONE = 5


def normalize_text(value: Any) -> str:
    if pd.isna(value):
        return ""

    text = str(value).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def slugify(value: str) -> str:
    return normalize_text(value).replace(" ", "_")


def title_case_spanish(value: str) -> str:
    return " ".join(word.capitalize() for word in str(value).split())


def read_lugar_master() -> pd.DataFrame:
    master = pd.read_csv(MAESTRO_LUGAR_PATH)
    required_columns = {
        "codigo",
        "id",
        "nombre",
        "terminos_relacionados",
        "latitud",
        "longitud",
        "condicion",
    }
    missing_columns = required_columns.difference(master.columns)
    if missing_columns:
        raise ValueError(
            f"Missing columns in {MAESTRO_LUGAR_PATH}: {sorted(missing_columns)}"
        )

    master = master.copy()
    master["codigo"] = master["codigo"].astype(str).str.strip()
    master["lugar"] = master["nombre"].map(title_case_spanish)
    return master


def build_place_aliases(master: pd.DataFrame) -> dict[str, str]:
    aliases: dict[str, str] = {}

    for row in master.itertuples(index=False):
        aliases[normalize_text(row.nombre)] = row.codigo
        terms = row.terminos_relacionados
        if pd.notna(terms):
            for term in str(terms).split("|"):
                aliases[normalize_text(term)] = row.codigo

    aliases.update(
        {
            "los niches 2": "NIC",
            "sta magdalena": "NIC",
            "teno don sergio": "TEM",
            "teno sta ana": "TEO",
            "sta ana": "TEO",
            "santa ana": "TEO",
            "teno rauco": "TEP",
            "viluco seguimiento": "VIL",
        }
    )
    return {key: value for key, value in aliases.items() if key}


def resolve_place_code(raw_place: Any, aliases: dict[str, str]) -> str | None:
    normalized = normalize_text(raw_place)
    if not normalized:
        return None

    if normalized in aliases:
        return aliases[normalized]

    if normalized.startswith("los niches"):
        return "NIC"
    if any(term in normalized for term in ("wapri", "marengo", "sta magdalena")):
        return "NIC"
    if any(term in normalized for term in ("teno montana", "don sergio")):
        return "TEM"
    if any(term in normalized for term in ("teno oriente", "sta ana", "santa ana")):
        return "TEO"
    if any(term in normalized for term in ("teno poniente", "teno rauco", "gonzalo")):
        return "TEP"
    if "viluco" in normalized:
        return "VIL"

    return None


def parse_hour_delta(value: Any) -> pd.Timedelta | pd.NaT:
    if pd.isna(value):
        return pd.NaT

    if isinstance(value, pd.Timestamp):
        return pd.Timedelta(
            hours=value.hour,
            minutes=value.minute,
            seconds=value.second,
            microseconds=value.microsecond,
        )

    if isinstance(value, datetime):
        return pd.Timedelta(
            hours=value.hour,
            minutes=value.minute,
            seconds=value.second,
            microseconds=value.microsecond,
        )

    if isinstance(value, time):
        return pd.Timedelta(
            hours=value.hour,
            minutes=value.minute,
            seconds=value.second,
            microseconds=value.microsecond,
        )

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if 0 <= float(value) < 1:
            return pd.Timedelta(days=float(value))
        if 0 <= float(value) <= 24:
            return pd.Timedelta(hours=float(value))

    text = str(value).strip()
    if not text:
        return pd.NaT

    delta = pd.to_timedelta(text, errors="coerce")
    if pd.notna(delta):
        return delta

    timestamp = pd.to_datetime(text, errors="coerce")
    if pd.notna(timestamp):
        return pd.Timedelta(
            hours=timestamp.hour,
            minutes=timestamp.minute,
            seconds=timestamp.second,
            microseconds=timestamp.microsecond,
        )

    return pd.NaT


def combine_date_and_hour(date_values: pd.Series, hour_values: pd.Series) -> pd.Series:
    dates = pd.to_datetime(date_values, errors="coerce").dt.normalize()
    hours = pd.Series(
        [parse_hour_delta(value) for value in hour_values],
        index=hour_values.index,
        dtype="timedelta64[ns]",
    )
    return dates + hours


def read_historical_temperatures(aliases: dict[str, str]) -> pd.DataFrame:
    df = pd.read_excel(
        HISTORICAL_TEMPERATURES_PATH,
        sheet_name="CONSOLIDADO TEMPERATURAS",
    )

    df = df.rename(
        columns={
            "LUGAR": "lugar_raw",
            "FECHA": "fecha",
            "HORA": "hora",
            "TEMPERATURA": "temperatura",
        }
    )
    df["codigo_lugar"] = df["lugar_raw"].map(
        lambda value: resolve_place_code(value, aliases)
    )
    df["ds"] = combine_date_and_hour(df["fecha"], df["hora"])
    df["temperatura_c"] = pd.to_numeric(df["temperatura"], errors="coerce")
    df["fuente"] = HISTORICAL_TEMPERATURES_PATH.name

    return df[["codigo_lugar", "lugar_raw", "ds", "temperatura_c", "fuente"]]


def read_2026_temperatures(aliases: dict[str, str]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    excel = pd.ExcelFile(TEMPERATURES_2026_PATH)

    for sheet_name in excel.sheet_names:
        df = pd.read_excel(TEMPERATURES_2026_PATH, sheet_name=sheet_name)
        if df.empty:
            continue

        temperature_column = next(
            (column for column in df.columns if normalize_text(column) in {"t", "t deg"}),
            None,
        )
        if temperature_column is None:
            temperature_column = "T°" if "T°" in df.columns else None
        if temperature_column is None:
            raise ValueError(f"Temperature column not found in sheet '{sheet_name}'")

        frame = pd.DataFrame(
            {
                "codigo_lugar": df["Lugar"].map(
                    lambda value: resolve_place_code(value, aliases)
                ),
                "lugar_raw": df["Lugar"],
                "ds": combine_date_and_hour(df["Fecha"], df["Hora"]),
                "temperatura_c": pd.to_numeric(df[temperature_column], errors="coerce"),
                "fuente": f"{TEMPERATURES_2026_PATH.name}::{sheet_name}",
            }
        )
        frames.append(frame)

    if not frames:
        return pd.DataFrame(
            columns=["codigo_lugar", "lugar_raw", "ds", "temperatura_c", "fuente"]
        )

    return pd.concat(frames, ignore_index=True)


def validate_places(raw: pd.DataFrame, master: pd.DataFrame) -> None:
    unknown = sorted(
        raw.loc[raw["codigo_lugar"].isna() & raw["lugar_raw"].notna(), "lugar_raw"]
        .astype(str)
        .unique()
    )
    if unknown:
        raise ValueError(f"Places without mapping to maestro/lugar.csv: {unknown}")

    observed_codes = set(
        raw.loc[raw["ds"].notna() & raw["temperatura_c"].notna(), "codigo_lugar"]
        .dropna()
        .unique()
    )
    expected_codes = set(master["codigo"])
    missing_codes = sorted(expected_codes.difference(observed_codes))
    if missing_codes:
        raise ValueError(
            "No valid temperature observations were found for maestro places: "
            f"{missing_codes}"
        )


def aggregate_hourly(raw: pd.DataFrame, master: pd.DataFrame) -> pd.DataFrame:
    valid = raw.loc[raw["codigo_lugar"].notna() & raw["ds"].notna()].copy()
    valid["ds"] = valid["ds"].dt.floor("h")

    hourly = (
        valid.groupby(["codigo_lugar", "ds"], as_index=False)
        .agg(
            temperatura_c=("temperatura_c", "mean"),
            observaciones_validas=("temperatura_c", "count"),
            observaciones_total=("temperatura_c", "size"),
        )
        .merge(
            master[
                ["codigo", "id", "lugar", "nombre", "condicion", "latitud", "longitud"]
            ],
            left_on="codigo_lugar",
            right_on="codigo",
            how="left",
        )
        .drop(columns=["codigo"])
        .rename(columns={"id": "id_lugar", "nombre": "nombre_maestro"})
    )

    return hourly


def fill_with_mapping(
    frame: pd.DataFrame,
    value_map: pd.Series,
    keys: list[str],
    method: str,
) -> None:
    missing = frame["temperatura_c"].isna()
    if not missing.any():
        return

    lookup = frame.loc[missing, keys].apply(tuple, axis=1).map(value_map)
    fill_mask = missing & lookup.notna()
    frame.loc[fill_mask, "temperatura_c"] = lookup.loc[fill_mask]
    frame.loc[fill_mask, "metodo_imputacion"] = method


def complete_and_impute_zone(zone: pd.DataFrame) -> pd.DataFrame:
    zone = zone.sort_values("ds").copy()
    code = zone["codigo_lugar"].iloc[0]

    observed = zone.loc[zone["temperatura_c"].notna()].copy()
    if observed.empty:
        raise ValueError(f"Cannot impute {code}: no observed temperatures available")

    full_range = pd.date_range(
        observed["ds"].min(),
        observed["ds"].max(),
        freq="h",
    )
    full = (
        zone.set_index("ds")
        .reindex(full_range)
        .rename_axis("ds")
        .reset_index()
    )

    metadata_columns = [
        "codigo_lugar",
        "id_lugar",
        "lugar",
        "nombre_maestro",
        "condicion",
        "latitud",
        "longitud",
    ]
    for column in metadata_columns:
        full[column] = zone[column].dropna().iloc[0]

    full["observaciones_validas"] = full["observaciones_validas"].fillna(0).astype(int)
    full["observaciones_total"] = full["observaciones_total"].fillna(0).astype(int)
    full["temperatura_observada_c"] = full["temperatura_c"]
    full["metodo_imputacion"] = "observado"
    full.loc[full["temperatura_c"].isna(), "metodo_imputacion"] = pd.NA

    full = full.set_index("ds")
    interpolated = full["temperatura_c"].interpolate(
        method="time",
        limit=SHORT_GAP_LIMIT_HOURS,
        limit_area="inside",
    )
    linear_mask = full["temperatura_c"].isna() & interpolated.notna()
    full.loc[linear_mask, "temperatura_c"] = interpolated.loc[linear_mask]
    full.loc[linear_mask, "metodo_imputacion"] = (
        f"interpolacion_temporal_hasta_{SHORT_GAP_LIMIT_HOURS}h"
    )
    full = full.reset_index()

    observed = observed.assign(
        mes=observed["ds"].dt.month,
        dia=observed["ds"].dt.day,
        hora=observed["ds"].dt.hour,
    )
    full = full.assign(
        mes=full["ds"].dt.month,
        dia=full["ds"].dt.day,
        hora=full["ds"].dt.hour,
    )

    climatology_day_hour = observed.groupby(["mes", "dia", "hora"])[
        "temperatura_c"
    ].median()
    climatology_month_hour = observed.groupby(["mes", "hora"])[
        "temperatura_c"
    ].median()
    climatology_hour = observed.groupby(["hora"])["temperatura_c"].median()
    zone_median = observed["temperatura_c"].median()

    fill_with_mapping(
        full,
        climatology_day_hour,
        ["mes", "dia", "hora"],
        "mediana_estacional_mes_dia_hora",
    )
    fill_with_mapping(
        full,
        climatology_month_hour,
        ["mes", "hora"],
        "mediana_estacional_mes_hora",
    )
    fill_with_mapping(full, climatology_hour, ["hora"], "mediana_horaria_zona")

    still_missing = full["temperatura_c"].isna()
    if still_missing.any():
        full.loc[still_missing, "temperatura_c"] = zone_median
        full.loc[still_missing, "metodo_imputacion"] = "mediana_zona"

    if full["temperatura_c"].isna().any():
        raise ValueError(f"Imputation left null temperatures for {code}")

    full["temperatura_c"] = full["temperatura_c"].round(3)
    full["temperatura_observada_c"] = full["temperatura_observada_c"].round(3)
    full["es_imputado"] = full["metodo_imputacion"] != "observado"
    full = full.drop(columns=["mes", "dia", "hora"])

    expected_hours = pd.date_range(full["ds"].min(), full["ds"].max(), freq="h")
    if len(expected_hours) != len(full) or not full["ds"].equals(
        pd.Series(expected_hours, name="ds")
    ):
        raise ValueError(f"Hourly gaps remain after imputation for {code}")

    return full


def build_time_series(hourly: pd.DataFrame, master: pd.DataFrame) -> pd.DataFrame:
    zones: list[pd.DataFrame] = []

    for code in master.sort_values("id")["codigo"]:
        zone = hourly.loc[hourly["codigo_lugar"] == code]
        if zone.empty:
            raise ValueError(f"No hourly data found for maestro place {code}")
        zones.append(complete_and_impute_zone(zone))

    result = pd.concat(zones, ignore_index=True)
    result = result.sort_values(["id_lugar", "ds"]).reset_index(drop=True)

    if result["temperatura_c"].isna().any():
        raise ValueError("Consolidated output contains null temperatures")

    return result


def build_large_gap_report(
    hourly: pd.DataFrame,
    master: pd.DataFrame,
    threshold_hours: int = LARGE_GAP_THRESHOLD_HOURS,
    max_gaps_per_zone: int = LARGE_GAPS_PER_ZONE,
) -> pd.DataFrame:
    reports: list[pd.DataFrame] = []

    for code in master.sort_values("id")["codigo"]:
        zone = hourly.loc[
            (hourly["codigo_lugar"] == code) & (hourly["temperatura_c"].notna())
        ].sort_values("ds")
        if zone.empty:
            continue

        gaps = zone[["codigo_lugar", "id_lugar", "lugar", "ds"]].copy()
        gaps["siguiente_medicion"] = gaps["ds"].shift(-1)
        gaps["gap_horas"] = (
            (gaps["siguiente_medicion"] - gaps["ds"]) / pd.Timedelta(hours=1)
        )
        gaps["horas_sin_medicion"] = gaps["gap_horas"] - 1
        gaps = gaps.loc[gaps["gap_horas"] > threshold_hours].copy()
        if gaps.empty:
            continue

        gaps = gaps.nlargest(max_gaps_per_zone, "gap_horas")
        gaps = gaps.rename(columns={"ds": "ultima_medicion_antes_gap"})
        reports.append(
            gaps[
                [
                    "codigo_lugar",
                    "id_lugar",
                    "lugar",
                    "ultima_medicion_antes_gap",
                    "siguiente_medicion",
                    "gap_horas",
                    "horas_sin_medicion",
                ]
            ]
        )

    if not reports:
        return pd.DataFrame(
            columns=[
                "codigo_lugar",
                "id_lugar",
                "lugar",
                "ultima_medicion_antes_gap",
                "siguiente_medicion",
                "gap_horas",
                "horas_sin_medicion",
            ]
        )

    return pd.concat(reports, ignore_index=True)


def print_large_gap_report(report: pd.DataFrame) -> None:
    print(
        "\nGaps horarios observados mayores a "
        f"{LARGE_GAP_THRESHOLD_HOURS} horas:"
    )
    if report.empty:
        print("No se encontraron gaps mayores a 1 dia.")
        return

    for code, zone in report.groupby("codigo_lugar", sort=False):
        lugar = zone["lugar"].iloc[0]
        print(f"\n{code} - {lugar}")
        for row in zone.itertuples(index=False):
            gap_hours = int(row.gap_horas)
            missing_hours = int(row.horas_sin_medicion)
            print(
                "  "
                f"{row.ultima_medicion_antes_gap} -> {row.siguiente_medicion}: "
                f"{gap_hours} horas entre mediciones "
                f"({missing_hours} horas sin medicion)"
            )


def build_summary(series: pd.DataFrame) -> pd.DataFrame:
    summary = (
        series.groupby(["codigo_lugar", "id_lugar", "lugar"], as_index=False)
        .agg(
            fecha_inicio=("ds", "min"),
            fecha_fin=("ds", "max"),
            horas=("ds", "size"),
            horas_observadas=("es_imputado", lambda values: int((~values).sum())),
            horas_imputadas=("es_imputado", lambda values: int(values.sum())),
            temperatura_min_c=("temperatura_c", "min"),
            temperatura_max_c=("temperatura_c", "max"),
            temperatura_media_c=("temperatura_c", "mean"),
        )
        .sort_values("id_lugar")
    )
    summary["porcentaje_imputado"] = (
        summary["horas_imputadas"] / summary["horas"] * 100
    ).round(2)
    return summary


def write_outputs(series: pd.DataFrame, summary: pd.DataFrame) -> None:
    SILVER_2026_DIR.mkdir(parents=True, exist_ok=True)
    PER_PLACE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    ordered_columns = [
        "codigo_lugar",
        "id_lugar",
        "lugar",
        "nombre_maestro",
        "condicion",
        "latitud",
        "longitud",
        "ds",
        "temperatura_c",
        "temperatura_observada_c",
        "es_imputado",
        "metodo_imputacion",
        "observaciones_validas",
        "observaciones_total",
    ]
    series[ordered_columns].to_csv(CONSOLIDATED_OUTPUT_PATH, index=False)
    summary.to_csv(SUMMARY_OUTPUT_PATH, index=False)

    for code, zone in series.groupby("codigo_lugar", sort=False):
        lugar = zone["lugar"].iloc[0]
        output_path = PER_PLACE_OUTPUT_DIR / f"{code}_{slugify(lugar)}.csv"
        zone[ordered_columns].to_csv(output_path, index=False)


def main() -> None:
    master = read_lugar_master()
    aliases = build_place_aliases(master)

    raw = pd.concat(
        [
            read_historical_temperatures(aliases),
            read_2026_temperatures(aliases),
        ],
        ignore_index=True,
    )

    validate_places(raw, master)
    hourly = aggregate_hourly(raw, master)
    large_gap_report = build_large_gap_report(hourly, master)
    series = build_time_series(hourly, master)
    summary = build_summary(series)
    write_outputs(series, summary)

    print(f"Archivo consolidado: {CONSOLIDATED_OUTPUT_PATH}")
    print(f"Resumen: {SUMMARY_OUTPUT_PATH}")
    print(f"Series por lugar: {PER_PLACE_OUTPUT_DIR}")
    print_large_gap_report(large_gap_report)
    print()
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()

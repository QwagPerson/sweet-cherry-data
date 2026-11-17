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


def read_2026_temperatures(aliases: dict[str, str], path: Path = TEMPERATURES_2026_PATH) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    excel = pd.ExcelFile(path)

    for sheet_name in excel.sheet_names:
        df = pd.read_excel(excel, sheet_name=sheet_name)
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
                "fuente": f"{path.name}::{sheet_name}",
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
    donor_counts: pd.Series | None = None,
    donor_years: pd.Series | None = None,
) -> None:
    missing = frame["temperatura_c"].isna()
    if not missing.any():
        return

    lookup_keys = frame.loc[missing, keys[0]] if len(keys) == 1 else frame.loc[missing, keys].apply(tuple, axis=1)
    lookup = lookup_keys.map(value_map)
    fill_mask = missing & lookup.notna()
    frame.loc[fill_mask, "temperatura_c"] = lookup.loc[fill_mask]
    frame.loc[fill_mask, "metodo_imputacion"] = method
    tuples = frame.loc[fill_mask, keys[0]] if len(keys) == 1 else frame.loc[fill_mask, keys].apply(tuple, axis=1)
    if donor_counts is not None:
        frame.loc[fill_mask, "donantes_metodo_n"] = tuples.map(donor_counts)
    if donor_years is not None:
        frame.loc[fill_mask, "donantes_anios"] = tuples.map(donor_years)


def complete_and_impute_zone(zone: pd.DataFrame, *, climatology_mode: str = "retrospective", cutoff: pd.Timestamp | None = None, start: pd.Timestamp | None = None, end: pd.Timestamp | None = None) -> pd.DataFrame:
    if zone.empty:
        raise ValueError("Cannot reconstruct an empty zone")
    code = zone["codigo_lugar"].iloc[0]
    if climatology_mode not in {"retrospective", "cutoff", "none"}:
        raise ValueError("climatology_mode must be retrospective, cutoff or none")
    if climatology_mode == "cutoff" and cutoff is None:
        raise ValueError("cutoff mode requires a cutoff timestamp")
    if cutoff is not None:
        cutoff = pd.Timestamp(cutoff)
        zone = zone.loc[zone["ds"] <= cutoff].copy()
        if end is not None and pd.Timestamp(end) > cutoff:
            raise ValueError("end cannot exceed cutoff: this is a reconstruction, not a forecast")
        if zone.empty:
            raise ValueError(f"Cannot reconstruct {code}: no observations at or before cutoff")
    zone = zone.sort_values("ds").copy()

    observed = zone.loc[zone["temperatura_c"].notna()].copy()
    if observed.empty:
        raise ValueError(f"Cannot impute {code}: no observed temperatures available")

    full_range = pd.date_range(
        pd.Timestamp(start) if start is not None else observed["ds"].min(),
        pd.Timestamp(end) if end is not None else observed["ds"].max(),
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
    missing = full["temperatura_c"].isna()
    groups = missing.ne(missing.shift()).cumsum()
    gap_lengths = missing.groupby(groups).transform("sum")
    full["hueco_original_horas"] = gap_lengths.where(missing, 0).astype(int)
    interpolated = full["temperatura_c"].interpolate(
        method="time",
        limit_area="inside",
    )
    linear_mask = missing & gap_lengths.le(SHORT_GAP_LIMIT_HOURS) & interpolated.notna()
    full.loc[linear_mask, "temperatura_c"] = interpolated.loc[linear_mask]
    full.loc[linear_mask, "metodo_imputacion"] = (
        f"interpolacion_temporal_hasta_{SHORT_GAP_LIMIT_HOURS}h"
    )
    observed_times = pd.Series(full.index, index=full.index).where(~missing)
    full.loc[linear_mask, "interpolacion_desde"] = observed_times.ffill().loc[linear_mask]
    full.loc[linear_mask, "interpolacion_hasta"] = observed_times.bfill().loc[linear_mask]
    full = full.reset_index()

    observed = observed.assign(
        mes=observed["ds"].dt.month,
        dia=observed["ds"].dt.day,
        hora=observed["ds"].dt.hour,
        anio=observed["ds"].dt.year,
    )
    full = full.assign(
        mes=full["ds"].dt.month,
        dia=full["ds"].dt.day,
        hora=full["ds"].dt.hour,
    )

    # Only original observations are donors; no synthetic temperature trains climatology.
    full["modo_climatologia"] = climatology_mode
    full["corte_climatologia"] = cutoff if cutoff is not None else pd.NaT
    full["donantes_desde"] = observed["ds"].min() if climatology_mode != "none" else pd.NaT
    full["donantes_hasta"] = observed["ds"].max() if climatology_mode != "none" else pd.NaT
    full["donantes_total"] = len(observed) if climatology_mode != "none" else 0
    full["donantes_metodo_n"] = 0
    full["donantes_anios"] = ""
    if climatology_mode == "none":
        full["metodo_imputacion"] = full["metodo_imputacion"].fillna("faltante")
        full["es_imputado"] = ~full["metodo_imputacion"].isin(["observado", "faltante"])
        full["tipo_dato"] = full["metodo_imputacion"].map(lambda x: "observado" if x == "observado" else "faltante" if x == "faltante" else "interpolado")
        return full.drop(columns=["mes", "dia", "hora"])

    climatology_day_hour = observed.groupby(["mes", "dia", "hora"])[
        "temperatura_c"
    ].median()
    climatology_month_hour = observed.groupby(["mes", "hora"])[
        "temperatura_c"
    ].median()
    climatology_hour = observed.groupby(["hora"])["temperatura_c"].median()
    zone_median = observed["temperatura_c"].median()

    def donor_maps(keys):
        grouped = observed.groupby(keys)
        return grouped.size(), grouped["anio"].agg(lambda v: "|".join(str(y) for y in sorted(v.unique())))

    fill_with_mapping(
        full,
        climatology_day_hour,
        ["mes", "dia", "hora"],
        "mediana_estacional_mes_dia_hora",
        *donor_maps(["mes", "dia", "hora"]),
    )
    fill_with_mapping(
        full,
        climatology_month_hour,
        ["mes", "hora"],
        "mediana_estacional_mes_hora",
        *donor_maps(["mes", "hora"]),
    )
    fill_with_mapping(full, climatology_hour, ["hora"], "mediana_horaria_zona", *donor_maps(["hora"]))

    still_missing = full["temperatura_c"].isna()
    if still_missing.any():
        full.loc[still_missing, "temperatura_c"] = zone_median
        full.loc[still_missing, "metodo_imputacion"] = "mediana_zona"
        full.loc[still_missing, "donantes_metodo_n"] = len(observed)
        full.loc[still_missing, "donantes_anios"] = "|".join(str(y) for y in sorted(observed.anio.unique()))

    if full["temperatura_c"].isna().any():
        raise ValueError(f"Imputation left null temperatures for {code}")

    full["temperatura_c"] = full["temperatura_c"].round(3)
    full["temperatura_observada_c"] = full["temperatura_observada_c"].round(3)
    full["es_imputado"] = full["metodo_imputacion"] != "observado"
    full["tipo_dato"] = full["metodo_imputacion"].map(lambda x: "observado" if x == "observado" else "interpolado" if x.startswith("interpolacion") else "climatologia")
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
            horas_observadas=("metodo_imputacion", lambda values: int(values.eq("observado").sum())),
            horas_interpoladas=("metodo_imputacion", lambda values: int(values.str.startswith("interpolacion").sum())),
            horas_climatologia=("metodo_imputacion", lambda values: int(values.str.startswith("mediana").sum())),
            horas_faltantes=("temperatura_c", lambda values: int(values.isna().sum())),
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
    from audited import main as audited_main
    audited_main()


if __name__ == "__main__":
    main()

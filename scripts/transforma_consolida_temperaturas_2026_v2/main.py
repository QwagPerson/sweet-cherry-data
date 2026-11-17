"""Consolidate historical temperatures with V2 taking precedence per zone/hour."""
from pathlib import Path
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from transforma_consolida_temperaturas_historico_2026 import main as base

V2_PATH = base.BRONZE_2026_DIR / "Temperaturas 2026 V2.xlsx"


def merge_latest(previous: pd.DataFrame, latest: pd.DataFrame) -> pd.DataFrame:
    """Keep older observations wherever V2 has no valid replacement."""
    latest = latest.copy()
    unknown = latest.loc[latest["codigo_lugar"].isna(), "lugar_raw"].dropna().unique()
    if len(unknown):
        raise ValueError(f"Zonas V2 sin equivalencia en el maestro: {unknown.tolist()}")
    valid = latest["ds"].notna() & np.isfinite(latest["temperatura_c"]) & latest["codigo_lugar"].notna()
    print(f"V2: {len(latest)} filas; {int((~valid).sum())} filas inválidas descartadas")
    latest = latest.loc[valid].copy()
    if latest.empty or not latest["ds"].dt.year.eq(2026).all():
        raise ValueError("V2 debe contener mediciones válidas exclusivamente de 2026")
    latest["ds"] = latest["ds"].dt.floor("h")
    previous = previous.copy()
    previous["ds"] = previous["ds"].dt.floor("h")
    keys = ["codigo_lugar", "ds"]
    replacement_keys = pd.MultiIndex.from_frame(latest[keys])
    replaced = pd.MultiIndex.from_frame(previous[keys]).isin(replacement_keys)
    print(f"Filas anteriores reemplazadas por V2: {int(replaced.sum())}")
    return pd.concat([previous.loc[~replaced], latest], ignore_index=True)


def main() -> None:
    # Both entry points now use the same reviewed source policy and safe output path.
    sys.path.insert(0, str(Path(base.__file__).parent))
    from audited import main as audited_main
    audited_main()


if __name__ == "__main__":
    main()

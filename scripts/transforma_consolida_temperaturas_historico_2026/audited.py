"""Combine all bronze temperature sources; review by default, promote locally explicitly."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
import main as base

KEYS = ["codigo_lugar", "ds"]
DEFAULT_OUTPUT = base.PROJECT_ROOT.parent / "output" / "temperature_integration_all_years" / "review"
FIA_2025 = base.BRONZE_2025_DIR / "FIA 2025 - Temperatura campos.xlsx"
V2 = base.BRONZE_2026_DIR / "Temperaturas 2026 V2.xlsx"
FIA_2024 = base.PROJECT_ROOT / "data/bronze/2024/FIA - Temperaturas 2024.xlsx"

def read_source(path: Path, aliases: dict, sheet_names=None) -> pd.DataFrame:
    frames = []
    excel = pd.ExcelFile(path)
    for sheet in sheet_names if sheet_names is not None else excel.sheet_names:
        d = pd.read_excel(excel, sheet_name=sheet)
        cols = {base.normalize_text(c): c for c in d.columns}
        if not {"lugar", "fecha", "hora"}.issubset(cols):
            continue
        temp = next((cols[k] for k in ["temperatura", "t c", "t"] if k in cols), None)
        if temp is None:
            raise ValueError(f"Temperature column missing: {path.name}::{sheet}")
        f = pd.DataFrame({
            "codigo_lugar": d[cols["lugar"]].map(lambda x: base.resolve_place_code(x, aliases)),
            "lugar_raw": d[cols["lugar"]],
            "variedad_raw": d[cols["variedad"]] if "variedad" in cols else "",
            "ds_original": base.combine_date_and_hour(d[cols["fecha"]], d[cols["hora"]]),
            "temperatura_raw": d[temp],
            "temperatura_c": pd.to_numeric(d[temp], errors="coerce"),
            "fuente": path.name, "hoja": sheet,
            "fila_excel": np.arange(2, len(d)+2),
            "hora_raw": d[cols["hora"]].astype(str),
        })
        f["ds"] = f.ds_original.dt.floor("h")
        # Broad screening bounds, not a claim of sensor calibration.
        f["rechazo"] = np.select([
            f.codigo_lugar.isna(), f.ds.isna(), ~np.isfinite(f.temperatura_c),
            ~f.temperatura_c.between(-30,60),
            f.ds.dt.year.ne(2025) if path == FIA_2025 else pd.Series(False,index=f.index),
            f.ds.dt.year.ne(2024) if path == FIA_2024 else pd.Series(False,index=f.index),
            f.ds.dt.year.ne(2026) if path == V2 else pd.Series(False,index=f.index),
        ], ["campo_sin_mapear", "fecha_hora_invalida", "temperatura_no_numerica", "fuera_rango_revision", "anio_no_2025", "anio_no_2024", "anio_no_2026"], default="")
        f["id_registro"] = path.name + "::" + sheet + "::" + f.fila_excel.astype(str)
        frames.append(f)
    return pd.concat(frames, ignore_index=True)

def source_hourly(raw: pd.DataFrame) -> pd.DataFrame:
    valid = raw.loc[raw.rechazo.eq("")].copy()
    if valid.fuente.eq(FIA_2024.name).all():
        # Global is the canonical sheet; detail sheets can supply missing hours.
        # Mirrored sheets must not add weight or average conflicting copies.
        canonical = valid.loc[valid.hoja.eq("Global")]
        detail = valid.loc[~valid.hoja.eq("Global")]
        missing = ~pd.MultiIndex.from_frame(detail[KEYS]).isin(pd.MultiIndex.from_frame(canonical[KEYS]))
        valid = pd.concat([canonical, detail.loc[missing]], ignore_index=True)
    # Repeated copies at the same timestamp/value do not increase their weight.
    unique = valid if valid.fuente.eq(base.HISTORICAL_TEMPERATURES_PATH.name).all() else valid.drop_duplicates(["codigo_lugar", "ds_original", "temperatura_c"])
    result = unique.groupby(KEYS, as_index=False).agg(
        temperatura_c=("temperatura_c", "mean"),
        observaciones_validas=("temperatura_c", "size"),
        temperatura_min_fuente=("temperatura_c", "min"),
        temperatura_max_fuente=("temperatura_c", "max"),
    )
    provenance = valid.groupby(KEYS, as_index=False).agg(
        observaciones_total=("id_registro", "size"),
        registros_fuente=("id_registro", lambda v: json.dumps(v.tolist(), ensure_ascii=False)),
        fuente=("fuente", "first"),
        hojas_fuente=("hoja", lambda v: "|".join(sorted(set(v)))),
    )
    return result.merge(provenance, on=KEYS)

def merge_sources(history, older, latest, fia, master, *, fia_2024=None):
    """Existing historical observations prevail; FIA fills uncovered hours only.

    V2 supersedes V1 where valid, as in the existing V2 process. Conflicting
    sensor/site mappings are retained in the audit and never averaged across files.
    """
    chosen = history.copy()
    inputs = [(older, True), (latest, True), (fia, False)]
    if fia_2024 is not None:
        inputs.append((fia_2024, False))
    for incoming, replace in inputs:
        match = pd.MultiIndex.from_frame(chosen[KEYS]).isin(pd.MultiIndex.from_frame(incoming[KEYS]))
        if replace:
            chosen = chosen.loc[~match]
        else:
            incoming = incoming.loc[~pd.MultiIndex.from_frame(incoming[KEYS]).isin(pd.MultiIndex.from_frame(chosen[KEYS]))]
        chosen = pd.concat([chosen, incoming], ignore_index=True)
    return chosen.merge(master[["codigo", "id", "lugar", "nombre", "condicion", "latitud", "longitud"]], left_on="codigo_lugar", right_on="codigo").drop(columns="codigo").rename(columns={"id":"id_lugar", "nombre":"nombre_maestro"})

def generate(hourly, master, *, mode="retrospective", cutoff=None, start=None, end=None):
    start = hourly.ds.min() if start is None else pd.Timestamp(start)
    if end is None:
        end = min(hourly.ds.max(), pd.Timestamp(cutoff)) if cutoff is not None else hourly.ds.max()
    else:
        end = pd.Timestamp(end)
    frames=[]
    for code in master.sort_values("id").codigo:
        zone=hourly.loc[hourly.codigo_lugar.eq(code)]
        frames.append(base.complete_and_impute_zone(zone, climatology_mode=mode, cutoff=cutoff, start=start, end=end))
    return pd.concat(frames,ignore_index=True).sort_values(["id_lugar","ds"])

def write_review(series, directory):
    directory=Path(directory)
    directory.mkdir(parents=True,exist_ok=True)
    series.to_csv(directory/"temperaturas_horarias_por_lugar.csv",index=False)
    base.build_summary(series).to_csv(directory/"temperaturas_horarias_por_lugar_resumen.csv",index=False)
    per=directory/"temperaturas_horarias_por_lugar"
    per.mkdir(exist_ok=True)
    for code,d in series.groupby("codigo_lugar"):
        d.to_csv(per/f"{code}_{base.slugify(d.lugar.iloc[0])}.csv",index=False)

def load_sources(aliases):
    specs=[(base.HISTORICAL_TEMPERATURES_PATH,["CONSOLIDADO TEMPERATURAS"]),(base.TEMPERATURES_2026_PATH,None),(V2,None),(FIA_2025,None),(FIA_2024,None)]
    discovered = {p.resolve() for p in (base.PROJECT_ROOT / "data/bronze").rglob("*.xlsx") if "temperatura" in base.normalize_text(p.stem)}
    configured = {p.resolve() for p, _ in specs}
    if discovered != configured:
        raise ValueError(f"Temperature source inventory changed; configure these files before consolidating: {discovered ^ configured}")
    aliases_2024={**aliases, "tds":"TEM", "teno prado":"TEP", "santa magda":"NIC"}
    return [read_source(p,aliases_2024 if p==FIA_2024 else aliases,s) for p,s in specs]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir",type=Path,default=DEFAULT_OUTPUT)
    parser.add_argument("--promote-local",action="store_true",help="Write the validated consolidation to local silver (never deploy remotely)")
    parser.add_argument("--climatology-mode",choices=["retrospective","cutoff","none"],default="retrospective")
    parser.add_argument("--cutoff",type=pd.Timestamp)
    parser.add_argument("--start",type=pd.Timestamp)
    parser.add_argument("--end",type=pd.Timestamp)
    args=parser.parse_args()
    if args.promote_local:
        if args.output_dir != DEFAULT_OUTPUT:
            parser.error("--promote-local selects the canonical silver directory; omit --output-dir")
        if args.climatology_mode != "retrospective" or args.cutoff is not None:
            parser.error("Canonical local silver uses retrospective reconstruction; keep cutoff/none as separate review outputs")
        args.output_dir=base.SILVER_2026_DIR
    elif args.output_dir.resolve().is_relative_to((base.PROJECT_ROOT/"data").resolve()):
        parser.error("Review outputs must be outside data/. Review before promoting to production.")
    master=base.read_lugar_master()
    sources=load_sources(base.build_place_aliases(master))
    hourly=merge_sources(*(source_hourly(d) for d in sources[:4]),master, fia_2024=source_hourly(sources[4]))
    series=generate(hourly,master,mode=args.climatology_mode,cutoff=args.cutoff,start=args.start,end=args.end)
    write_review(series,args.output_dir)
    raw=pd.concat(sources,ignore_index=True)
    raw.to_csv(args.output_dir/"registros_fuentes.csv.gz",index=False)
    raw.loc[raw.rechazo.ne("")].to_csv(args.output_dir/"rechazos.csv",index=False)
    hourly.to_csv(args.output_dir/"observaciones_seleccionadas.csv.gz",index=False)
    manifest=[{"path":str(p),"sha256":hashlib.sha256(p.read_bytes()).hexdigest()} for p in [base.HISTORICAL_TEMPERATURES_PATH,base.TEMPERATURES_2026_PATH,V2,FIA_2025,FIA_2024]]
    (args.output_dir/"manifest.json").write_text(json.dumps({"sources":manifest,"mode":args.climatology_mode,"cutoff":str(args.cutoff),"timezone":"hora local nominal sin zona declarada; sin conversion UTC", "units":"Celsius; explicit in FIA 2025, assumed from project in other files"},indent=2,ensure_ascii=False),encoding="utf-8")
    print(base.build_summary(series).to_string(index=False))

if __name__ == "__main__":
    main()

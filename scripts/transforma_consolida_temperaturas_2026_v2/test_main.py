import importlib.util
from pathlib import Path

import pandas as pd
import pytest

spec = importlib.util.spec_from_file_location("temperatures_v2", Path(__file__).with_name("main.py"))
v2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v2)


def frame(rows):
    result = pd.DataFrame(rows, columns=["codigo_lugar", "lugar_raw", "ds", "temperatura_c", "fuente"])
    result["ds"] = pd.to_datetime(result["ds"])
    return result


def test_v2_replaces_overlaps_preserves_history_other_zones_and_invalid_fallback():
    old = frame([
        ("MEL", "Melipilla", "2025-01-01", 20., "old"),
        ("MEL", "Melipilla", "2026-01-01", 20., "old"),
        ("MEL", "Melipilla", "2026-01-02", 21., "old"),
        ("NIC", "Los Niches", "2026-01-01", 10., "old"),
    ])
    new = frame([
        ("MEL", "Melipilla", "2026-01-01", 25., "v2"),
        ("MEL", "Melipilla", "2026-01-02", float('nan'), "v2"),
        ("MEL", "Melipilla", "2026-01-03", 26., "v2"),
    ])
    merged = v2.merge_latest(old, new)
    assert len(merged) == 5
    assert merged["temperatura_c"].tolist() == [20., 21., 10., 25., 26.]
    assert not merged.duplicated(["codigo_lugar", "ds"]).any()


def test_unknown_zone_is_rejected():
    new = frame([(None, "Unknown", "2026-01-01", 10., "v2")])
    with pytest.raises(ValueError, match="sin equivalencia"):
        v2.merge_latest(new.iloc[:0], new)


def test_2026_zone_names_match_master():
    aliases = v2.base.build_place_aliases(v2.base.read_lugar_master())
    expected = {"Teno Montaña": "TEM", "Teno Oriente": "TEO", "Teno Poniente": "TEP", "Melipilla": "MEL", "Sarmiento": "SAR", "Viluco": "VIL"}
    for name, code in expected.items():
        assert v2.base.resolve_place_code(name, aliases) == code

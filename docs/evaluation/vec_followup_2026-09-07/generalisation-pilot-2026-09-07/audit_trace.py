"""Validate the canonical working-day input before any outcome is observed."""
import csv
import gzip
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent
CODE = BASE / "vec_env-state-delay-run"
SOURCE = CODE / "eval/data/manchester_workingday"
TRACE = SOURCE / "trace_wd_am_wdrsu.npz"
LEGACY = BASE / "tos-data-full/traces/trace_wd_am_fullrsu.npz"
FCD = SOURCE / "fcd_wd_am_0800_1100.xml.gz"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    declared = dict((line.split()[1], line.split()[0])
                    for line in (SOURCE / "SHA256SUMS").read_text().splitlines())
    assert sha(TRACE) == declared[TRACE.name], "Published trace checksum differs"
    assert sha(FCD) == declared[FCD.name], "Published source FCD checksum differs"
    with np.load(TRACE, allow_pickle=False) as data:
        a = dict(data)
    shape = (10800, 215)
    assert a["pos_x"].shape == a["pos_y"].shape == a["speed"].shape == shape
    assert a["mask"].shape == a["enter"].shape == shape
    assert a["mask"].dtype == a["enter"].dtype == np.bool_
    assert a["rsu_xy"].shape == (9, 2)
    assert int(a["T"]) == shape[0] and int(a["maxN"]) == shape[1]
    assert float(a["dt"]) == 1 and int(a["sumo_seed"]) == 42
    for name, array in a.items():
        if array.dtype.kind in "biuf":
            assert np.isfinite(array).all(), name
    assert np.array_equal(a["times"], np.arange(28800, 39600, dtype=np.float32))
    assert np.all(a["speed"][a["mask"]] >= 0)
    assert not np.any(a["enter"] & ~a["mask"])
    with np.load(LEGACY, allow_pickle=False) as old:
        common = sorted(old.files)
        legacy_equal = {name: bool(np.array_equal(a[name], old[name])) for name in common}
        assert np.array_equal(a["mask"].sum(axis=1), old["mask"].sum(axis=1))
    # Legacy occupancy uses the old nondeterministic slot assignment and must
    # not be joined to this trace. Reconstruct visits from the shipped FCD.
    slots, free, previous, open_visits, rows = {}, [], set(), {}, []
    next_slot = 0
    step = 0
    with gzip.open(FCD, "rb") as handle:
        for _, elem in ET.iterparse(handle, events=("end",)):
            if elem.tag != "timestep":
                continue
            assert float(elem.get("time")) == a["times"][step]
            vehicles = {v.get("id"): (float(v.get("x")), float(v.get("y")), float(v.get("speed")))
                        for v in elem.findall("vehicle")}
            current = set(vehicles)
            for vid in sorted(previous-current):
                slot, first = open_visits.pop(vid)
                rows.append((vid, slot, first, step-1))
                free.append(slots.pop(vid))
            for vid in sorted(current-previous):
                if free:
                    slot = free.pop()
                else:
                    slot = next_slot
                    next_slot += 1
                slots[vid] = slot
                open_visits[vid] = (slot, step)
            xyz = np.zeros((shape[1], 3), dtype=np.float32)
            mask = np.zeros(shape[1], dtype=bool)
            enters = np.zeros(shape[1], dtype=bool)
            for vid, slot in slots.items():
                xyz[slot] = vehicles[vid]
                mask[slot] = True
                enters[slot] = vid not in previous
            for index, name in enumerate(("pos_x", "pos_y", "speed")):
                assert np.array_equal(xyz[:, index], a[name][step]), (name, step)
            assert np.array_equal(mask, a["mask"][step]), ("mask", step)
            assert np.array_equal(enters, a["enter"][step]), ("enter", step)
            previous = current
            step += 1
            elem.clear()
    assert step == shape[0] and next_slot == shape[1]
    for vid, (slot, first) in open_visits.items():
        rows.append((vid, slot, first, step-1))
    rows.sort(key=lambda row: (row[2], row[1]))
    occupancy = ROOT / "occupancy_wd_am_canonical.csv"
    with occupancy.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(("sumo_vehicle_id", "slot", "t_enter", "t_exit"))
        writer.writerows(rows)
    assert sum(row[3]-row[2]+1 for row in rows) == int(a["mask"].sum())
    visit_count = len(rows)
    xy = np.stack([a["pos_x"][a["mask"]], a["pos_y"][a["mask"]]], axis=-1)
    nearest_sq = np.full(len(xy), np.inf)
    for rsu in a["rsu_xy"]:
        nearest_sq = np.minimum(nearest_sq, np.sum((xy.astype(np.float64)-rsu)**2, axis=-1))
    coverage = float(np.mean(nearest_sq <= 500**2))
    assert coverage == 1, "Some vehicle positions lack the documented 500m geometric coverage"
    active = a["mask"].sum(axis=1)
    turnover = int(np.count_nonzero(a["enter"][1:] & a["mask"][:-1]))
    receipt = {
        "status": "passed", "selection": "Full canonical working-day morning window; chosen before scheduler outcomes",
        "trace": {"path": str(TRACE), "sha256": sha(TRACE)},
        "date": "2024-10-15", "local_window": "08:00–11:00", "steps": shape[0],
        "maxN": shape[1], "rsus": 9, "sumo_seed": 42,
        "active_vehicle_seconds": int(active.sum()),
        "active_vehicles": {"minimum": int(active.min()), "maximum": int(active.max()), "mean": float(active.mean())},
        "geometric_coverage_at_500m": coverage,
        "maximum_nearest_rsu_distance_m": float(np.sqrt(nearest_sq.max())),
        "rsu_xy": a["rsu_xy"].tolist(), "visit_count": visit_count,
        "immediate_slot_handovers": turnover,
        "fcd_positions_speed_mask_enter_timestamps": "exact_all_10800_rows",
        "canonical_occupancy": {"path": str(occupancy), "sha256": sha(occupancy)},
        "legacy_comparison": {"per_array_equal": legacy_equal, "active_counts_per_second": "exact", "path": str(LEGACY), "sha256": sha(LEGACY),
                              "note": "Legacy slot order differs; do not use its occupancy table with canonical arrays."},
        "sources": {str(p): sha(p) for p in (SOURCE / "SHA256SUMS", CODE / "eval/data/README.md", FCD,
                   BASE / "tos-data-full/traces/PROVENANCE.md")},
        "interpretation": "Same-region scenario transfer, not independent geography or traffic-only intervention. Nine RSUs and per-visit vehicle-queue reset differ from the old incident trace; both new comparison arms share them. Geometric coverage is not a guaranteed radio admission rate.",
    }
    (ROOT / "input_validation.json").write_text(json.dumps(receipt, indent=2, sort_keys=True)+"\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()

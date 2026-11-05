"""Reproducible datasets built from the instructor's unchanged simulator."""
from __future__ import annotations
import argparse
import csv
import random
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from simulator.core import make_robot, step_robot


def generate_rows(fleets: int = 64, samples_per_fleet: int = 512, robots: int = 8, seed: int = 606, scenario_shift: bool = False) -> list[dict]:
    if min(fleets, samples_per_fleet, robots) < 1:
        raise ValueError("fleets, samples_per_fleet y robots deben ser positivos")
    rows = []
    for fleet in range(fleets):
        rng = random.Random(seed + fleet * 1009)
        shift_rng = random.Random(seed + fleet * 1009 + 700001)
        states = [make_robot(i + 1, rng) for i in range(robots)]
        fleet_id = f"S{seed}-F{fleet + 1:03d}"
        for step in range(samples_per_fleet):
            sample, status = step_robot(states[step % robots], rng)
            sample["robot_id"] = f"{fleet_id}-{sample['robot_id']}"
            sample["timestamp"] = 1700000000.0 + fleet * 10000 + step // robots
            if scenario_shift:
                sample["motor_temp"] += shift_rng.gauss(0, 0.75)
                sample["vibration"] = max(0, sample["vibration"] * 1.02)
                sample["motor_current"] *= 0.98
            rows.append({"fleet_id": fleet_id, **sample, "status": status})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fleets", type=int, default=64)
    parser.add_argument("--samples-per-fleet", type=int, default=512)
    parser.add_argument("--robots", type=int, default=8)
    parser.add_argument("--seed", type=int, default=606)
    parser.add_argument("--output", default="data/training.csv")
    args = parser.parse_args()
    rows = generate_rows(args.fleets, args.samples_per_fleet, args.robots, args.seed)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} muestras de {args.fleets} flotas guardadas en {path}")


if __name__ == "__main__":
    main()

"""A bounded scenario for the browser client, using the original fleet simulator."""
import random

from simulator.core import make_robot, step_robot


def make_demo_scenario() -> dict:
    rng = random.Random(606)
    robots = [make_robot(index, rng) for index in range(1, 7)]
    frames = []
    for _ in range(40):
        frame = []
        for robot in robots:
            sample, _ = step_robot(robot, rng, dt=3.0)
            frame.append(sample)
        frames.append(frame)
    return {"interval_seconds": 3, "duration_seconds": 120, "frames": frames}

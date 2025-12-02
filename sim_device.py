from multiprocessing import Array
import yaml, pathlib, random

CFG = yaml.safe_load(pathlib.Path("device.yaml").read_text())
ai = [50.0, 25.0]  # tank_level, room_temp

# Shared bo array of 10 ints
bo = Array('i', [0]*10)

p = CFG["process"]["tank"]
dt = CFG["process"]["dt_ms"]/1000
sp = p["setpoint"]

def step():
    ai[0] = max(0, min(100, ai[0]
             + (p["fill_rate"] if bo[0] else 0)
             - (p["drain_rate"] if bo[1] else 0)
             - p["leak_rate"]
             + random.uniform(-p["noise"], p["noise"])))

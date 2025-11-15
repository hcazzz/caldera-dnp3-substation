import time, random, yaml, pathlib
CFG = yaml.safe_load(pathlib.Path("device.yaml").read_text())
ai = [50.0, 25.0]      # tank_level, room_temp
bo = [0, 0]            # fill_valve, drain_valve
p  = CFG["process"]["tank"]; dt = CFG["process"]["dt_ms"]/1000; sp = p["setpoint"]

def step():
    ai[0] = max(0, min(100, ai[0]
             + (p["fill_rate"] if bo[0] else 0)
             - (p["drain_rate"] if bo[1] else 0)
             -  p["leak_rate"]
             +  random.uniform(-p["noise"], p["noise"])))

if __name__ == "__main__":
    import time
    while True:
        step()
        print(f"tank={ai[0]:.1f} | fill={bo[0]} drain={bo[1]}")
        time.sleep(dt)
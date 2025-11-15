# viz.py
import matplotlib
matplotlib.use("TkAgg")          # must be BEFORE pyplot
import time
import matplotlib.pyplot as plt
from collections import deque
from sim_device import ai, bo, dt, step   # note: we import step so this process advances the sim

plt.ion()
fig, ax = plt.subplots()
ax.set_title("Tank Level (AI0)")
ax.set_xlabel("time (s)")
ax.set_ylabel("level")
t0 = time.perf_counter()
T, L = deque(maxlen=1200), deque(maxlen=1200)
(line,) = ax.plot([], [], lw=2)

try:
    while True:
        step()                      # advance the simulation in THIS process
        now = time.perf_counter() - t0
        T.append(now); L.append(ai[0])
        line.set_data(T, L)
        ax.relim(); ax.autoscale_view()
        fig.canvas.draw_idle(); fig.canvas.flush_events()
        time.sleep(dt)              # throttle to sim timestep
except KeyboardInterrupt:
    pass

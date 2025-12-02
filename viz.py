import threading
import time
import tkinter as tk
from collections import deque
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# --- Import simulation device ---
from sim_device import ai, bo, step, dt as sim_dt
import yaml

# --- Config ---
cfg_path = Path("device.yaml")
cfg = yaml.safe_load(cfg_path.read_text()) if cfg_path.exists() else {}
dt_seconds = float(sim_dt) if sim_dt is not None else cfg.get("process", {}).get("dt_ms", 200) / 1000.0

# --- Substation parameters ---
NOMINAL_VOLTAGE = 1.0          # normalized bus voltage (1.0 = nominal)
OVERCURRENT_THRESHOLD = 0.9    # normalized line current threshold for alarm

# --- Plot buffers ---
MAX_POINTS = 300
voltage_history = deque(maxlen=MAX_POINTS)
current_history = deque(maxlen=MAX_POINTS)
breaker1_history = deque(maxlen=MAX_POINTS)
breaker2_history = deque(maxlen=MAX_POINTS)
alarm_history = deque(maxlen=MAX_POINTS)
time_history = deque(maxlen=MAX_POINTS)
start_time = time.time()

def start(shared_bo):
    """Function to start the GUI in a separate process"""
    sample_func = create_sample_function(shared_bo)
    vis = SubstationVisualizer(dt_seconds, sample_func)
    vis.root.mainloop()  # launch Tkinter mainloop
    
def create_sample_function(shared_bo):
    """Return a function that updates bus voltage, line current, and alarm."""
    def sample_substation_step():
        t = time.time() - start_time
        time_history.append(t)

        # Bus voltage: live if either breaker closed
        bus_voltage = 1.0 if shared_bo[0] or shared_bo[1] else 0.0
        ai[0] = bus_voltage

        # Line current: sum of breakers with some small fluctuation
        line_current = 0.5 * (shared_bo[0] + shared_bo[1]) + 0.05 * (time.time() % 10)
        ai[1] = line_current

        # Overcurrent alarm
        if line_current > OVERCURRENT_THRESHOLD:
            shared_bo[2] = 1
        else:
            shared_bo[2] = 0

        # Record histories for plotting
        voltage_history.append(bus_voltage)
        current_history.append(line_current)
        breaker1_history.append(shared_bo[0])
        breaker2_history.append(shared_bo[1])
        alarm_history.append(shared_bo[2])

        # Debug print
        print(f"[substation] Voltage={bus_voltage:.2f}, Current={line_current:.2f}, "
              f"Breaker1={shared_bo[0]}, Breaker2={shared_bo[1]}, Alarm={shared_bo[2]}")
    return sample_substation_step

# --- GUI / plotting ---
class SubstationVisualizer:
    def __init__(self, dt, sample_function):
        self.root = tk.Tk()
        self.root.title("Electric Substation Visualizer")
        self.root.geometry("1000x700")

        self.sample_function = sample_function
        self.running = True
        self.dt = dt

        # Matplotlib figure
        self.fig, (self.ax_voltage, self.ax_current, self.ax_breakers) = plt.subplots(3, 1, figsize=(8, 10), sharex=True)
        self.fig.tight_layout(pad=4.0)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Controls
        ctrl = tk.Frame(self.root)
        ctrl.pack(fill=tk.X)
        self.pause_btn = tk.Button(ctrl, text="Pause", command=self.toggle_pause)
        self.pause_btn.pack(side=tk.LEFT, padx=5, pady=5)
        self.reset_btn = tk.Button(ctrl, text="Reset Plot", command=self.reset_plot)
        self.reset_btn.pack(side=tk.LEFT, padx=5, pady=5)

        # Start background thread
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def toggle_pause(self):
        self.running = not self.running
        self.pause_btn.config(text="Pause" if self.running else "Resume")

    def reset_plot(self):
        time_history.clear()
        voltage_history.clear()
        current_history.clear()
        breaker1_history.clear()
        breaker2_history.clear()
        alarm_history.clear()

    def _draw(self):
        # Voltage
        self.ax_voltage.clear()
        self.ax_voltage.plot(time_history, voltage_history, label="Bus Voltage", color="blue")
        self.ax_voltage.set_ylim(0, 1.2)
        self.ax_voltage.set_ylabel("Voltage (p.u.)")
        self.ax_voltage.legend()
        self.ax_voltage.grid(True)

        # Line current
        self.ax_current.clear()
        self.ax_current.plot(time_history, current_history, label="Line Current", color="green")
        self.ax_current.axhline(OVERCURRENT_THRESHOLD, linestyle="--", color="red", label="Overcurrent Threshold")
        self.ax_current.set_ylim(0, 1.2)
        self.ax_current.set_ylabel("Current (p.u.)")
        self.ax_current.legend()
        self.ax_current.grid(True)

        # Breakers and alarm
        self.ax_breakers.clear()
        self.ax_breakers.step(time_history, breaker1_history, where="post", label="Breaker 1")
        self.ax_breakers.step(time_history, breaker2_history, where="post", label="Breaker 2")
        self.ax_breakers.step(time_history, alarm_history, where="post", label="Overcurrent Alarm")
        self.ax_breakers.set_ylim(-0.1, 1.2)
        self.ax_breakers.set_ylabel("State")
        self.ax_breakers.set_xlabel("Time (s)")
        self.ax_breakers.legend()
        self.ax_breakers.grid(True)

        self.canvas.draw_idle()

    def _run_loop(self):
        while True:
            if self.running:
                try:
                    self.sample_function()
                    self._draw()
                except Exception as e:
                    print(f"[vis] update error: {e}")
            time.sleep(self.dt)

if __name__ == "__main__":
    from multiprocessing import Array

    shared_bo = Array('i', 10)  # 10-element shared array for breakers/alarms
    sample_func = create_sample_function(shared_bo)
    vis = SubstationVisualizer(dt_seconds, sample_func)
    tk.mainloop()

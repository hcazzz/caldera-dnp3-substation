from multiprocessing import Array, Process
from sim_device import ai, bo
import outstation_bridge
import viz

if __name__ == "__main__":
    # Create shared bo array
    shared_bo = Array('i', 10)  # shared across processes

    # Start DNP3 bridge
    p_bridge = Process(target=outstation_bridge.start, args=(shared_bo,))
    p_bridge.start()

    # Start GUI/Visualizer
    p_gui = Process(target=viz.start, args=(shared_bo,))
    p_gui.start()

    # Wait for both
    p_bridge.join()
    p_gui.join()

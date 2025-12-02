#!/usr/bin/env python3
import time, yaml, pathlib
from pydnp3 import asiodnp3, opendnp3, asiopal, openpal
from sim_device import ai, step, dt
from pydnp3.opendnp3 import (
    ICommandHandler,
    ControlRelayOutputBlock,
    CommandStatus,
    BinaryOutputStatus,
)

def start(shared_bo):
    """Start the DNP3 outstation bridge using the shared bo array."""
    bo = shared_bo  # use the shared array passed as argument

    # ---------- Command handler ----------
    class SimCommandHandler(opendnp3.ICommandHandler):
        def __init__(self):
            super().__init__()
            self.ost = None

        def Start(self): pass
        def End(self): pass

        def Select(self, cmd, idx):
            if isinstance(cmd, ControlRelayOutputBlock) and idx in range(10):
                return CommandStatus.SUCCESS
            return CommandStatus.NOT_SUPPORTED

        def Operate(self, cmd, idx, op_type=None):
            if not isinstance(cmd, ControlRelayOutputBlock) or idx not in range(10):
                print(f"[bridge] unsupported CROB idx={idx}")
                return CommandStatus.NOT_SUPPORTED

            # Extract CROB code as readable string
            code = getattr(cmd, "code", getattr(cmd, "functionCode", None))
            txt = str(code if code is not None else cmd)

            # ----- Interpret CROB -----
            if "_PULSE" in txt or "MODULATE" in txt or "TOGGLE" in txt:
                bo[idx] = 1 - bo[idx]
            elif "ON" in txt or "CLOSE" in txt or "LATCH_ON" in txt:
                bo[idx] = 1
            elif "OFF" in txt or "TRIP" in txt or "LATCH_OFF" in txt:
                bo[idx] = 0
            else:
                print(f"[bridge] unknown CROB code={txt}")
                return CommandStatus.NOT_SUPPORTED

            print(f"[bridge] bo now: {list(bo)}")
            print(f"[bridge] CROB idx={idx} -> bo[{idx}]={bo[idx]} (code={txt}) raw_code={code}")

            # DNP3 return update to outstation
            ub = asiodnp3.UpdateBuilder()
            ub.Update(BinaryOutputStatus(bool(bo[idx])), idx)
            self.ost.Apply(ub.Build())
            return CommandStatus.SUCCESS

    # ---------- Config and manager ----------
    CFG = yaml.safe_load(pathlib.Path("device.yaml").read_text())
    IP, PORT = CFG["network"]["listen_ip"], CFG["network"]["port"]

    mgr = asiodnp3.DNP3Manager(1)
    chan = mgr.AddTCPServer(
        "srv",
        opendnp3.levels.NORMAL | opendnp3.levels.ALL_COMMS | opendnp3.levels.ALL_APP_COMMS,
        asiopal.ChannelRetry().Default(),
        IP,
        PORT,
        asiodnp3.PrintingChannelListener().Create()
    )

    # ---------- DATABASE SIZES ----------
    db_sizes = opendnp3.DatabaseSizes(
        0, 0, 2, 13, 0, 10, 0, 0
    )
    stack_cfg = asiodnp3.OutstationStackConfig(db_sizes)
    stack_cfg.outstation.eventBufferConfig = opendnp3.EventBufferConfig.AllTypes(100)
    stack_cfg.outstation.params.allowUnsolicited = False
    stack_cfg.link.LocalAddr = 10
    stack_cfg.link.RemoteAddr = 1
    stack_cfg.link.KeepAliveTimeout = openpal.TimeDuration().Max()
    stack_cfg.link.Timeout = openpal.TimeDuration().Seconds(5)

    app = opendnp3.DefaultOutstationApplication.Create()
    cmd = SimCommandHandler()
    ost = chan.AddOutstation("ost", cmd, app, stack_cfg)
    cmd.ost = ost

    # ---------- PRELOAD DATABASE ----------
    print("[bridge] Preloading database (counters 0..12, analogs, binary outputs)...")
    init = asiodnp3.UpdateBuilder()
    for i in range(13):
        init.Update(opendnp3.Counter(0), i)
    init.Update(opendnp3.Analog(ai[0]), 0)
    init.Update(opendnp3.Analog(ai[1]), 1)
    for i in range(10):
        init.Update(BinaryOutputStatus(bool(bo[i])), i)
    ost.Apply(init.Build())

    # ---------- ENABLE ----------
    ost.Enable()
    print(f"[bridge] outstation ENABLED and ready on {IP}:{PORT}")
    print(f"[bridge] Addresses: Local={stack_cfg.link.LocalAddr}, Remote={stack_cfg.link.RemoteAddr}")
    time.sleep(1)

    # ---------- Main loop ----------
    counter_value = 0
    try:
        while True:
            step()
            counter_value = (counter_value + 1) % 1000000

            b = asiodnp3.UpdateBuilder()
            b.Update(opendnp3.Analog(ai[0]), 0)
            b.Update(opendnp3.Analog(ai[1]), 1)
            for i in range(13):
                b.Update(opendnp3.Counter(counter_value + i), i)
            for i in range(10):
                b.Update(BinaryOutputStatus(bool(bo[i])), i)

            ost.Apply(b.Build())
            time.sleep(dt)

    except KeyboardInterrupt:
        print("[bridge] exiting")
        ost.Shutdown()
        mgr.Shutdown()


if __name__ == "__main__":
    from multiprocessing import Array
    # create a shared bo array of 10 integers
    bo = Array('i', 10)
    start(bo)

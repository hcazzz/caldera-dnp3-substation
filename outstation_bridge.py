import time, yaml, pathlib
from pydnp3 import asiodnp3, opendnp3, asiopal
from sim_device import ai, bo, step, dt

from pydnp3.opendnp3 import (
    ICommandHandler,
    ControlRelayOutputBlock,
    ControlCode,
    CommandStatus,
    BinaryOutputStatus,
)

class SimCommandHandler(opendnp3.ICommandHandler):
    def __init__(self): super().__init__(); self.ost = None
    def Start(self): pass
    def End(self): pass
    def Select(self, cmd, idx):
        return opendnp3.CommandStatus.SUCCESS if isinstance(cmd, opendnp3.ControlRelayOutputBlock) and idx in (0,1) else opendnp3.CommandStatus.NOT_SUPPORTED
    def Operate(self, cmd, idx, op_type):
        if not isinstance(cmd, opendnp3.ControlRelayOutputBlock) or idx not in (0,1):
            print(f"[bridge] unsupported CROB idx={idx}"); return opendnp3.CommandStatus.NOT_SUPPORTED
        code = getattr(cmd, "code", getattr(cmd, "functionCode", None))
        txt = str(code if code is not None else cmd)
        is_on  = any(k in txt for k in ("LATCH_ON","PULSE_ON","CLOSE"))
        is_off = any(k in txt for k in ("LATCH_OFF","PULSE_OFF","TRIP"))
        if not (is_on or is_off):
            print(f"[bridge] unknown CROB code={txt}"); return opendnp3.CommandStatus.NOT_SUPPORTED
        bo[idx] = 1 if is_on and not is_off else 0
        print(f"[bridge] CROB idx={idx} -> bo={bo}")
        ub = asiodnp3.UpdateBuilder()
        ub.Update(opendnp3.BinaryOutputStatus(bool(bo[idx])), idx)
        self.ost.Apply(ub.Build())
        return opendnp3.CommandStatus.SUCCESS







CFG = yaml.safe_load(pathlib.Path("device.yaml").read_text())
IP, PORT = CFG["network"]["listen_ip"], CFG["network"]["port"]

mgr = asiodnp3.DNP3Manager(1)

chan = mgr.AddTCPServer(
    "srv",
    opendnp3.levels.NORMAL | opendnp3.levels.ALL_COMMS,
    asiopal.ChannelRetry().Default(),
    IP,
    PORT,
    asiodnp3.PrintingChannelListener().Create()
)

db_sizes = opendnp3.DatabaseSizes(0, 0, 2, 0, 0, 2, 0, 0)
stack_cfg = asiodnp3.OutstationStackConfig(db_sizes)
stack_cfg.link.LocalAddr = 1
stack_cfg.link.RemoteAddr = 2

app = opendnp3.DefaultOutstationApplication.Create()
cmd = SimCommandHandler()
ost = chan.AddOutstation("ost", cmd, app, stack_cfg)
cmd.ost = ost

ost.Enable()
print(f"[bridge] outstation up on {IP}:{PORT}")



try:
    while True:
        step()
        b = asiodnp3.UpdateBuilder()
        b.Update(opendnp3.Analog(ai[0]), 0)
        b.Update(opendnp3.Analog(ai[1]), 1)
        b.Update(opendnp3.BinaryOutputStatus(bool(bo[0])), 0)
        b.Update(opendnp3.BinaryOutputStatus(bool(bo[1])), 1)
        ost.Apply(b.Build())
        time.sleep(dt)
except KeyboardInterrupt:
    print("[bridge] exiting")
    ost.Shutdown()
    mgr.Shutdown()


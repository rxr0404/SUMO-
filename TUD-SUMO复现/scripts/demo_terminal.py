# -*- coding: utf-8 -*-
"""
终端演示版 ALINEA —— 与 traci_demo.py 相同的控制逻辑，但：
  - 控制周期之间加 0.8 s 真实延时，让控制台输出可以肉眼观察（供截图）；
  - 只跑 660 s（11 个控制周期），输出更紧凑。
用途：展示"Python 正在通过 TraCI 与 SUMO 实时交互"的运行画面。
"""
import os
import sys
import io
import time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CFG, OUT, resolve_sumo_home, STEP_LENGTH
import traci

CI, O_CRIT, K_ALINEA = 60, 3.0, 25.0
R_MIN, R_MAX = 150.0, 450.0
RM_JUNC, DURATION = "RM", 660

def build_cycle_states(rate, n_steps):
    cycle = 3600.0 / max(rate, 1.0)
    one = ["G"] * 2 + ["y"] * 2 + ["r"] * max(2, int((cycle - 2.0) / STEP_LENGTH))
    return (one * (n_steps // len(one) + 1))[:n_steps]

def main():
    print("=" * 78)
    print("  Python <-> SUMO (TraCI) interactive demo: ALINEA ramp metering")
    print("  control interval = 60 s, O_crit = 3%, rate in [150, 450] veh/h")
    print("=" * 78)
    home = resolve_sumo_home()
    traci.start([os.path.join(home, "bin", "sumo.exe"), "-c", CFG])
    print(f"[connected] SUMO started via TraCI, step length {STEP_LENGTH}s", flush=True)

    rate, t_log = R_MAX, []
    while traci.simulation.getTime() < DURATION:
        n_steps = int(CI / STEP_LENGTH)
        states = build_cycle_states(rate, n_steps)
        occ_sum = 0.0
        for st in states:
            traci.trafficlight.setRedYellowGreenState(RM_JUNC, st)   # 控制信号灯
            traci.simulationStep()                                    # 推进一步
            occ_sum += traci.inductionloop.getLastStepOccupancy("m2_d0")
            occ_sum += traci.inductionloop.getLastStepOccupancy("m2_d1")
        t = traci.simulation.getTime()
        occ = occ_sum / (2.0 * len(states))
        rate = min(R_MAX, max(R_MIN, rate + K_ALINEA * (O_CRIT - occ)))  # ALINEA
        speed = traci.edge.getLastStepMeanSpeed("main2")
        n_veh = traci.edge.getLastStepVehicleNumber("main2")
        t_log.append((t, occ, rate))
        print(f"  t={t:5.0f}s | downstream occupancy={occ:5.2f}% | ALINEA rate={rate:5.0f} veh/h"
              f" | main2: {speed:4.1f} m/s, {n_veh:2d} veh", flush=True)
        time.sleep(0.8)   # 放慢输出节奏，便于观察

    traci.close()
    print("[done] simulation closed. Full version: scripts/traci_demo.py", flush=True)

if __name__ == "__main__":
    main()

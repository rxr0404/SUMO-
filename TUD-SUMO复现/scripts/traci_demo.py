# -*- coding: utf-8 -*-
"""
纯 TraCI 交互演示 —— 不借助 TUD-SUMO，用 SUMO 官方 Python 接口（traci 包）
直接驱动仿真。这是"Python 与 SUMO 交互"最底层的形式，
也是论文 B §4 中作为对比基线的实现方式。

TraCI 的工作原理（对应论文 A §X）：
  sumo.exe 启动后开一个 TCP 端口，Python 的 traci 包通过 socket 发送命令/
  接收数据：可以逐步推进仿真、查询任意车辆/车道/检测器的状态、
  修改信号灯、改变车速、插入车辆……

本脚本用纯 TraCI 实现与 Test D 相同的 ALINEA 匝道控制：
  traci.simulationStep()               推进一步
  traci.inductionloop.getLastStepOccupancy()   读线圈占用率
  traci.trafficlight.setRedYellowGreenState()  直接命令红黄绿状态（一次放一辆策略）
  traci.edge / traci.vehicle           读路段/车辆数据
并在控制台实时打印，最后输出对比图与 CSV。

对应作业要求：3（Python 与 SUMO 交互——底层 API 演示）。
"""
import csv
import os
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CFG, OUT, PYLIBS, resolve_sumo_home, SIM_DURATION_S, STEP_LENGTH

import traci

# ---- ALINEA 参数（与 test_d_alinea.py 完全一致，便于对比） ----
CI, O_CRIT, K_ALINEA = 60, 3.0, 25.0
R_MIN, R_MAX = 150.0, 450.0
RM_JUNC = "RM"

def build_cycle_states(rate, n_steps):
    """按"一次放一辆"策略生成本控制周期内每一步的信号状态序列。

    放行率 rate (veh/h) -> 每辆车一个周期 cycle=3600/rate s：
    G 1s -> y 1s -> r (cycle-2)s，循环填充 n_steps 步（每步 0.5 s）。"""
    cycle = 3600.0 / max(rate, 1.0)
    g_steps, y_steps = int(1.0 / STEP_LENGTH), int(1.0 / STEP_LENGTH)
    r_steps = max(2, int((cycle - 2.0) / STEP_LENGTH))
    one_cycle = ["G"] * g_steps + ["y"] * y_steps + ["r"] * r_steps
    states = (one_cycle * (n_steps // len(one_cycle) + 1))[:n_steps]
    return states

def main():
    sumo_home = resolve_sumo_home()
    sumo_bin = os.path.join(sumo_home, "bin", "sumo.exe")
    # traci.start 会拉起 sumo.exe 子进程并建立 socket 连接
    traci.start([sumo_bin, "-c", CFG])
    print(f"[TraCI] connected to SUMO (step length {STEP_LENGTH}s, duration {SIM_DURATION_S}s)")

    rate, log = R_MAX, []
    n_steps_ci = int(CI / STEP_LENGTH)

    while traci.simulation.getMinExpectedNumber() > 0 and traci.simulation.getTime() < SIM_DURATION_S:
        # ---- ALINEA 用上一周期的实测占用率更新放行率（首周期用初始值） ----
        # ---- 生成本周期每一步的信号状态，逐步推进仿真，同时累加占用率 ----
        n_steps_ci = int(CI / STEP_LENGTH)
        states = build_cycle_states(rate, n_steps_ci)
        occ_sum = 0.0
        for st in states:
            if traci.simulation.getTime() >= SIM_DURATION_S:
                break
            # 直接命令信号灯状态 —— Python 对 SUMO 最直接的"控制"
            traci.trafficlight.setRedYellowGreenState(RM_JUNC, st)
            traci.simulationStep()
            # 每步都读占用率（瞬时值），周期末取平均 —— 与 TUD-SUMO 的
            # get_interval_detector_data() 等效；只读最后一步会得到噪声
            occ_sum += traci.inductionloop.getLastStepOccupancy("m2_d0")
            occ_sum += traci.inductionloop.getLastStepOccupancy("m2_d1")
        occ = occ_sum / (2.0 * len(states))

        t = traci.simulation.getTime()

        main2_speed = traci.edge.getLastStepMeanSpeed("main2")
        veh_n = traci.edge.getLastStepVehicleNumber("main2")
        # 演示车辆级读取：取 main2 上第一辆车的名字与速度
        vids = traci.edge.getLastStepVehicleIDs("main2")
        v_info = f"{vids[0]} @ {traci.vehicle.getSpeed(vids[0]):.1f} m/s" if vids else "-"

        # ---- ALINEA 反馈律 ----
        rate = min(R_MAX, max(R_MIN, rate + K_ALINEA * (O_CRIT - occ)))

        log.append((t, occ, rate, main2_speed, veh_n))
        print(f"  t={t:6.0f}s  occupancy={occ:5.2f}%  rate={rate:5.0f} veh/h  "
              f"main2: {main2_speed:4.1f} m/s {veh_n:3d} veh  [{v_info}]")

    traci.close()
    print("[TraCI] simulation finished, connection closed.")

    with open(os.path.join(OUT, "traci_demo_log.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["time_s", "occupancy_pct", "metering_rate_veh_h", "main2_speed_ms", "main2_veh_n"])
        w.writerows(log)

    # ---- 画图：占用率与放行率双轴对比 ----
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ts  = [r[0] for r in log]
    occ = [r[1] for r in log]
    rts = [r[2] for r in log]
    spd = [r[3] for r in log]
    fig, ax1 = plt.subplots(figsize=(11, 5))
    ax1.plot(ts, rts, "b-o", ms=3, label="metering rate (veh/h)")
    ax1.set_xlabel("time (s)"); ax1.set_ylabel("metering rate (veh/h)", color="b")
    ax2 = ax1.twinx()
    ax2.plot(ts, occ, "r-s", ms=3, label="downstream occupancy (%)")
    ax2.plot(ts, [O_CRIT]*len(ts), "r--", lw=1, label="O_crit")
    ax2.set_ylabel("occupancy (%) / speed (m/s)", color="r")
    ax2.plot(ts, spd, "g-^", ms=3, alpha=0.6, label="main2 mean speed (m/s)")
    fig.legend(loc="upper right", bbox_to_anchor=(0.88, 0.88))
    ax1.set_title("Pure-TraCI ALINEA ramp metering demo")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "traci_demo_control.png"), dpi=150)
    print("[TraCI] outputs -> traci_demo_log.csv / traci_demo_control.png")

if __name__ == "__main__":
    main()

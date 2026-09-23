# -*- coding: utf-8 -*-
"""
Test E —— 事件系统：动态事故（复现论文 B §3 Test E: "A scenario with an incident
active on the road segment immediately downstream of the on-ramp"）。

事件系统（论文 B §2.2）：TUD-SUMO 允许在仿真运行中动态触发事件
（事故、封路、天气等），且事件设置可保存复现 —— 这解决了纯 SUMO
难以做"可复现的受控实验"的痛点。

做了什么：
  1. 先让仿真自由运行 600 s；
  2. 在主线（汇入点下游路段 main2）上选一辆车，用 cause_incident() 制造事故：
     车辆原地停靠 300 s，所在路段限速降到 15 km/h；
  3. 继续仿真到结束，观察事故造成的速度骤降与消散；
  4. 用 Plotter 画 main2 平均速度时间序列（事故区间自动标注）。

对应作业要求：3（Python 与 SUMO 动态交互）。
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CFG, OUT, resolve_sumo_home, TOTAL_STEPS

from tud_sumo import Simulation, Plotter

def main():
    sim = Simulation("Test E - incident",
                     scenario_desc="Reproduction of TUD-SUMO paper Test E")

    sim.start(config_file=CFG,
              sumo_home=resolve_sumo_home(),
              get_fc_data=False,
              suppress_pbar=True)

    # 跟踪 main2 的逐车道数据（画边级平均速度时间序列用）
    sim.add_tracked_edges(["main2"])

    # 阶段 1：自由运行 600 s（1200 步）
    sim.step_through(end_step=1200)

    # 选一辆正在主线上游行驶的车 —— 它的"下一条边"就是汇入点下游的 main2，
    # cause_incident() 会把车停在下一条边上（与论文 Test E 的事故位置一致）
    vids = sim.get_vehicle_ids()
    veh_edges = sim.get_vehicle_vals(vids, "edge_id")
    if isinstance(veh_edges, str):
        veh_edges = {vids[0]: veh_edges}
    target = next((v for v in vids if veh_edges.get(v) == "main1"), None)
    print(f"[Test E] incident vehicle: {target} (currently on {veh_edges.get(target)})")

    # 制造事故：停 300 s，事故路段限速 15 km/h（论文 Table 1: cause_incident()）
    ok = sim.cause_incident(duration=300, vehicle_ids=target, position=0.5)
    print(f"[Test E] incident created at t={sim.curr_step*0.5:.0f}s: {ok}")

    # 阶段 2：继续跑到仿真结束（事故 300 s 后自动清除）
    sim.step_through(end_step=TOTAL_STEPS)
    sim.save_data(os.path.join(OUT, "test_e_sim_data.json"))
    sim.end()

    # 画 main2 全边平均速度时间序列 —— 事故造成的"速度骤降-恢复"清晰可见
    p = Plotter(sim, save_fig_loc=OUT, save_fig_dpi=150)
    p.plot_edge_data("main2", "speeds",
                     fig_title="Test E - mainline speed with incident (t=600-900s)",
                     save_fig="test_e_main2_speed.png")
    print("[Test E] done. outputs -> test_e_main2_speed.png / test_e_sim_data.json")

if __name__ == "__main__":
    main()

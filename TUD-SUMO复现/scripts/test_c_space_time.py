# -*- coding: utf-8 -*-
"""
Test C —— 时空图（复现论文 B §3 Test C: "Generation of a space-time diagram from
the minimum required amount of simulation data"）。

时空图 (space-time diagram)：横轴=沿路位置，纵轴=时间，颜色=速度。
交通流的激波、排队 upstream 传播、通行瓶颈在图上一目了然，
是交通流理论的核心分析工具（论文 A §VII 的基本图分析也依赖它）。

与 Test B 的区别（论文 B §4 特别强调的一点）：
  Test C 只跟踪 4 条边的聚合数据（add_tracked_edges），不存每辆车的 FCD，
  数据量小两个数量级，但同样能画出时空图 —— 体现 TUD-SUMO 的"最小数据"设计。

对应作业要求：2（数据获取）+ 3（Python 交互）。
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CFG, OUT, resolve_sumo_home, TOTAL_STEPS

from tud_sumo import Simulation, Plotter

def main():
    sim = Simulation("Test C - space-time diagram",
                     scenario_desc="Reproduction of TUD-SUMO paper Test C")

    sim.start(config_file=CFG,
              sumo_home=resolve_sumo_home(),
              get_fc_data=False,       # 不存 FCD（Test C 的"最小数据"要点）
              suppress_pbar=True)

    # 跟踪 4 条边的逐车道数据：主线上下游 + 匝道两段（论文 Table 1: add_tracked_edges()）
    sim.add_tracked_edges(["main1", "main2", "ramp1", "ramp2"])

    sim.step_through(end_step=TOTAL_STEPS)
    sim.save_data(os.path.join(OUT, "test_c_sim_data.json"))
    sim.end()

    # 用 TUD-SUMO 自带的 Plotter 画时空图（主线两段连续边）
    p = Plotter(sim, save_fig_loc=OUT, save_fig_dpi=150)
    p.plot_space_time_diagram(["main1", "main2"],
                              gf_sigma=[2, 6],      # 高斯平滑（纵2横6）
                              fig_title="Test C - space-time diagram (mainline)",
                              save_fig="test_c_space_time.png")
    print("[Test C] done. outputs -> test_c_space_time.png / test_c_sim_data.json")

if __name__ == "__main__":
    main()

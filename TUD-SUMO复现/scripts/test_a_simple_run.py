# -*- coding: utf-8 -*-
"""
Test A —— 裸跑仿真（复现论文 B §3 Test A: "Simple execution of the simulation
without any interaction"）。

做了什么：
  1. 用 TUD-SUMO 的 Simulation 类启动 SUMO（读取 sim.sumocfg 场景）；
  2. 不加任何控制，步进跑完 2000 s（4000 个 0.5 s 步长）；
  3. 期间 TUD-SUMO 自动逐步收集全网统计（车辆数、行程时间、延误等）；
  4. 打印仿真摘要，把全部数据保存为标准化 JSON 文件（论文 B §2.1）。

对应作业要求：1（正确运行交通仿真）+ 2（获取基本交通运行数据）。
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CFG, OUT, resolve_sumo_home, TOTAL_STEPS

import tud_sumo
from tud_sumo import Simulation

def main():
    sim = Simulation("Test A - simple run",
                     scenario_desc="Reproduction of TUD-SUMO paper (SoftwareX 2026) Test A")

    # 启动 SUMO：TUD-SUMO 在内部通过 TraCI 与 sumo.exe 建立连接
    sim.start(config_file=CFG,
              sumo_home=resolve_sumo_home(),
              get_fc_data=False,      # Test A 不需要浮动车数据（省内存）
              suppress_pbar=True)

    # 一步不停跑到仿真结束（不施加任何控制）
    sim.step_through(end_step=TOTAL_STEPS)

    # 打印摘要：车辆统计 + TUD-SUMO 对象概览（论文 B Table 1 中的 print_summary()）
    sim.print_summary()

    # 全部数据保存为单个 JSON 文件（论文 B §2.1: "save all data in a compact
    # standardised data format, either as a single JSON or binary file"）
    sim.save_data(os.path.join(OUT, "test_a_sim_data.json"))

    # 另存一份人类可读的摘要
    with open(os.path.join(OUT, "test_a_summary.txt"), "w", encoding="utf-8") as f:
        f.write(f"simulated steps : {sim.curr_step}\n")
        f.write(f"total vehicles  : departed={sim.get_to_depart()}, in network={sim.get_no_vehicles()}\n")
        f.write(f"total TTS (s)   : {sim.get_tts():.0f}\n")
        f.write(f"total delay (s) : {sim.get_delay():.0f}\n")

    sim.end()
    print("[Test A] done. outputs -> test_a_sim_data.json / test_a_summary.txt")

if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
Test B —— 浮动车数据 FCD（复现论文 B §3 Test B: "Generation of floating-car data
from a simple execution of the simulation"）。

FCD (Floating Car Data)：每一时间步、每一辆车的 位置/速度/加速度 等，
是交通可视化（轨迹图、时空图）和车辆行为分析的基础数据。

做了什么：
  1. 启动仿真时开启 get_fc_data=True（默认），TUD-SUMO 自动订阅每辆车的数据；
  2. 跑完 2000 s，用 save_fc_data() 把 FCD 存成 JSON；
  3. 读取 FCD，用 matplotlib 画"车辆轨迹图"（x=道路位置，y=时间，颜色=速度）
     —— 这是交通工程里最经典的 FCD 应用之一。

对应作业要求：2（获取基本交通运行数据）+ 3（Python 与 SUMO 交互读取数据）。
"""
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CFG, OUT, resolve_sumo_home, TOTAL_STEPS

import matplotlib
matplotlib.use("Agg")           # 无窗口环境直接出图
import matplotlib.pyplot as plt
from tud_sumo import Simulation

def main():
    sim = Simulation("Test B - floating car data",
                     scenario_desc="Reproduction of TUD-SUMO paper Test B")

    sim.start(config_file=CFG,
              sumo_home=resolve_sumo_home(),
              get_fc_data=True,        # 开启 FCD 收集（Test B 的核心）
              suppress_pbar=True)

    sim.step_through(end_step=TOTAL_STEPS)

    # 保存 FCD（论文 B Table 1: save_fc_data()）
    fcd_file = os.path.join(OUT, "test_b_fcd.json")
    sim.save_fc_data(fcd_file, json_indent=None)   # 紧凑存储
    print(f"[Test B] FCD saved: {fcd_file} ({os.path.getsize(fcd_file)//1024//1024} MB)")
    sim.end()

    # ---- 读取 FCD 并绘制轨迹图 ----
    # FCD 结构（TUD-SUMO v3.3.2）：
    #   fcd["fc_data"] = [每步 {veh_id: {longitude, latitude, speed(km/h), lane_id, ...}}]
    #   fcd["veh_info"] = {veh_id: {origin, destination, departure, ...}}
    # 注意：longitude/latitude 是"带路网偏移的 x/y"（netconvert 会平移坐标系），
    #       speed 单位是 km/h。下面从路网文件的 <location netOffset=...> 还原真实 x。
    import xml.etree.ElementTree as ET
    loc = ET.parse(os.path.join(os.path.dirname(CFG), "onramp.net.xml")).getroot().find("location")
    ox, oy = [float(v) for v in loc.get("netOffset").split(",")]

    with open(fcd_file, encoding="utf-8") as f:
        fcd = json.load(f)

    steps = fcd["fc_data"]
    dt = 0.5
    traj = {}   # veh_id -> ([t...], [x...], [v_kmh...])
    for i, step_veh in enumerate(steps):
        for vid, rec in step_veh.items():
            if not rec["lane_id"].startswith("main1"):   # 只画主线车辆
                continue
            t = i * dt
            tr = traj.setdefault(vid, ([], [], []))
            tr[0].append(t); tr[1].append(rec["longitude"] + ox); tr[2].append(rec["speed"])

    fig, ax = plt.subplots(figsize=(11, 5.5))
    for vid, (ts, xs, vs) in traj.items():
        # 颜色编码速度：蓝=快 红=慢
        sc = ax.scatter(xs, ts, c=vs, cmap="RdYlBu", vmin=0, vmax=140, s=2)
    ax.set_xlabel("position along motorway x (m)")
    ax.set_ylabel("simulation time (s)")
    ax.set_title("Test B - vehicle trajectories from floating car data (colour = speed)")
    cb = fig.colorbar(sc, ax=ax); cb.set_label("speed (km/h)")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "test_b_trajectories.png"), dpi=150)
    print("[Test B] trajectory figure saved: test_b_trajectories.png")

if __name__ == "__main__":
    main()

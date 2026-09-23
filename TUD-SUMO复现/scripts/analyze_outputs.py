# -*- coding: utf-8 -*-
"""
数据分析 —— 解析 SUMO 原生输出文件（不经过 TUD-SUMO），生成 CSV 与图表。

SUMO 的四类典型输出（对应论文 A §II 的输出清单）：
  detector_output.xml : E1 线圈检测器 —— 流量、占用率、平均速度（每 1 s 聚合）
  edgedata_output.xml : 按 edge 每 120 s 聚合的密度/速度/流量
  tripinfo_output.xml : 每辆车的完整行程（出发/到达/行程时间/延误/等待时间）
  summary_output.xml  : 每步的全网汇总（在网车辆数、平均速度、延误等）

对应作业要求：2（获取基本交通运行数据）。
"""
import csv
import io
import os
import sys
import xml.etree.ElementTree as ET
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import SCEN, OUT

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

def main():
    # ---------- 1. 检测器数据 ----------
    root = ET.parse(os.path.join(SCEN, "detector_output.xml")).getroot()
    det_ts = {}          # det_id -> {"t": [], "flow": [], "occ": [], "speed": []}
    for iv in root.findall("interval"):
        did, begin = iv.get("id"), float(iv.get("begin"))
        d = det_ts.setdefault(did, {"t": [], "flow": [], "occ": [], "speed": []})
        d["t"].append(begin)
        d["flow"].append(float(iv.get("nVehContrib") or 0))
        d["occ"].append(float(iv.get("occupancy") or 0))
        d["speed"].append(float(iv.get("speed") or 0))
    with open(os.path.join(OUT, "detectors_flow_occupancy.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["detector", "begin_s", "flow_veh_h", "occupancy_pct", "speed_ms"])
        for did, d in det_ts.items():
            for i in range(len(d["t"])):
                w.writerow([did, d["t"][i], d["flow"][i], d["occ"][i], d["speed"][i]])
    print("[analysis] detector CSV written")

    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    for did, d in det_ts.items():
        axes[0].plot(d["t"], d["flow"], label=did, lw=1)
        axes[1].plot(d["t"], d["speed"], label=did, lw=1)
    axes[0].set_ylabel("flow (veh/h per detector)"); axes[0].legend(ncol=5, fontsize=8)
    axes[0].set_title("Induction-loop detector data (pure SUMO output)")
    axes[1].set_ylabel("mean speed (m/s)"); axes[1].set_xlabel("time (s)")
    axes[1].legend(ncol=5, fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "analysis_detectors.png"), dpi=150)
    print("[analysis] detector figure written")

    # ---------- 2. 行程数据 ----------
    root = ET.parse(os.path.join(SCEN, "tripinfo_output.xml")).getroot()
    durs, losses = [], []
    for tr in root.findall("tripinfo"):
        durs.append(float(tr.get("duration")))
        losses.append(float(tr.get("timeLoss")))
    durs.sort()
    n = len(durs)
    with open(os.path.join(OUT, "tripinfo_stats.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["metric", "value"])
        w.writerow(["n_trips", n])
        w.writerow(["mean_duration_s", f"{sum(durs)/n:.2f}"])
        w.writerow(["median_duration_s", f"{durs[n//2]:.2f}"])
        w.writerow(["mean_timeLoss_s", f"{sum(losses)/n:.2f}"])
        w.writerow(["p95_duration_s", f"{durs[int(n*0.95)]:.2f}"])
    print(f"[analysis] tripinfo: {n} trips, mean duration {sum(durs)/n:.1f}s, "
          f"mean timeLoss {sum(losses)/n:.1f}s")

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.hist(durs, bins=50, color="#4C72B0", edgecolor="white")
    ax.axvline(sum(durs)/n, color="r", ls="--", label=f"mean {sum(durs)/n:.0f}s")
    ax.set_xlabel("trip duration (s)"); ax.set_ylabel("number of vehicles")
    ax.set_title("Trip duration distribution (tripinfo_output.xml)")
    ax.legend()
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "analysis_trip_durations.png"), dpi=150)
    print("[analysis] trip histogram written")

    # ---------- 3. 全网时序 ----------
    root = ET.parse(os.path.join(SCEN, "summary_output.xml")).getroot()
    t, running, speed, waiting = [], [], [], []
    for st in root.findall("step"):
        t.append(float(st.get("time")))
        running.append(int(st.get("running")))
        speed.append(float(st.get("meanSpeed")))
        waiting.append(int(st.get("halting")))
    fig, axes = plt.subplots(2, 1, figsize=(11, 6.5), sharex=True)
    axes[0].plot(t, running, label="running in network")
    axes[0].plot(t, waiting, label="halting (speed<0.1 m/s)")
    axes[0].set_ylabel("vehicles"); axes[0].legend(); axes[0].set_title("Network-wide summary (summary_output.xml)")
    axes[1].plot(t, speed, color="g")
    axes[1].set_ylabel("network mean speed (m/s)"); axes[1].set_xlabel("time (s)")
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "analysis_network_summary.png"), dpi=150)
    print("[analysis] network summary figure written")

if __name__ == "__main__":
    main()

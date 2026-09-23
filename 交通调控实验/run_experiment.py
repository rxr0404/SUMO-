# -*- coding: utf-8 -*-
"""
交通调控实验：匝道信号灯绿灯时间对交通运行的影响。

实验设计（单一变量对照）：
  - 同一路网、同一交通需求（主线 1000→1500→1000 veh/h，匝道恒 500 veh/h）、
    同一步长 0.5s、同一随机种子 42，唯一变量 = 匝道信号灯 RM 的绿灯时间：
      方案0（调整前/基线）：常绿，不控制
      方案A（调整后-短绿灯）：绿2s+黄1s+红7s，周期 10s，放行能力 ≈ 360 veh/h
      方案B（调整后-长绿灯）：绿6s+黄1s+红3s，周期 10s，放行能力 ≈ 900 veh/h
  - 三种方案均由本脚本通过 TUD-SUMO 的 set_phases() 在仿真启动后经 TraCI
    动态写入信号灯（Python 与 SUMO 交互的体现），连跑三遍并自动汇总对比。

运行：python run_experiment.py
输出：outputs/ 下三个方案的原始数据 JSON、对比汇总 CSV、两张对比图。
"""
import csv
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

BASE = os.path.dirname(os.path.abspath(__file__))
REPRO = os.path.join(os.path.dirname(BASE), "reproduce_tud_sumo")

# 复用主项目的依赖与 SUMO_HOME 解析逻辑
sys.path.insert(0, os.path.join(REPRO, "scripts"))
import common  # noqa: E402  (把 _pylibs 加入 sys.path)

from tud_sumo import Simulation  # noqa: E402

CFG = os.path.join(BASE, "scenario", "sim.sumocfg")
OUT = os.path.join(BASE, "outputs")
os.makedirs(OUT, exist_ok=True)

STEP_LEN = 0.5
TOTAL_STEPS = 4000          # 2000 s
SEED = 42                   # 固定随机种子，保证三方案唯一差异是信号配时

PLANS = [
    # (方案id, 报告名, 相位状态列表, 相位时长列表)
    ("plan0_free",  "方案0-常绿(基线)",        ["G"],       [2000]),
    ("planA_short", "方案A-短绿灯(绿2s红7s)",  ["G", "y", "r"], [2, 1, 7]),
    ("planB_long",  "方案B-长绿灯(绿6s红3s)",  ["G", "y", "r"], [6, 1, 3]),
]


def run_plan(plan_id, plan_name, phases, times):
    """运行单个信号方案的完整仿真，返回保存的数据文件路径。"""
    sim = Simulation(f"实验-{plan_id}", scenario_desc=f"绿灯时间调控实验: {plan_name}")
    sim.start(config_file=CFG,
              sumo_home=common.resolve_sumo_home(),
              get_fc_data=False,
              seed=SEED,
              suppress_pbar=True)

    # 通过 TraCI 动态写入信号方案（Python 与 SUMO 交互的核心动作）
    sim.set_phases({"RM": {"phases": phases, "times": times}})

    # 跟踪匝道与主线各边（取逐时段在车数/速度曲线）
    sim.add_tracked_edges(["ramp1", "ramp2", "main1", "main2"])

    sim.step_through(end_step=TOTAL_STEPS)
    f = os.path.join(OUT, f"{plan_id}_sim_data.json")
    sim.save_data(f)
    sim.end()
    print(f"[run] {plan_name} done -> {os.path.basename(f)}")
    return f


def load_metrics(path):
    """从单方案数据文件中提取对比指标。"""
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)["data"]

    trips_c = d["trips"]["completed"]
    trips_i = d["trips"]["incomplete"]

    def group(trips, origin):
        """按出发边分组统计行程时间（s）。"""
        durs = [t["arrival"] - t["departure"]
                for t in trips.values() if t["origin"] == origin and "arrival" in t]
        return durs

    ramp_dur = group(trips_c, "ramp1")
    main_dur = group(trips_c, "main1")

    veh = d["vehicles"]
    total_twt = sum(veh["twt"]) * STEP_LEN          # 全网总等待时间 (s)
    total_delay = sum(veh["delay"])                  # 全网总延误 (s)

    # 匝道排队规模：匝道两段边上的瞬时车辆数（每 20 步 = 10s 采样一次画曲线）
    ramp_veh = [len(d["edges"]["ramp1"]["step_vehicles"][i]) +
                len(d["edges"]["ramp2"]["step_vehicles"][i])
                for i in range(0, TOTAL_STEPS, 20)]
    main2_speed = d["edges"]["main2"]["speeds"]

    return {
        "completed": len(trips_c),
        "incomplete": len(trips_i),
        "ramp_completed": len(ramp_dur),
        "ramp_incomplete": sum(1 for t in trips_i.values() if t["origin"] == "ramp1"),
        "ramp_mean_dur": sum(ramp_dur) / len(ramp_dur) if ramp_dur else float("nan"),
        "main_mean_dur": sum(main_dur) / len(main_dur) if main_dur else float("nan"),
        "total_twt": total_twt,
        "total_delay": total_delay,
        "ramp_veh_curve": ramp_veh,
        "main2_speed_curve": main2_speed,
    }


def main():
    # ---- 1. 依次运行三种方案 ----
    paths = {}
    for pid, name, phases, times in PLANS:
        print(f"[run] {name} ...")
        paths[pid] = run_plan(pid, name, phases, times)

    # ---- 2. 汇总指标 ----
    metrics = {pid: load_metrics(p) for pid, (pid, name, _, _), p in
               [(pl[0], pl, paths[pl[0]]) for pl in PLANS]}

    # ---- 3. 汇总表 CSV ----
    csv_path = os.path.join(OUT, "对比汇总.csv")
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["指标", *[name for _, name, _, _ in PLANS]])
        w.writerow(["完成行程车辆数", *[metrics[pid]["completed"] for pid, *_ in PLANS]])
        w.writerow(["未完成(仿真结束时仍在网/未插入)", *[metrics[pid]["incomplete"] for pid, *_ in PLANS]])
        w.writerow(["匝道车辆完成数", *[metrics[pid]["ramp_completed"] for pid, *_ in PLANS]])
        w.writerow(["匝道车辆未完成数", *[metrics[pid]["ramp_incomplete"] for pid, *_ in PLANS]])
        w.writerow(["匝道车辆平均行程时间 (s)", *[f"{metrics[pid]['ramp_mean_dur']:.1f}" for pid, *_ in PLANS]])
        w.writerow(["主线车辆平均行程时间 (s)", *[f"{metrics[pid]['main_mean_dur']:.1f}" for pid, *_ in PLANS]])
        w.writerow(["全网总等待时间 (s)", *[f"{metrics[pid]['total_twt']:.0f}" for pid, *_ in PLANS]])
        w.writerow(["全网总延误 (s)", *[f"{metrics[pid]['total_delay']:.0f}" for pid, *_ in PLANS]])
    print(f"[analysis] 对比表 -> {csv_path}")

    # ---- 4. 终端打印对比表 ----
    rows = list(csv.reader(open(csv_path, encoding="utf-8-sig")))
    for row in rows:
        print(f"  {row[0]:<28s}" + "".join(f"{c:>16s}" for c in row[1:]))

    # ---- 5. 对比图 ----
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei"]
    plt.rcParams["axes.unicode_minus"] = False

    names = [name for _, name, _, _ in PLANS]
    t_axis = [i * 20 * STEP_LEN for i in range(len(metrics["plan0_free"]["ramp_veh_curve"]))]

    fig, axes = plt.subplots(2, 2, figsize=(13, 8.5))
    # (a) 匝道排队规模
    for pid, name, _, _ in PLANS:
        axes[0][0].plot(t_axis, metrics[pid]["ramp_veh_curve"], lw=1.5, label=name)
    axes[0][0].set_title("(a) 匝道上瞬时车辆数（排队规模）")
    axes[0][0].set_xlabel("仿真时间 (s)"); axes[0][0].set_ylabel("匝道在车数 (辆)")
    axes[0][0].legend(fontsize=9)
    # (b) 主线平均速度
    for pid, name, _, _ in PLANS:
        sp = metrics[pid]["main2_speed_curve"]
        axes[0][1].plot([i * STEP_LEN for i in range(len(sp))], sp, lw=1, label=name)
    axes[0][1].set_title("(b) 主线汇入段 main2 平均速度")
    axes[0][1].set_xlabel("仿真时间 (s)"); axes[0][1].set_ylabel("平均速度 (km/h)")
    axes[0][1].legend(fontsize=9)
    # (c) 匝道车平均行程时间
    vals = [metrics[pid]["ramp_mean_dur"] for pid, *_ in PLANS]
    axes[1][0].bar(range(3), vals, color=["#8ecae6", "#e76f51", "#2a9d8f"])
    axes[1][0].set_xticks(range(3)); axes[1][0].set_xticklabels(["方案0\n常绿", "方案A\n短绿灯", "方案B\n长绿灯"])
    axes[1][0].set_title("(c) 匝道车辆平均行程时间")
    axes[1][0].set_ylabel("平均行程时间 (s)")
    for i, v in enumerate(vals):
        axes[1][0].text(i, v, f"{v:.0f}s", ha="center", va="bottom")
    # (d) 完成车辆数
    vals2 = [metrics[pid]["completed"] for pid, *_ in PLANS]
    axes[1][1].bar(range(3), vals2, color=["#8ecae6", "#e76f51", "#2a9d8f"])
    axes[1][1].set_xticks(range(3)); axes[1][1].set_xticklabels(["方案0\n常绿", "方案A\n短绿灯", "方案B\n长绿灯"])
    axes[1][1].set_title("(d) 全部完成行程的车辆数")
    axes[1][1].set_ylabel("完成车辆数 (辆)")
    axes[1][1].set_ylim(0, 1050)
    for i, v in enumerate(vals2):
        axes[1][1].text(i, v, f"{v}", ha="center", va="bottom")
    fig.suptitle("交通调控实验：匝道信号灯绿灯时间对交通运行的影响（同需求/同种子，仅绿灯时间不同）")
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(os.path.join(OUT, "对比图_绿灯时间实验.png"), dpi=150)
    print(f"[analysis] 对比图 -> outputs/对比图_绿灯时间实验.png")

    # 原始曲线数据存 CSV（匝道排队曲线）
    with open(os.path.join(OUT, "匝道排队曲线.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["time_s", *names])
        for i, t in enumerate(t_axis):
            w.writerow([t, *[metrics[pid]["ramp_veh_curve"][i] for pid, *_ in PLANS]])

    print("[experiment] all done.")


if __name__ == "__main__":
    main()

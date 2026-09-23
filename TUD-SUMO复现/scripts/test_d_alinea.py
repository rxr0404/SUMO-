# -*- coding: utf-8 -*-
"""
Test D —— ALINEA 匝道控制（复现论文 B §3 Test D: "A ramp metering scenario with
ALINEA applied to the on-ramp, demonstrating traffic signal management and
interaction with the simulation"）。

ALINEA（Papageorgiou 等, 1991）：最经典的局部匝道控制算法，
   r(n) = clamp( r(n-1) + K * (O_crit - O_meas),  r_min, r_max )
   - O_meas：汇入点下游检测器实测占用率（%）
   - O_crit：临界占用率（通行能力最大时的占用率）
   - K     ：调节增益
   下游占用率高于临界值 → 压低匝道放行率（保护主线）；
   低于临界值 → 放宽放行率（充分利用主线）。这就是典型的"反馈控制"。

本脚本展示了 Python 与 SUMO 交互的完整闭环：
   读取检测器数据 → 控制算法计算 → 通过 TraCI 修改信号灯 → 影响仿真。

对应作业要求：3（Python 与 SUMO 交互——本作业的核心演示）。
"""
import csv
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CFG, OUT, resolve_sumo_home, STEP_LENGTH, TOTAL_STEPS

from tud_sumo import Simulation, Plotter

# ---- ALINEA 参数 ----
CI       = 60     # 控制周期 (s)：每 60 s 更新一次放行率
O_CRIT   = 3.0    # 临界占用率 (%)：本场景自由流占用率约 2.4-3.2%（三车道分流后），
                  # 取 3% 使反馈正好在需求波动区间内起作用 —— 峰时压低、平时放开，
                  # 曲线上能看到 ALINEA "呼吸"。实际应用应从基本图标定。
K_ALINEA = 25.0   # 增益 (veh/h per % occupancy)
R_MIN    = 150.0  # 最小放行率 (veh/h)
R_MAX    = 450.0  # 最大放行率 (veh/h)：低于匝道需求 500，控制效果才可见
# 注意单位：TUD-SUMO 存储的占用率是 0-1 的分数（源码 occupancy/100），
# get_interval_detector_data 返回的值需 ×100 换算回百分比。

def main():
    sim = Simulation("Test D - ALINEA ramp metering",
                     scenario_desc="Reproduction of TUD-SUMO paper Test D")

    sim.start(config_file=CFG,
              sumo_home=resolve_sumo_home(),
              get_fc_data=False,
              suppress_pbar=True)

    # 把信号灯路口 RM 登记为"匝道控制对象"（meter）：
    #   - 记录每次放行率与对应时刻（供 plot_rm_rate 画图）
    #   - 沿 ramp1/ramp2 估计排队长度（供 plot_rm_queuing 画图）
    #   - 立即以 init_rate 初始化信号灯
    sim.add_tracked_junctions({
        "RM": {"meter_params": {
            "min_rate": R_MIN, "max_rate": R_MAX,
            "ramp_edges": ["ramp1", "ramp2"],
            "init_rate": R_MAX}}})

    rate = R_MAX                      # 初始放行率
    n_steps_ci = int(CI / STEP_LENGTH)
    log = []                          # 控制日志（时间, 占用率, 放行率）
    print(f"[ALINEA] control interval={CI}s  O_crit={O_CRIT}%  K={K_ALINEA}  "
          f"rate range=[{R_MIN:.0f},{R_MAX:.0f}] veh/h")

    t = 0.0
    n_steps_ci = int(CI / STEP_LENGTH)
    while sim.curr_step < TOTAL_STEPS:
        # 1) 仿真推进一个控制周期（末尾不足一个周期时只推剩余步数）
        n = min(n_steps_ci, TOTAL_STEPS - sim.curr_step)
        sim.step_through(n_steps=n)

        # 2) 读取下游检测器在本周期内的平均占用率
        #    （论文 Table 1: get_interval_detector_data()；返回值为 0-1 分数，×100 转百分比）
        occ_frac = sim.get_interval_detector_data(["m2_d0", "m2_d1"], "occupancies",
                                                  n_steps=n, avg_det_vals=True)
        occ = occ_frac * 100.0

        # 3) ALINEA 反馈律更新放行率
        rate = min(R_MAX, max(R_MIN, rate + K_ALINEA * (O_CRIT - occ)))

        # 4) 把放行率写入匝道信号灯（论文 Table 1: set_tl_metering_rate()，
        #    内部按"一次放一辆"策略折算红绿灯时长 —— 详见论文 §2.2）
        sim.set_tl_metering_rate("RM", rate, control_interval=CI)

        log.append((sim.curr_step * STEP_LENGTH, occ, rate))
        print(f"  t={sim.curr_step*STEP_LENGTH:6.0f}s  downstream occupancy={occ:5.2f}%  "
              f"metering rate={rate:5.0f} veh/h")

    sim.save_data(os.path.join(OUT, "test_d_sim_data.json"))
    sim.end()

    # 控制日志存 CSV
    with open(os.path.join(OUT, "test_d_control_log.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["time_s", "downstream_occupancy_pct", "metering_rate_veh_h"])
        w.writerows(log)

    # ---- TUD-SUMO 工程可视化（论文 Fig.2 的同类图） ----
    p = Plotter(sim, save_fig_loc=OUT, save_fig_dpi=150)
    p.plot_rm_rate("RM", fig_title="Test D - ALINEA metering rate",
                   save_fig="test_d_metering_rate.png")       # 放行率曲线
    p.plot_tl_colours("RM", save_fig="test_d_phase_timing.png")  # 红绿灯相位时序图
    p.plot_rm_queuing("RM", fig_title="Test D - ramp queue",
                      save_fig="test_d_ramp_queue.png")       # 匝道排队长度
    print("[Test D] done. outputs -> test_d_*.png / test_d_control_log.csv / test_d_sim_data.json")

if __name__ == "__main__":
    main()

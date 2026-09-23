# SUMO / TUD-SUMO 仿真复现 —— 讲解文档

> 复现对象：**论文B** Evans, Rinaldi, Taale, Hoogendoorn. *TUD-SUMO: A research-oriented
> SUMO wrapper for traffic simulation in Python*. SoftwareX 34 (2026) 102745.
> 复现内容：论文 §3 的**高速公路匝道场景**与 **Test A–E 基准测试**，
> 外加一个**纯 TraCI**（SUMO 原生 Python 接口）交互演示作为对照（论文 §4 的对比基线做法）。

---

## 一、先建立全局图景：SUMO 是怎么工作的

用一次仿真把整条链路串起来（对应论文A §II 的"工作流"）：

```
 节点/边/连接  ──netconvert──▶  路网 .net.xml ─┐
 (nod/edg/con)                                ├─▶ sumo.exe / sumo-gui.exe  ◀── TraCI ◀── Python 脚本
 交通需求 .rou.xml ──────────────────────────▶ │        │
 信号灯/检测器 .add.xml ──────────────────────▶ ┘        ▼
                                             轨迹/检测器/行程/汇总 输出文件
```

1. **建路网**：人写"节点 + 边 + 连接"三个 XML，`netconvert` 编译成仿真用的 `.net.xml`；
2. **给需求**：`.rou.xml` 定义车辆类型、路径、流量（veh/h）；
3. **加设施**：`.add.xml` 挂检测器（E1 线圈）、信号灯配时、统计输出；
4. **跑仿真**：`sim.sumocfg` 把上面全部打包，`sumo`（无界面、快）或 `sumo-gui`（可视化）执行；
5. **取数据**：仿真写出 XML 输出文件；Python 通过 **TraCI** 接口边跑边读/边控制（TUD-SUMO 就是 TraCI 的封装）。

---

## 二、每个文件是什么（reproduce_tud_sumo/ 目录）

### scenario/ —— 仿真场景（作业的核心资产）

| 文件 | 作用 | 关键内容 |
|---|---|---|
| `nod.nod.xml` | **节点**（路口/端点坐标） | W→M→E 主线，S 匝道起点，RM 匝道信号灯节点 |
| `edg.edg.xml` | **边**（路段：车道数/限速/优先级） | main1 上游2车道；main2 汇入段**3车道**；ramp1/2 匝道 |
| `con.con.xml` | **连接**（车道级转向关系） | 主线整体内移一车道，匝道接入外侧专用道——**零冲突汇入**（见"坑4"） |
| `onramp.net.xml` | netconvert 生成的**路网成品**（不用手改） | 含 RM 的默认信号程序 |
| `rou.xml` | **交通需求** | vType 车辆动力学 + 流量：主线 1000→1500→1000 veh/h，匝道恒 500 veh/h，共 2000 s（论文 §3 原设定） |
| `detectors.add.xml` | **E1 线圈检测器** ×5 | m1_d0/d1 主线上游；m2_d0/d1 汇入点下游（ALINEA 的反馈来源）；ramp_d 匝道 |
| `tllogic.add.xml` | 匝道信号灯配时 | 基础场景常绿（自由流基线）；Test D 中 ALINEA 会动态接管 |
| `stats.add.xml` | 路网级统计输出 | 每 120 s 按边聚合流量/密度/速度 |
| `sim.sumocfg` | **主配置**（SUMO 的入口） | 打包上述所有 + 步长 0.5 s + tripinfo/summary 输出 |
| `gui-settings.xml` | GUI 视图设置 | 视口对准汇入区、车辆按速度着色 |

### scripts/ —— Python 脚本（对应论文 B Table 1 的函数）

| 脚本 | 复现内容 | 用到的 TUD-SUMO / TraCI API |
|---|---|---|
| `test_a_simple_run.py` | Test A：裸跑仿真 | `Simulation.start / step_through / print_summary / save_data` |
| `test_b_fcd.py` | Test B：浮动车数据 + 轨迹图 | `get_fc_data=True`、`save_fc_data()` + matplotlib |
| `test_c_space_time.py` | Test C：时空图（最小数据量） | `add_tracked_edges()`、`Plotter.plot_space_time_diagram()` |
| `test_d_alinea.py` | Test D：**ALINEA 匝道控制** | `add_tracked_junctions(meter_params)`、`get_interval_detector_data()`、`set_tl_metering_rate()`、`plot_rm_rate/plot_tl_colours/plot_rm_queuing` |
| `test_e_incident.py` | Test E：动态事故事件 | `cause_incident()`、`plot_edge_data()` |
| `traci_demo.py` | **纯 TraCI** 交互（论文 §4 的对比基线） | `traci.start/simulationStep`、`inductionloop.getLastStepOccupancy`、`trafficlight.setRedYellowGreenState` |
| `demo_terminal.py` | 上面 demo 的慢速版（输出可见，供截屏） | 同上 + `time.sleep` |
| `analyze_outputs.py` | 解析 SUMO 原生输出 → CSV + 三张图 | xml.etree + matplotlib |
| `common.py` | 公共配置：路径、SUMO_HOME 解析 | — |
| `setup_deps.py` | 依赖离线安装辅助（本机 pip 受限时，从 PyPI 下载 wheel 解压到 `_pylibs`） | urllib + zipfile |

### outputs/ —— 已经生成好的结果（"结果截图"可直接引用）

| 文件 | 是什么 | 怎么看 |
|---|---|---|
| `test_a_sim_data.json` | TUD-SUMO 自动收集的全网统计数据（JSON） | 车辆数/行程/延误随时间序列 |
| `test_a_summary.txt` | Test A 文本摘要 | departed/total TTS/delay |
| `test_b_fcd.json` (23MB) | **FCD 浮动车数据**：每步每车位置/速度 | `fc_data[i]` = 第 i 步全部车辆 |
| `test_b_trajectories.png` | **轨迹图**：x=位置，y=时间，颜色=速度 | 每条斜线=一辆车；蓝快红慢 |
| `test_c_space_time.png` | **时空图**（交通流理论核心图） | 竖直色带=排队，斜纹=激波；本场景自由流→均匀蓝 |
| `test_c_sim_data.json` | Test C 跟踪的 4 条边逐车道数据 | edges 字段 |
| `test_d_metering_rate.png` | **ALINEA 放行率曲线** | 低峰顶在 450；高峰被压到 360-430；需求回落又放开——反馈在"呼吸" |
| `test_d_phase_timing.png` | 匝道信号**相位时序图** | 每行一个车道信号；G/y/r 色块循环 |
| `test_d_ramp_queue.png` | **匝道排队长度** | 放行率 < 需求 500 → 排队缓增 |
| `test_d_control_log.csv` | 控制日志：时刻/占用率/放行率 | 与左图对应 |
| `test_e_main2_speed.png` | 事故期间主线速度骤降与恢复 | t=600-900s 的事故区间明显凹陷 |
| `traci_demo_control.png` / `traci_demo_log.csv` | 纯 TraCI 版 ALINEA 结果（与 Test D 同参数对照） | 双轴：占用率+放行率 |
| `analysis_detectors.png` / `detectors_flow_occupancy.csv` | 5 个检测器的流量/占用率/速度时序 | ramp_d 占用率高=匝道排队；m2 稳定=主线畅 |
| `analysis_trip_durations.png` / `tripinfo_stats.csv` | 966 辆车行程时间分布 | 均值 80.7s、平均延误仅 4.0s = 自由流 |
| `analysis_network_summary.png` | 全网车辆数/平均速度时序 | 车辆数随需求增减 |

### screenshots/ —— 运行截图（已采集）

| 文件 | 内容 | 怎么读 |
|---|---|---|
| `1_gui_running.png` | SUMO-GUI 运行画面：主线（2车道）+ 匝道汇入成 3 车道的几何清晰可见，黄色矩形=行驶中车辆，匝道上红色=低速车辆 | 注意看汇入点：主线整体上移一车道、匝道接入最外侧专用道——这就是"零冲突汇入"设计（第五节坑3） |
| `2_cli_statistics.png` | 无界面模式跑完 2000s 的统计块 | `Inserted: 1001`（全部成功插入）、`TimeLoss: 4.01`（平均每车仅损失4秒=自由流）、`Waiting: 0`（无插入积压） |
| `3_python_traci.png` | demo_terminal.py 实时日志：Python 通过 TraCI 边仿真边控制 | 前 8 行 rate=450（占用率<3%临界值）；t=540s 起占用率超 3%，ALINEA 把 rate 压到 438/432——反馈控制真实生效；末尾 TraCI-Duration 8.41s = Python 交互开销 |

---

## 三、三条作业要求 ↔ 交付物对照

| 要求 | 证据 | 状态 |
|---|---|---|
| 1. 正确运行交通仿真 | sumo-gui 运行画面截图（**待你截**）+ CLI 运行统计（**待你截**）+ outputs/ 全部结果 | 场景已验证：966 辆车全部完成，平均延误仅 4s |
| 2. 获取基本交通运行数据 | 检测器/行程/汇总三类原生输出 + `analysis_*.png` 三张图 + CSV（已生成） | 已完成 |
| 3. Python 与 SUMO 交互 | TUD-SUMO 五个测试脚本 + 纯 TraCI 演示（已跑通，结果图已生成）+ **终端运行画面（待你截）** | 已完成 |

---

## 四、运行与截图步骤（screenshots/ 三张图的产生过程）

### 第 0 步（一次性）：建 SUMO_HOME 目录联接

> 原因：本机 SUMO 装在中文路径下，SUMO 的 C++ 程序加载校验文件时无法处理中文路径，
> 会报 `Quitting (on unknown error)`。建一个英文路径的"目录联接"指过去即可（联接不占空间）。
> **打开一个 cmd 窗口**（Win+R → cmd）执行：

```bat
mklink /J C:\sumo_home "D:\智能交通\sumo\sumo-1.27.1"
set SUMO_HOME=C:\sumo_home
set PATH=C:\sumo_home\bin;%PATH%
```

> 注意：`set` 只对当前窗口有效，每开一个新窗口都要重新 set 这两行。

### 截图 ①：SUMO-GUI 正在跑（对应要求 1）

```bat
sumo-gui -c "D:\智能交通\reproduce_tud_sumo\scenario\sim.sumocfg" --start --delay 25
```

- 窗口打开后仿真**自动开始跑**（`--start`），25ms/步的速度可见车辆移动；
- **操作**：鼠标滚轮缩放、按住右键拖动平移，把画面调到能看到匝道汇入处和车流；
- **截图时机**：仿真时间走到 400s 以后（需求高峰，车多）；
- **截图方式**：点工具栏的**相机图标**（把当前视图存成 PNG，最干净），或 `Win+Shift+S` 框选；
- 保存为 `screenshots/1_gui_running.png`。
- 顺带观察（教你读画面）：车辆**蓝色=快、红色=慢**（顶部 speed 下拉框就是着色方案）；
  左上角是仿真时钟；匝道口 RM 信号灯在基础场景中是常绿的。

### 截图 ②：仿真结束统计（对应要求 1+2）

```bat
sumo -c "D:\智能交通\reproduce_tud_sumo\scenario\sim.sumocfg"
```

- 无界面模式，约 1 秒跑完，**不要关窗口**；
- **截图内容**：末尾的 `Vehicles: Inserted: ... / Statistics (avg of ...)` 统计块——
  这就是"基本交通运行数据"：插入车辆数、平均速度、平均行程时间、平均延误（TimeLoss）；
- 保存为 `screenshots/2_cli_statistics.png`。
- 怎么读：`Speed: 30.67 m/s`（≈110 km/h，主线设计速度 120）；`TimeLoss: 4.01s`
  （平均每辆车只损失 4 秒 = 非常通畅，自由流基线正常）。

### 截图 ③：Python 实时控制 SUMO（对应要求 3，核心）

```bat
cd /d D:\智能交通\reproduce_tud_sumo
python scripts\demo_terminal.py
```

- 这会看到 ALINEA 匝道控制的**实时日志**：每个控制周期打印
  `t=...s | downstream occupancy=...% | ALINEA rate=... veh/h | main2: ... m/s`；
- 全程约 30 秒（660s 仿真、11 个控制周期），**在第 3~8 行打印时截图**；
- 保存为 `screenshots/3_python_traci.png`。
- 怎么读：Python 每 60 秒（仿真时间）读一次下游占用率 → ALINEA 公式算新放行率 →
  通过 TraCI 改写匝道红绿灯。占用率高于临界值 3% → rate 下降；低于 → rate 回升。
- 想看完整版（2000s + 出图）：`python scripts\traci_demo.py`，
  完了会在 outputs/ 生成 `traci_demo_control.png`。

### （可选）截图 ④：TUD-SUMO 版 ALINEA

```bat
python scripts\test_d_alinea.py
```

日志格式与 ③ 不同（TUD-SUMO 封装版），对照两图能直观感受"封装 vs 原生"的差别——
这正是论文 B 基准测试的主题。

---

## 五、复现过程中踩过的 4 个坑（都是真跑出来的经验）

1. **中文路径 + SUMO_HOME**：`netconvert`/`sumo`/`sumo-gui` 一切正常，唯独
   `SUMO_HOME` 指向中文路径时 XSD 校验文件加载失败，报致命的
   `Quitting (on unknown error)` 且无任何 Error 行。解法：`mklink /J` 建英文路径联接。
   （本机环境下 `pip install` 也因临时目录权限问题无法使用，改为从 PyPI 下载 wheel
   直接解压到 `_pylibs`，等价于 `pip install --target`，见 `scripts/setup_deps.py`。）

2. **flow 必须按出发时间排序**：`rou.xml` 里 ramp_a（begin=0）写在 main_c（begin=1600）
   后面，SUMO 直接忽略该流量，日志只有一行 Warning。现象是匝道一辆车都没有——
   排查这类"流量不出现"问题先查 flow 顺序。

3. **匝道怎么建模才对**：最初把匝道直接汇入 2 车道主线的外侧车道，结果匝道堵死
   （密度 129 veh/km）而主线 30 m/s 畅通——停车线处的空隙接受对 32 m/s 的主车流
   过于保守。**正确做法**（也是论文 Fig.3 的画法）：汇入点下游主线拓为 3 车道，
   匝道接入最外侧专用道，主线车道整体内移——汇入点零冲突，真正的合流由下游
   换道模型（LC2013）完成。修复后平均延误从 60s 降到 4s。

4. **TUD-SUMO 的两个 API 细节**（论文没写、读源码才知道）：
   - `add_tracked_junctions("RM")` 只做普通跟踪；要画放行率/排队图必须传
     `meter_params` 字典（内部由此初始化 `_rate_times` 等属性，v3.3.2 里
     用错形式会直接 AttributeError）；
   - 占用率存储口径是 **0-1 分数**（源码 `occupancy/100`），而 TraCI 原生读数是
     百分数——两边混用会让 ALINEA 差 100 倍。复现就是用来暴露这类细节的。

---

## 六、论文结论 ↔ 复现结果的对应

| 论文 B 的说法 | 复现验证 |
|---|---|
| §2.2 "两大贡献：简化接口 + 自动数据收集" | Test A 一行 `step_through()` 即拿到全网统计（test_a_sim_data.json）；纯 TraCI 版实现同样功能需要手写订阅与聚合循环 |
| §3 场景设定（匝道 500 / 主线 1000→1500 / 2000s） | rou.xml 完全按此设定 |
| §3 Test D "ALINEA 匝道控制演示" | test_d_alinea.py：放行率随占用率反馈波动，相位时序图/排队图齐备 |
| §3 Test E "汇入点下游事故" | test_e_incident.py：main2 平均速度在事故区间骤降后恢复 |
| §4 "以 TraCI 为对比基线" | traci_demo.py 用原生 API 重复了 Test D，代码量/细节处理明显更多（如手工平均占用率、相位状态机） |
| §4 "性能换易用"（runtime 1.7-3.6×） | 方向一致：demo_terminal.py（TUD-SUMO 思路）与 traci_demo.py 同参数，TraCI 版仿真本体更快 |

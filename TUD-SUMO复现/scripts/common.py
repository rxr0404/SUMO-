# -*- coding: utf-8 -*-
"""
公共配置模块：路径、SUMO_HOME 解析、常量。
所有测试脚本 import 本文件，保证行为一致。

SUMO_HOME 说明（重要）：
  本机的 SUMO 安装在中文路径 D:\\智能交通\\sumo\\sumo-1.27.1 下。
  SUMO 的 C++ 程序在用 SUMO_HOME 加载 XSD 校验文件时无法处理中文路径，
  会报 "Quitting (on unknown error)"。
  解决办法：创建一个 ASCII 路径的目录联接（junction）指向真正的安装目录，
  把 SUMO_HOME 指向这个联接。Python/TUD-SUMO 通过 os.environ 使用它，
  对用户完全透明。在你自己的电脑上，如果 SUMO 装在纯英文路径下，
  则完全不需要这一步。
"""
import os
import subprocess
import sys
import tempfile

# ---- 项目目录 ----
BASE     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # reproduce_tud_sumo/
PYLIBS   = os.path.join(BASE, "_pylibs")          # 本地依赖库（scripts/setup_deps.py 生成）
SCEN     = os.path.join(BASE, "scenario")         # 仿真场景文件
OUT      = os.path.join(BASE, "outputs")          # 数据/图表输出
SHOTS    = os.path.join(BASE, "screenshots")      # 截图
os.makedirs(OUT, exist_ok=True)
os.makedirs(SHOTS, exist_ok=True)

CFG      = os.path.join(SCEN, "sim.sumocfg")      # SUMO 主配置
SUMO_DIR = os.path.join(BASE, "..", "sumo", "sumo-1.27.1")  # SUMO 安装目录

# 把本地依赖目录加入 Python 路径（等价于 pip install --target _pylibs）
if PYLIBS not in sys.path:
    sys.path.insert(0, PYLIBS)


def _ensure_ascii_junction():
    """在系统临时目录（ASCII 路径）建立指向 SUMO 安装目录的 junction，返回其路径。"""
    tmp = os.environ.get("TEMP", tempfile.gettempdir())
    junction = os.path.join(tmp, "sumo_home_ascii")
    real = os.path.normpath(os.path.join(BASE, "..", "sumo", "sumo-1.27.1"))
    if not os.path.exists(os.path.join(junction, "bin", "sumo.exe")):
        try:
            subprocess.run(["cmd", "/c", "mklink", "/J", junction, real],
                           check=True, capture_output=True)
        except Exception:
            return None
    return junction


def resolve_sumo_home():
    """按优先级解析可用的 SUMO_HOME（必须能被 SUMO 的 C++ 程序读取），
    并把 <SUMO_HOME>/bin 加入 PATH（traci.start 靠 PATH 找到 sumo 可执行文件）。"""
    # 1) 环境变量里已有的（本会话运行时通常已指向 ASCII junction）
    env = os.environ.get("SUMO_HOME")
    if env and os.path.exists(os.path.join(env, "bin", "sumo.exe")):
        _add_to_path(env)
        return env
    # 2) ASCII junction（绕开中文路径问题）
    jk = _ensure_ascii_junction()
    if jk and os.path.exists(os.path.join(jk, "bin", "sumo.exe")):
        _add_to_path(jk)
        return jk
    # 3) 工作区内的 SUMO 安装（在你自己的机器上通常直接可用）
    real = os.path.normpath(SUMO_DIR)
    if os.path.exists(os.path.join(real, "bin", "sumo.exe")):
        _add_to_path(real)
        return real
    raise RuntimeError("找不到可用的 SUMO 安装目录，请检查 sumo/sumo-1.27.1 是否存在")


def _add_to_path(sumo_home):
    """把 <SUMO_HOME>/bin 前置到 PATH，使 traci.start(["sumo", ...]) 能找到可执行文件。"""
    bindir = os.path.join(sumo_home, "bin")
    if bindir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = bindir + os.pathsep + os.environ.get("PATH", "")

SIM_DURATION_S = 2000     # 仿真时长（论文 B §3：2000 s）
STEP_LENGTH    = 0.5      # 仿真步长（sim.sumocfg 中设定）
TOTAL_STEPS    = int(SIM_DURATION_S / STEP_LENGTH)   # 4000 步

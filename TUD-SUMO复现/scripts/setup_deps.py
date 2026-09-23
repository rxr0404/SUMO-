# -*- coding: utf-8 -*-
"""依赖离线安装辅助脚本。

背景：本机环境下 pip 无法正常完成安装（临时目录权限受限），
因此改为直接从 PyPI 官方接口获取 wheel 包下载地址，
下载后解压到 _pylibs 目录，通过 PYTHONPATH 引用 ——
效果等价于 `pip install --target _pylibs 包名`。

用法：python scripts/setup_deps.py
（若你的机器 pip 可用，也可以直接 `pip install -r` 下列包名：
  traci sumolib tud-sumo mpl-tools shapely moviepy proglog decorator imageio imageio-ffmpeg）
"""
import json
import os
import sys
import urllib.request
import zipfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # reproduce_tud_sumo/
WHEELS = os.path.join(BASE, "_wheels")      # wheel 下载缓存（可随时删除）
LIBS = os.path.join(BASE, "_pylibs")        # 解压后的依赖库（scripts/common.py 会引用）
os.makedirs(WHEELS, exist_ok=True)
os.makedirs(LIBS, exist_ok=True)

# (包名, wheel 类型: 'any'=纯Python | 'cp312'=含C扩展 | 'win'=py3-none-win_amd64)
PACKAGES = [
    ("traci", "any"),
    ("sumolib", "any"),
    ("tud-sumo", "any"),
    ("mpl-tools", "any"),
    ("shapely", "cp312"),           # shapely 含 C 扩展，需要与本机 Python/平台匹配的版本
    ("moviepy", "any"),
    ("proglog", "any"),             # moviepy 依赖
    ("decorator", "any"),           # moviepy 依赖
    ("imageio", "any"),             # moviepy 依赖
    ("imageio-ffmpeg", "win"),      # moviepy 依赖（内含 ffmpeg 可执行文件）
]


def pick(pkg_name, kind):
    """从 PyPI 元数据中挑选合适的 wheel 文件。"""
    url = f"https://pypi.org/pypi/{pkg_name}/json"
    with urllib.request.urlopen(url, timeout=60) as r:
        data = json.loads(r.read().decode("utf-8"))
    files = data["urls"]
    if kind == "cp312":
        cands = [f for f in files if "cp312" in f["filename"] and "win_amd64" in f["filename"]]
    elif kind == "win":
        cands = [f for f in files if f["filename"].endswith(".whl") and "py3-none-win_amd64" in f["filename"]]
    else:
        cands = [f for f in files
                 if f["filename"].endswith(".whl") and
                 ("py3-none-any" in f["filename"] or "py2.py3-none-any" in f["filename"])]
    if not cands:
        raise RuntimeError(f"no suitable wheel for {pkg_name}: {[f['filename'] for f in files]}")
    return cands[0]


def main():
    for name, kind in PACKAGES:
        meta = pick(name, kind)
        dest = os.path.join(WHEELS, meta["filename"])
        if not os.path.exists(dest):     # 已下载过则跳过
            print(f"downloading {meta['filename']} ({meta['size'] // 1024} KB) ...")
            urllib.request.urlretrieve(meta["url"], dest)
        with zipfile.ZipFile(dest) as z:  # wheel 本质是 zip，直接解压即完成"安装"
            z.extractall(LIBS)
        print(f"  -> {name} ok")
    print("DONE. 依赖已就位于", LIBS)


if __name__ == "__main__":
    main()

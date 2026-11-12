"""Streamlit dashboard for "First Move".

Run:
    streamlit run dashboard.py

It reads logs/a.csv (A: score / membrane / sent) and logs/b.csv
(B: recv / state). Both files are produced by a_perception.py and
b_control.py; run sim_swarm.py for a sample log.
"""

from __future__ import annotations

import os

import pandas as pd
import streamlit as st

A_LOG = "logs/a.csv"
B_LOG = "logs/b.csv"

st.set_page_config(page_title="先手 · 看板", page_icon="🤖", layout="wide")
st.title("先手 · 事件级通信看板")
st.caption("A 观察者 → 16B 事件 → B 被控；稳定时 0 B/s，变化时 16 B/事件。")


def load(path: str) -> pd.DataFrame | None:
    if not os.path.exists(path):
        return None
    try:
        return pd.read_csv(path)
    except Exception as exc:  # pragma: no cover - file dependent
        st.warning(f"读取 {path} 失败：{exc}")
        return None


a = load(A_LOG)
b = load(B_LOG)

if a is None:
    st.info(
        "还没有 `logs/a.csv`。先运行：\n\n"
        "```bash\npython sim_swarm.py          # 生成仿真日志\n"
        "# 或\npython a_perception.py --camera 0 --dry-run\n```"
    )
    st.stop()

# metrics
packets = int(a["sent"].fillna(0).sum()) if "sent" in a else 0
duration = float(a["t"].max() - a["t"].min()) if len(a) > 1 else 0.0
bandwidth = (packets * 16.0 / duration) if duration > 0 else 0.0

reaction = None
if b is not None and "recv" in b and packets:
    sent_times = a.loc[a["sent"] == 1, "t"].tolist()
    recv_times = b.loc[b["recv"] == 1, "t"].tolist()
    deltas = []
    for ts in sent_times:
        later = [tr for tr in recv_times if tr >= ts]
        if later:
            deltas.append(later[0] - ts)
    if deltas:
        reaction = sum(deltas) / len(deltas)

c1, c2, c3, c4 = st.columns(4)
c1.metric("事件包", f"{packets}")
c2.metric("平均带宽", f"{bandwidth:.1f} B/s")
c3.metric("平均接收延迟", f"{reaction * 1000:.0f} ms" if reaction is not None else "—")
c4.metric("记录时长", f"{duration:.1f} s")

# A: score + membrane
st.subheader("A：变化分数与 LIF 膜电位")
if {"t", "score", "membrane"}.issubset(a.columns):
    chart = a.set_index("t")[["score", "membrane"]]
    st.line_chart(chart, height=260)

# A: event markers
if "sent" in a:
    events = a[a["sent"] == 1]
    st.subheader("A：事件触发")
    if len(events):
        st.dataframe(
            events[["t", "bearing_deg", "distance_cm"]].rename(
                columns={"t": "时间 (s)", "bearing_deg": "方位 (°)",
                         "distance_cm": "距离 (cm)"}
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.caption("本次记录没有触发事件。")

# B: state timeline
if b is not None:
    st.subheader("B：接收与状态")
    b_view = b.copy()
    b_view["STOP"] = (b_view.get("state") == "STOP").astype(int)
    if {"t", "STOP"}.issubset(b_view.columns):
        st.line_chart(b_view.set_index("t")[["STOP"]], height=180)
    st.dataframe(b_view.tail(30), use_container_width=True, hide_index=True)
else:
    st.info("还没有 `logs/b.csv`：运行 `python b_control.py --simulate`。")

st.caption(
    "提示：A/B 的时间戳来自各自进程；做论文数据时用同一台机器或 PTP 对齐。"
)

"""2D concept simulation for "First Move".

Runs without a robot and writes:
    media/demo.gif       animated concept (for the README)
    media/demo_poster.png  single frame (for slides)
    logs/sim.csv         timeline data

The simulation is deliberately simple: A watches a blind spot, B drives
forward, a pedestrian enters B's blind side, A fires one 16-byte event and
B stops before the pedestrian reaches its path.

Usage:
    python sim_swarm.py
"""

from __future__ import annotations

import argparse
import csv
import os

from PIL import Image, ImageDraw, ImageFont

W, H = 880, 495
FONT_CANDIDATES = [
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/msyhbd.ttc",
    "C:/Windows/Fonts/simhei.ttf",
]


def get_font(size: int):
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                pass
    return ImageFont.load_default()


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def draw_frame(t: float, spike_times: list[float]) -> Image.Image:
    img = Image.new("RGB", (W, H), "#f7f8fa")
    d = ImageDraw.Draw(img)

    # timeline
    bx = 330 + clamp((t - 0.5) / 8.5, 0.0, 1.0) * 140
    py = 160 + clamp((t - 6.0) / 3.0, 0.0, 1.0) * 140
    sent = t >= 9.0
    stopped = t >= 9.0
    membrane = 0.0 if t < 6.0 else clamp((t - 6.0) / 3.0, 0.0, 1.0)
    if sent:
        membrane = 0.12
    score = 0.0 if t < 6.0 else clamp((t - 6.0) / 3.0, 0.0, 1.0) * 0.08

    # header
    d.text((28, 16), "先手 · 事件级通信概念仿真", font=get_font(25), fill="#111827")
    d.text((28, 48), "A 观察者    B 被控    行人进入 B 的盲区", font=get_font(14),
           fill="#6b7280")

    # arena
    d.rounded_rectangle((40, 82, 840, 408), radius=16, outline="#d1d5db",
                        width=2, fill="#ffffff")

    # field-of-view overlays
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    ax, ay = 150, 250
    od.polygon([(ax, ay), (700, 115), (700, 385)], fill=(34, 197, 94, 28))
    od.polygon([(bx, 300), (bx + 130, 265), (bx + 130, 335)], fill=(59, 130, 246, 30))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    d = ImageDraw.Draw(img)

    # blind-spot label + pedestrian
    d.ellipse((622, py - 18, 658, py + 18), fill="#ef4444")
    d.text((600, py + 22), "行人（B 的盲区）", font=get_font(13), fill="#b91c1c")

    # A
    d.ellipse((ax - 18, ay - 18, ax + 18, ay + 18), fill="#22c55e")
    d.text((ax - 40, ay + 22), "A 观察者", font=get_font(13), fill="#15803d")

    # B
    d.rounded_rectangle((bx - 28, 282, bx + 28, 318), radius=8, fill="#3b82f6")
    d.text((bx - 26, 322), "B 被控", font=get_font(13), fill="#1d4ed8")
    if stopped:
        d.text((bx - 22, 252), "STOP", font=get_font(18), fill="#dc2626")

    # event arrow
    if sent:
        d.line((ax + 20, ay, bx - 32, 300), fill="#f59e0b", width=3)
        d.text(((ax + bx) / 2 - 16, (ay + 300) / 2 - 28), "16 B",
               font=get_font(18), fill="#b45309")

    # bottom: spike raster
    left, right, base = 60, 820, 452
    d.text((40, 424), "A 的事件脉冲", font=get_font(14), fill="#374151")
    d.line((left, base, right, base), fill="#9ca3af", width=2)
    window = 14.0
    for st in spike_times:
        if st > t + 1e-6:
            continue
        x = left + (st / window) * (right - left)
        d.line((x, base, x, base - 22), fill="#f59e0b", width=3)
        d.ellipse((x - 3, base - 26, x + 3, base - 20), fill="#f59e0b")

    # metrics
    bw = "16 B" if sent else "0 B"
    d.text((600, 424), f"带宽 {bw}", font=get_font(14), fill="#374151")
    d.text((710, 424), f"V={membrane:.2f}", font=get_font(14), fill="#374151")
    d.text((600, 446), f"score={score:.3f}", font=get_font(13), fill="#6b7280")

    # status line
    status = "B: STOP（收到事件）" if stopped else "B: FORWARD（无事件）"
    d.text((40, 468), status, font=get_font(14),
           fill="#dc2626" if stopped else "#1d4ed8")

    return img


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="media/demo.gif")
    parser.add_argument("--poster", default="media/demo_poster.png")
    parser.add_argument("--csv", default="logs/sim.csv")
    parser.add_argument("--frames", type=int, default=30)
    parser.add_argument("--duration", type=int, default=140, help="ms per frame")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(args.csv) or ".", exist_ok=True)

    spike_times = [9.0]
    frames = []
    rows = []
    for i in range(args.frames):
        t = i * 14.0 / (args.frames - 1)
        frame = draw_frame(t, spike_times)
        frames.append(frame)
        rows.append([
            f"{t:.2f}",
            f"{0.0 if t < 6 else min((t - 6) / 3, 1) * 0.08:.4f}",
            f"{0.0 if t < 6 else min((t - 6) / 3, 1):.3f}",
            1 if t >= 9 else 0,
            "STOP" if t >= 9 else "FORWARD",
        ])

    # save poster at the moment A fires
    poster_t = 9.2
    draw_frame(poster_t, spike_times).save(args.poster)

    # palette conversion keeps the GIF small
    pal_frames = [f.convert("P", palette=Image.Palette.ADAPTIVE, colors=128)
                  for f in frames]
    pal_frames[0].save(
        args.out,
        save_all=True,
        append_images=pal_frames[1:],
        duration=args.duration,
        loop=0,
        optimize=True,
    )

    with open(args.csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["t", "score", "membrane", "sent", "state"])
        writer.writerows(rows)

    print(f"wrote {args.out} ({len(frames)} frames), {args.poster}, {args.csv}")


if __name__ == "__main__":
    main()

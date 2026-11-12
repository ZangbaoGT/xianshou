"""A (observer): camera -> frame difference -> LIF trigger -> 16-byte UDP event.

This is the sensor side of the demo. It runs on a laptop or on an RDK board
with a USB/CSI camera. If you have a real event camera, replace the frame
difference block with the event stream and keep everything downstream.

Example:
    python a_perception.py --camera 0 --target 192.168.1.2 --port 9000
    python a_perception.py --camera 0 --dry-run          # no network needed
"""

from __future__ import annotations

import argparse
import csv
import os
import socket
import time

import numpy as np

from protocol import EVENT_TYPES, EventPacket


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="A: observer / event sender")
    p.add_argument("--camera", type=int, default=0, help="OpenCV camera index")
    p.add_argument("--target", default="127.0.0.1", help="B's IP address")
    p.add_argument("--port", type=int, default=9000, help="UDP port")
    p.add_argument("--src-id", type=int, default=1, help="robot id of A")
    p.add_argument("--width", type=int, default=320)
    p.add_argument("--height", type=int, default=240)
    p.add_argument("--diff-threshold", type=int, default=25,
                   help="pixel difference threshold (0-255)")
    p.add_argument("--fov-deg", type=float, default=60.0,
                   help="horizontal field of view for bearing estimation")
    p.add_argument("--lif-leak", type=float, default=0.15,
                   help="membrane leak per frame (0-1)")
    p.add_argument("--lif-threshold", type=float, default=0.30,
                   help="fire when membrane potential reaches this value")
    p.add_argument("--fps", type=float, default=30.0)
    p.add_argument("--dry-run", action="store_true", help="print packets, do not send")
    p.add_argument("--max-seconds", type=float, default=0.0,
                   help="stop after N seconds (0 = run forever)")
    p.add_argument("--log", default="logs/a.csv")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    try:
        import cv2
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise SystemExit(
            "opencv-python is required. Install it with:\n"
            "    pip install -r requirements.txt"
        ) from exc

    os.makedirs(os.path.dirname(args.log) or ".", exist_ok=True)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        raise SystemExit(f"cannot open camera {args.camera}")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)

    prev_gray = None
    membrane = 0.0          # LIF membrane potential
    seq = 0
    t0 = time.time()

    log = open(args.log, "w", newline="", encoding="utf-8")
    writer = csv.writer(log)
    writer.writerow(["t", "score", "membrane", "sent", "bearing_deg", "distance_cm"])

    print(f"[A] camera={args.camera} target={args.target}:{args.port} "
          f"dry_run={args.dry_run}", flush=True)
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("[A] camera read failed", flush=True)
                break

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (5, 5), 0)
            if prev_gray is None:
                prev_gray = gray
                continue

            diff = cv2.absdiff(prev_gray, gray)
            prev_gray = gray
            mask = cv2.threshold(diff, args.diff_threshold, 255,
                                 cv2.THRESH_BINARY)[1]

            # "change score": fraction of pixels that changed
            score = float(np.count_nonzero(mask)) / float(mask.size)

            # leaky integrate-and-fire: accumulate surprise, fire on threshold
            membrane = membrane * (1.0 - args.lif_leak) + score

            sent = 0
            bearing = 0.0
            distance_cm = 0
            if membrane >= args.lif_threshold:
                contours, _ = cv2.findContours(
                    mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
                )
                if contours:
                    largest = max(contours, key=cv2.contourArea)
                    x, y, w, h = cv2.boundingRect(largest)
                    cx = x + w / 2.0
                    bearing = (cx / float(gray.shape[1]) - 0.5) * args.fov_deg
                    # crude distance proxy from the blob height; replace with
                    # a depth camera or a calibrated pinhole model for real use
                    distance_cm = int(np.clip(230 - 2.0 * h, 20, 400))

                packet = EventPacket(
                    timestamp_ms=int(time.time() * 1000),
                    src_id=args.src_id,
                    event_type=EVENT_TYPES["obstacle"],
                    bearing_deg=bearing,
                    distance_cm=distance_cm,
                    confidence=min(1.0, membrane),
                    seq=seq,
                )
                seq = (seq + 1) & 0xFF
                data = packet.encode()
                if not args.dry_run:
                    sock.sendto(data, (args.target, args.port))
                sent = 1
                membrane = 0.0
                print(f"[A] fire {packet} -> {len(data)}B", flush=True)

            writer.writerow([
                f"{time.time() - t0:.3f}",
                f"{score:.4f}",
                f"{membrane:.4f}",
                sent,
                f"{bearing:.1f}",
                distance_cm,
            ])

            if args.max_seconds and (time.time() - t0) > args.max_seconds:
                break
            time.sleep(max(0.0, 1.0 / args.fps))
    except KeyboardInterrupt:
        print("\n[A] stopped", flush=True)
    finally:
        cap.release()
        sock.close()
        log.close()


if __name__ == "__main__":
    main()

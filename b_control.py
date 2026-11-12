"""B (controlled robot): receive 16-byte events -> stop / forward.

The demo uses a simple state machine: any event puts B into STOP for
``--stop-seconds``, then B returns to FORWARD. Replace ``apply_state`` with
your robot SDK (ROS 2 ``/cmd_vel``, vendor Python API, GPIO, ...).

Example:
    python b_control.py --listen 0.0.0.0 --port 9000
    python b_control.py --simulate          # no robot, just print states
"""

from __future__ import annotations

import argparse
import csv
import os
import socket
import time

from protocol import EventPacket


def apply_state(state: str) -> None:
    """Actuator hook.

    TODO(real robot): replace the print with your SDK, e.g.

        from geometry_msgs.msg import Twist
        msg = Twist()
        msg.linear.x = 0.0 if state == "STOP" else 0.15
        pub.publish(msg)

    or ``robot.stop()`` / ``robot.forward(0.15)``.
    """
    print(f"[B] actuator -> {state}", flush=True)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="B: controlled robot / event receiver")
    p.add_argument("--listen", default="0.0.0.0")
    p.add_argument("--port", type=int, default=9000)
    p.add_argument("--stop-seconds", type=float, default=1.0,
                   help="how long B stays stopped after an event")
    p.add_argument("--simulate", action="store_true",
                   help="do not touch hardware; print states only")
    p.add_argument("--max-seconds", type=float, default=0.0)
    p.add_argument("--log", default="logs/b.csv")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    os.makedirs(os.path.dirname(args.log) or ".", exist_ok=True)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((args.listen, args.port))
    sock.settimeout(0.2)

    log = open(args.log, "w", newline="", encoding="utf-8")
    writer = csv.writer(log)
    writer.writerow(["t", "recv", "src_id", "bearing_deg", "distance_cm",
                     "confidence", "state"])

    stop_until = 0.0
    last_state = "FORWARD"
    t0 = time.time()
    print(f"[B] listening on {args.listen}:{args.port} simulate={args.simulate}",
          flush=True)

    try:
        while True:
            now = time.time()
            try:
                data, addr = sock.recvfrom(64)
                try:
                    packet = EventPacket.decode(data)
                    stop_until = max(stop_until, now + args.stop_seconds)
                    print(f"[B] recv {len(data)}B from {addr[0]}: {packet}",
                          flush=True)
                    writer.writerow([
                        f"{now - t0:.3f}", 1, packet.src_id,
                        f"{packet.bearing_deg:.1f}", packet.distance_cm,
                        f"{packet.confidence:.2f}", "STOP",
                    ])
                except ValueError as exc:
                    print(f"[B] bad packet ({len(data)}B): {exc}", flush=True)
                    writer.writerow([f"{now - t0:.3f}", 0, "", "", "", "", "BAD"])
            except socket.timeout:
                pass

            state = "STOP" if now < stop_until else "FORWARD"
            if state != last_state:
                apply_state(state)
                last_state = state

            if args.max_seconds and (now - t0) > args.max_seconds:
                break
    except KeyboardInterrupt:
        print("\n[B] stopped", flush=True)
    finally:
        sock.close()
        log.close()


if __name__ == "__main__":
    main()

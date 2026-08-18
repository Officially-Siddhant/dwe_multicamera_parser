#!/usr/bin/env python3
"""FSIN frame-sync trigger for two stellarHD Followers, from a Jetson GPIO.

Drives a square wave on a header pin (BOARD numbering, default 31 = PQ.06)
at the camera frame rate. Both cameras' FSIN lines are wired to this pin,
so both sensors fire on the same edge -> hardware-synchronized frames
(DWE "Follower-only / external clock" topology, see docs/sync.md).

Pin 31 has no hardware PWM (only GPIO / extperiph_clk4, and the latter
cannot divide 51 MHz down to 60 Hz), so this is a SOFTWARE-timed edge.
To keep jitter low it:
  * sleeps to ABSOLUTE deadlines (clock_nanosleep TIMER_ABSTIME), so
    per-iteration overhead doesn't accumulate as drift;
  * requests SCHED_FIFO real-time priority (needs root / CAP_SYS_NICE;
    falls back with a warning if refused);
  * pins itself to one CPU core (--cpu) so it isn't migrated mid-loop;
  * uses libgpiod line ops via Jetson.GPIO (already used elsewhere in
    this workspace for the modem service pin).

Run with --measure to log the achieved edge timing (jitter / drift) instead
of just running -- do this once under full camera + rosbag load before
trusting it in a mission. See docs/sync.md.

    sudo python3 fsin_trigger.py                # 60 Hz on pin 31, forever
    sudo python3 fsin_trigger.py --hz 30
    sudo python3 fsin_trigger.py --measure 30   # run 30 s and report jitter
"""
import argparse
import ctypes
import os
import signal
import sys
import time

import Jetson.GPIO as GPIO

CLOCK_MONOTONIC = 1
TIMER_ABSTIME = 1


class timespec(ctypes.Structure):
    _fields_ = [('tv_sec', ctypes.c_long), ('tv_nsec', ctypes.c_long)]


_libc = ctypes.CDLL('libc.so.6', use_errno=True)
_clock_nanosleep = _libc.clock_nanosleep
_clock_nanosleep.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.POINTER(timespec), ctypes.POINTER(timespec)]


def sleep_until_ns(t_ns):
    """Sleep until absolute CLOCK_MONOTONIC time t_ns (nanoseconds)."""
    ts = timespec(t_ns // 1_000_000_000, t_ns % 1_000_000_000)
    while True:
        r = _clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, ctypes.byref(ts), None)
        if r == 0:
            return
        if r != 4:      # EINTR -> retry, anything else -> give up
            return


def go_realtime(cpu, prio):
    try:
        os.sched_setaffinity(0, {cpu})
    except Exception as e:
        print(f"[fsin_trigger] warn: could not pin to cpu {cpu}: {e}", file=sys.stderr)
    try:
        os.sched_setscheduler(0, os.SCHED_FIFO, os.sched_param(prio))
        return True
    except PermissionError:
        print("[fsin_trigger] warn: SCHED_FIFO refused (run with sudo for low jitter); "
              "continuing at normal priority", file=sys.stderr)
        return False


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--pin', type=int, default=31, help='BOARD pin (default 31 = PQ.06 / GPIO11)')
    ap.add_argument('--hz', type=float, default=60.0, help='trigger frequency (must equal camera fps)')
    ap.add_argument('--duty', type=float, default=0.5, help='high fraction of each period (default 0.5)')
    ap.add_argument('--cpu', type=int, default=3, help='CPU core to pin to (default 3)')
    ap.add_argument('--prio', type=int, default=80, help='SCHED_FIFO priority (default 80)')
    ap.add_argument('--measure', type=float, metavar='SECONDS',
                    help='run for SECONDS, then print achieved edge timing stats and exit')
    args = ap.parse_args()

    period_ns = int(round(1e9 / args.hz))
    high_ns = int(round(period_ns * args.duty))

    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(args.pin, GPIO.OUT, initial=GPIO.LOW)
    out = GPIO.output
    pin = args.pin

    rt = go_realtime(args.cpu, args.prio)
    print(f"[fsin_trigger] pin {pin}: {args.hz:g} Hz, period {period_ns/1e6:.4f} ms, "
          f"duty {args.duty:.0%}, {'SCHED_FIFO' if rt else 'normal prio'}, cpu {args.cpu}",
          flush=True)

    running = True

    def stop(*_):
        nonlocal running
        running = False
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    rising = [] if args.measure else None
    t_end = time.monotonic_ns() + int(args.measure * 1e9) if args.measure else None

    # Align the first edge to a whole period boundary a little in the future.
    t_next = time.monotonic_ns() + period_ns
    try:
        while running:
            sleep_until_ns(t_next)
            out(pin, GPIO.HIGH)
            if rising is not None:
                rising.append(time.monotonic_ns())
            sleep_until_ns(t_next + high_ns)
            out(pin, GPIO.LOW)
            t_next += period_ns
            if t_end is not None and t_next >= t_end:
                break
    finally:
        out(pin, GPIO.LOW)
        GPIO.cleanup(pin)

    if rising is not None and len(rising) > 2:
        import numpy as np
        r = np.array(rising, dtype=np.float64)
        dt = np.diff(r) / 1e3                        # us
        # jitter = deviation of each rising edge from the ideal grid
        ideal = r[0] + np.arange(len(r)) * period_ns
        err = (r - ideal) / 1e3                      # us
        print(f"\n[fsin_trigger] measured {len(r)} rising edges over {(r[-1]-r[0])/1e9:.1f}s")
        print(f"  period   target {period_ns/1e3:.1f} us   mean {dt.mean():.1f} us   "
              f"std {dt.std():.1f} us   min {dt.min():.1f}   max {dt.max():.1f}")
        print(f"  edge err vs ideal grid: std {err.std():.1f} us   |max| {np.abs(err).max():.1f} us")
        print(f"  |period err| > 500 us on {(np.abs(dt - period_ns/1e3) > 500).sum()} of {len(dt)} edges")
        drift_us = (r[-1] - ideal[-1]) / 1e3
        print(f"  net drift over run: {drift_us:+.1f} us  (absolute-deadline sleep -> should be ~0)")


if __name__ == '__main__':
    main()

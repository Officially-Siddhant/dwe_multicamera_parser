#!/usr/bin/env python3
"""Do both cameras stream at full rate when opened TOGETHER? (FSIN lock test)

The definitive symptom of a broken FSIN trigger is not "no sync" -- it is a
Follower that streams a burst of ~12 frames and then STALLS whenever a
trigger source is present, while free-running fine on its own. This tool
opens both cameras concurrently N times and reports each one's delivered
fps per trial, straight from V4L2 via OpenCV (no ROS in the loop).

    both ~60 fps, every trial       -> trigger is clean, cameras locked
    one camera ~1 fps / stalls      -> marginal trigger (wiring, GND, level)
    both ~60 alone but not together -> same, trigger only matters when present

Run it with the trigger source running (fsin_trigger.py, or a Leader
camera streaming). Uses the udev symlinks so it doesn't care about
/dev/videoN order. See docs/sync.md.

    python3 check_lock.py            # 4 trials, 4 s each
    python3 check_lock.py -n 8 -s 6
"""
import argparse
import threading
import time

import cv2

LEFT, RIGHT = '/dev/dwe_camera_left', '/dev/dwe_camera_right'


def open_cam(dev, fps):
    c = cv2.VideoCapture(dev, cv2.CAP_V4L2)
    c.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
    c.set(cv2.CAP_PROP_FRAME_WIDTH, 1600)
    c.set(cv2.CAP_PROP_FRAME_HEIGHT, 1200)
    c.set(cv2.CAP_PROP_FPS, fps)
    c.set(cv2.CAP_PROP_CONVERT_RGB, 0)   # raw MJPEG bytes, no decode -> pure delivery rate
    c.read()                             # start streaming
    return c


def measure(cap, name, secs, out):
    n, t0 = 0, time.time()
    while time.time() - t0 < secs:
        n += cap.read()[0]
    out[name] = n / (time.time() - t0)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('-n', '--trials', type=int, default=4)
    ap.add_argument('-s', '--secs', type=float, default=4.0, help='measure window per trial')
    ap.add_argument('--fps', type=int, default=60)
    ap.add_argument('--stagger', type=float, default=1.0,
                    help='seconds between opening left and right (default 1)')
    args = ap.parse_args()

    ok = 0
    for t in range(args.trials):
        cl = open_cam(LEFT, args.fps)
        time.sleep(args.stagger)
        cr = open_cam(RIGHT, args.fps)
        r = {}
        th = [threading.Thread(target=measure, args=(cl, 'left', args.secs, r)),
              threading.Thread(target=measure, args=(cr, 'right', args.secs, r))]
        [x.start() for x in th]
        [x.join() for x in th]
        cl.release(); cr.release()
        good = r['left'] > 0.9 * args.fps and r['right'] > 0.9 * args.fps
        ok += good
        print(f"trial {t}: left {r['left']:5.1f} fps   right {r['right']:5.1f} fps   "
              f"{'OK' if good else 'FAIL'}")
        time.sleep(1)

    print(f"\n{ok}/{args.trials} trials with both cameras at >= {0.9*args.fps:.0f} fps")
    if ok == args.trials:
        print("VERDICT: LOCKED -- both cameras stream at full rate together")
    elif ok == 0:
        print("VERDICT: NOT LOCKED -- a camera stalls whenever both run; check trigger wiring / GND / level")
    else:
        print("VERDICT: INTERMITTENT -- marginal trigger; check wiring contact and logic level")


if __name__ == '__main__':
    main()

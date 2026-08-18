#!/usr/bin/env python3
"""Check whether the two DWE cameras are hardware-synchronized (FSIN).

HOW TO USE
  1. Point BOTH cameras at the SAME millisecond stopwatch (any phone
     stopwatch app in the frame centre; screen at max brightness) or a
     fast PWM strobe. NOT a slow-blinking LED -- see "why" below.
  2. Record ~20 s:  ros2 launch auv_camera_bringup dwe_ros2_dual.launch.py record:=true
  3. python3 check_sync.py <bag>            -> stamp health + paired frames
     eog sync_pairs/                         -> read the stopwatch on each side

  Synced:     both frames of every pair show the SAME ms reading
              (or differ by a constant << 16 ms across all pairs).
  Not synced: readings differ by an amount that WANDERS from pair to pair,
              or by ~half a frame period (~8 ms @ 60 fps).

WHY THE STOPWATCH, AND WHY NOT header.stamp
  * header.stamp is a publish-time now() from two independent processes,
    downstream of USB. Both cameras clock 60 fps off the same USB host, so
    the stamp offset is a flat constant whether or not the sensors are
    FSIN-locked (verified: a Jul 30 bag with NO FSIN wire and an Aug 14
    bag WITH it both show <0.05 ms stamp drift over 10+ min). Rate lock is
    free; PHASE lock is what FSIN adds, and only the image can show it.
  * A slow-blinking LED (~few Hz) can't resolve sub-frame phase either:
    a 3 ms shift is <1% of its cycle, so any correlation peak is broad and
    flat (verified on a synthetic model: +1.5 ms phase reads as 0.00).
    The test signal must change on the ms scale -> stopwatch digits or a
    ~200 Hz+ strobe. Then the phase is DIRECTLY readable off the frames.

This tool therefore reports stamp health (fps / dropouts / stamp offset,
as a sanity check that both cameras were streaming) and dumps nearest-
stamp frame PAIRS side by side for you to read. The verdict is yours,
from the digits -- it is not something the stamps can supply.
"""
import argparse
import os
import sys

import cv2
import numpy as np
import rosbag2_py
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import CompressedImage

TOPIC_1 = '/dwe/camera_1/image_raw/compressed'
TOPIC_2 = '/dwe/camera_2/image_raw/compressed'
GAP_S = 0.5


def read_bag(bag_path, max_frames):
    reader = rosbag2_py.SequentialReader()
    reader.open(rosbag2_py.StorageOptions(uri=bag_path, storage_id='sqlite3'),
                rosbag2_py.ConverterOptions('', ''))
    reader.set_filter(rosbag2_py.StorageFilter(topics=[TOPIC_1, TOPIC_2]))
    stamps = {TOPIC_1: [], TOPIC_2: []}
    raw = {TOPIC_1: [], TOPIC_2: []}
    while reader.has_next():
        topic, data, _ = reader.read_next()
        if all(len(v) >= max_frames for v in stamps.values()):
            break
        if len(stamps[topic]) >= max_frames:
            continue
        msg = deserialize_message(data, CompressedImage)
        stamps[topic].append(msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9)
        raw[topic].append(bytes(msg.data))
    return {k: np.array(v) for k, v in stamps.items()}, raw


def stamp_health(name, t):
    if len(t) < 2:
        print(f"{name}: only {len(t)} frame(s)")
        return False
    dt = np.diff(t)
    gaps = dt[dt > GAP_S]
    print(f"{name}: {len(t)} frames over {t[-1]-t[0]:.1f}s  "
          f"median dt={np.median(dt)*1e3:.2f}ms (~{1/np.median(dt):.1f} fps)  "
          f"dropouts>{GAP_S}s: {len(gaps)}")
    return True


def nearest(t_ref, t):
    idx = np.clip(np.searchsorted(t_ref, t), 1, len(t_ref) - 1)
    lo, hi = idx - 1, idx
    return np.where(np.abs(t_ref[hi] - t) < np.abs(t_ref[lo] - t), hi, lo)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('bag_path')
    ap.add_argument('-o', '--out', default='sync_pairs', help='output dir for frame pairs')
    ap.add_argument('-n', '--pairs', type=int, default=8, help='number of pairs to save')
    ap.add_argument('--max-frames', type=int, default=2000, help='frames per camera to read')
    ap.add_argument('--skip', type=float, default=2.0, help='warm-up seconds to ignore')
    args = ap.parse_args()

    st, raw = read_bag(args.bag_path, args.max_frames)
    t1, t2 = st[TOPIC_1], st[TOPIC_2]
    print(f"bag: {args.bag_path}")
    if not (stamp_health('camera_1', t1) and stamp_health('camera_2', t2)):
        sys.exit(2)

    lo = max(t1[0], t2[0]) + args.skip
    hi = min(t1[-1], t2[-1])
    sel2 = np.where((t2 >= lo) & (t2 <= hi))[0]
    if len(sel2) < 10:
        print("not enough overlapping frames"); sys.exit(2)

    j1 = nearest(t1, t2[sel2])
    off_ms = (t1[j1] - t2[sel2]) * 1e3
    print(f"\nnearest-stamp offset cam1-cam2 over {len(sel2)} frames: "
          f"median {np.median(off_ms):+.2f} ms, spread (std) {np.std(off_ms):.2f} ms")
    print("  (a flat stamp offset does NOT prove sync -- read the stopwatch in the pairs below)")

    os.makedirs(args.out, exist_ok=True)
    picks = np.linspace(0, len(sel2) - 1, args.pairs).astype(int)
    for k, p in enumerate(picks):
        i2 = sel2[p]; i1 = j1[p]
        im1 = cv2.imdecode(np.frombuffer(raw[TOPIC_1][i1], np.uint8), cv2.IMREAD_COLOR)
        im2 = cv2.imdecode(np.frombuffer(raw[TOPIC_2][i2], np.uint8), cv2.IMREAD_COLOR)
        if im1 is None or im2 is None:
            continue
        h = min(im1.shape[0], im2.shape[0])
        im1 = cv2.resize(im1, (int(im1.shape[1] * h / im1.shape[0]), h))
        im2 = cv2.resize(im2, (int(im2.shape[1] * h / im2.shape[0]), h))
        pair = np.hstack([im1, im2])
        label = f"pair {k}   cam1 (L)  |  cam2 (R)   stamp diff cam1-cam2 = {off_ms[p]:+.2f} ms"
        cv2.putText(pair, label, (20, 45), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 0, 0), 5)
        cv2.putText(pair, label, (20, 45), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 255, 255), 2)
        cv2.imwrite(os.path.join(args.out, f'pair_{k:02d}.jpg'), pair)

    print(f"\nsaved {len(picks)} side-by-side pairs -> {args.out}/   (view: eog {args.out})")
    print("Read the ms stopwatch on both halves of each pair:")
    print("  same reading (or constant tiny diff) in every pair  -> SYNCED")
    print("  diff wanders pair to pair, or ~8 ms                  -> NOT SYNCED")


if __name__ == '__main__':
    main()

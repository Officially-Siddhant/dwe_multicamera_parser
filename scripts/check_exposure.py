#!/usr/bin/env python3
"""Quick offline overexposure check for a recorded camera rosbag.

No network required -- reads the bag directly with rosbag2_py, decodes a
few sample CompressedImage frames with OpenCV, and reports the fraction of
near-white (>=250/255) pixels per frame. Meant for a fast between-runs
"did this dive come out overexposed" check on-site. See docs/exposure.md.
"""
import argparse
import sys

import cv2
import numpy as np
import rosbag2_py
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import CompressedImage

TOPICS = ['/dwe/camera_1/image_raw/compressed', '/dwe/camera_2/image_raw/compressed']

# Above this, a frame is flagged. 99% is what the original ocean-test
# whiteout measured; 0-1% is normal for a properly exposed scene.
WARN_SATURATION_PCT = 20.0


def sample_frames(bag_path, topic, n_samples):
    storage_options = rosbag2_py.StorageOptions(uri=bag_path, storage_id='sqlite3')
    reader = rosbag2_py.SequentialReader()
    reader.open(storage_options, rosbag2_py.ConverterOptions('', ''))
    reader.set_filter(rosbag2_py.StorageFilter(topics=[topic]))

    msgs = []
    while reader.has_next():
        _topic, data, _stamp = reader.read_next()
        msgs.append(data)
    if not msgs:
        return []

    idxs = sorted(set(int(i * (len(msgs) - 1) / max(n_samples - 1, 1))
                       for i in range(n_samples)))
    frames = []
    for i in idxs:
        msg = deserialize_message(msgs[i], CompressedImage)
        img = cv2.imdecode(np.frombuffer(bytes(msg.data), dtype=np.uint8), cv2.IMREAD_COLOR)
        frames.append((i, len(msgs), img))
    return frames


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('bag_path')
    ap.add_argument('-n', '--samples', type=int, default=3,
                     help='frames to sample per camera (default: 3)')
    ap.add_argument('--save-dir', help='also save sampled frames as .jpg here '
                                        '(view with e.g. "eog <dir>")')
    args = ap.parse_args()

    any_warned = False
    for topic in TOPICS:
        frames = sample_frames(args.bag_path, topic, args.samples)
        if not frames:
            print(f"{topic}: no messages found (topic not in this bag?)")
            continue

        print(f"{topic}:")
        for idx, total, img in frames:
            if img is None:
                print(f"  frame {idx}/{total}: failed to decode")
                continue
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            sat_pct = float((gray >= 250).mean() * 100.0)
            flag = " <-- OVEREXPOSED" if sat_pct >= WARN_SATURATION_PCT else ""
            if flag:
                any_warned = True
            print(f"  frame {idx}/{total}: mean={gray.mean():.1f}  "
                  f"%pixels>=250={sat_pct:.1f}%{flag}")

            if args.save_dir:
                import os
                os.makedirs(args.save_dir, exist_ok=True)
                cam = topic.split('/')[2]
                out = os.path.join(args.save_dir, f'{cam}_frame{idx}.jpg')
                cv2.imwrite(out, img)
                print(f"    saved {out}")

    if any_warned:
        print(f"\nAt least one frame is >= {WARN_SATURATION_PCT:.0f}% saturated -- "
              f"looks overexposed. See docs/exposure.md.")
        sys.exit(1)
    print("\nLooks fine -- no frame crossed the saturation threshold.")


if __name__ == '__main__':
    main()

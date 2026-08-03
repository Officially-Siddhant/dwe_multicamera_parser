# ROS2 Parser for Multiple DWE Cameras 

Adapted from the original single-camera package by Urlaxle: https://github.com/Urlaxle/dwe_ros2_parser

> Package renamed to `auv_camera_bringup` (repo/package was previously `dwe_multicamera_parser` /
> `dwe_ros2_parser`) when adopted as this vehicle's camera bringup. Node executable names
> (`dwe_ros2_parser`, `image_sub`, `camera_info_publisher`) and source file paths are unchanged.

## Overview

Simple ROS2 package that reads in a DeepWater Explorer camera stream using V4L and publishes it to a ros2 topic. Camera settings and topic names can be set in the launch file. 

## Quick Commands

```bash
# Build + source
colcon build --packages-select auv_camera_bringup && source install/setup.bash

# Both cameras live (left=camera_1, right=camera_2). No preview windows by
# default (show_image:=false) -- required headless (no DISPLAY), which is how
# this runs on the vehicle; cv::imshow crashes the node otherwise.
ros2 launch auv_camera_bringup dwe_ros2_dual.launch.py

# Same, plus record both streams to a rosbag in one command. Records the
# compressed (60fps-capable) topics -- see "Getting 60fps" below.
# (launch args use name:=value, not --flags; bag_output must not already exist)
ros2 launch auv_camera_bringup dwe_ros2_dual.launch.py record:=true \
    bag_output:=/home/nemo/ros_ws/bags/dive_01

# Record separately instead (cameras must already be running)
ros2 launch auv_camera_bringup dwe_ros2_record.launch.py \
    bag_output:=/home/nemo/ros_ws/bags/dive_01

# Debug viewer for one camera -- reports real received fps, not just what the
# driver claims it's configured for. Needs a decoded Image topic, so either
# republish (see step 6 note below) or launch with publish_compressed:=false.
ros2 run auv_camera_bringup image_sub --ros-args -r /dwe/camera:=/dwe/camera_1/image_raw

# Inspect / replay a recorded bag
ros2 bag info /home/nemo/ros_ws/bags/dive_01
ros2 bag play /home/nemo/ros_ws/bags/dive_01
```

Start with the following command:
```
ros2 launch auv_camera_bringup dwe_ros2_parser.launch.py
```

The `ros2 topic hz <topic_name>`and inbuilt tools like `ros2 run image_view image_view` seems to use a python subscriber instead of C++. This can lead to the percived frequency and quality of the images being significantly reduced compared to what the topic is acctually providing. In order to see the "proper" output from the topic the image_sub node in this repository can be run. It will display the video stream to screen using OPENCV, and print the frequency of recieved images every 5 seconds. Just be aware that this node subscribes to `/dwe/camera/`.

```
ros2 run auv_camera_bringup image_sub
```

## Dependencies

OpenCV:
```
apt install libopencv-dev
```

ROS2 Humble:

https://docs.ros.org/en/humble/Installation.html

Gstreamer:
```
apt install libglib2.0-dev libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev \
gstreamer1.0-tools gstreamer1.0-x gstreamer1.0-plugins-base gstreamer1.0-plugins-good \
gstreamer1.0-plugins-bad gstreamer1.0-libav libgstreamer-plugins-bad1.0-dev \
gstreamer1.0-plugins-ugly gstreamer1.0-gl \
```

V4l:
```
apt install v4l-utils
```

camera_info_manager (needed for the `camera_info_publisher` node, see below):
```
apt install ros-humble-camera-info-manager
```


## How to find device number
Run to list available devices:

```
v4l2-ctl --list-devices 
```

Example output:
```
stellarHD Leader: stellarHD Lea (usb-0000:00:14.0-5.1):
	/dev/video0
	/dev/video1
	/dev/media0

stellarHD Leader: stellarHD Lea (usb-0000:00:14.0-5.3):
	/dev/video2
	/dev/video3
	/dev/media1

stellarHD Leader: stellarHD Lea (usb-0000:00:14.0-5.4):
	/dev/video4
	/dev/video5
	/dev/media2

```

The index of the first /dev/videoX of each camera can be used directly as the device parameter in the launch file. For example for the topmost camera in the example output setting device index = 0 in the configuration will create a ros2 stream for that camera. Alternativley multiple camera streams can be added into one virtual streaming device using modprobe, and the stiched image can be published.

Command to create virtual camera:

```
sudo modprobe v4l2loopback video_nr=9 \
card_label=stellarHD_stitched exclusive_caps=1
```

Example stitching of two cameras:
```
gst-launch-1.0 -v \
compositor name=mix \
    sink_0::xpos=0    sink_0::ypos=0   sink_0::alpha=1 \
    sink_1::xpos=1600 sink_1::ypos=0   sink_1::alpha=1 \
! jpegenc ! jpegdec ! videoconvert ! v4l2sink device=/dev/video9 \
v4l2src device=/dev/video0 ! image/jpeg,width=1600,framerate=60/1 ! jpegdec ! mix.sink_0 \
v4l2src device=/dev/video2 ! image/jpeg,width=1600,framerate=60/1 ! jpegdec ! mix.sink_1
```

Example stitching of three cameras:
```
gst-launch-1.0 -v \
compositor name=mix \
    sink_0::xpos=0    sink_0::ypos=0   sink_0::alpha=1 \
    sink_1::xpos=1600 sink_1::ypos=0   sink_1::alpha=1 \
    sink_2::xpos=3200 sink_2::ypos=0   sink_2::alpha=1 \
! jpegenc ! jpegdec ! videoconvert ! v4l2sink device=/dev/video9 \
v4l2src device=/dev/video0 ! image/jpeg,width=1600,framerate=60/1 ! jpegdec ! mix.sink_0 \
v4l2src device=/dev/video2 ! image/jpeg,width=1600,framerate=60/1 ! jpegdec ! mix.sink_1 \
v4l2src device=/dev/video4 ! image/jpeg,width=1600,framerate=60/1 ! jpegdec ! mix.sink_2
```

## Dual-Camera Raw Publishing (Two Independent DWE Cameras)

The gstreamer stitching approach above combines multiple physical cameras into a single virtual device and topic. If instead you want **two independent DWE cameras each publishing their own raw stream** on their own namespaced topics (e.g. for stereo/extrinsic calibration downstream), the package now supports that directly, without any virtual device or gstreamer stitching.

### What was added

- **`frame_id` parameter** on the `dwe_ros2_parser` node (`include/dwe_ros2_parser/dwe_ros2_parser.hh`, `src/dwe_ros2_parser.cc`). Previously every published image was hardcoded to `frame_id: camera_frame`, which made two simultaneously-running cameras indistinguishable downstream. Each camera instance can now be given its own frame id (e.g. `camera_1_frame`, `camera_2_frame`) via a launch parameter.
- **`launch/dwe_ros2_dual.launch.py`** — launches two `dwe_ros2_parser` nodes, each in its own namespace (`dwe/camera_1`, `dwe/camera_2`) with its own `device` index and `frame_id`, and a relative `image_topic: image_raw`, so the resulting topics are `/dwe/camera_1/image_raw` and `/dwe/camera_2/image_raw`.
- **`src/camera_info_publisher.cc`** — a new node that subscribes to a camera's `image_raw` topic, loads that camera's intrinsics/distortion from a calibration YAML via `camera_info_manager`, and republishes `sensor_msgs/CameraInfo` stamped with the same header as the image, on a relative `camera_info` topic. This pairing (`image_raw` + `camera_info` in the same namespace) is what `image_proc`/`stereo_image_proc` and other rectification tools expect.
- **`config/camera_1.yaml`, `config/camera_2.yaml`** — per-camera calibration files consumed by `camera_info_publisher`. **These currently contain placeholder intrinsics** (identity distortion, a rough guessed focal length), not measured calibration — see step 7 below.
- **`CMakeLists.txt` / `package.xml`** — added the `camera_info_manager` dependency, the `camera_info_publisher` executable/target, and install the `config/` directory alongside `launch/`.

### Getting two DWE cameras running, in order

1. **Install/rebuild dependencies** — make sure `ros-humble-camera-info-manager` is installed (see Dependencies above), in addition to the existing OpenCV/gstreamer/v4l-utils deps.
2. **Identify each physical camera's device index** — run `v4l2-ctl --list-devices` (see "How to find device number" above) and note the *first* `/dev/videoX` index for each of the two physical DWE cameras.
3. *(Recommended, not yet implemented)* — `/dev/videoX` indices are not guaranteed stable across reboot or USB replug order. Consider adding udev rules that create persistent symlinks (e.g. `/dev/dwe_camera_1`, `/dev/dwe_camera_2`) so the device indices in the launch file don't silently point at the wrong camera later.
4. **Set the real device indices** (and any camera-specific `width`/`height`/`framerate`/`exposure`/`save_folder`/`image_prefix` you need) for `camera_1` and `camera_2` in `launch/dwe_ros2_dual.launch.py`. On this vehicle, both cameras enumerate as `stellarHD Follower` and are wired as: `camera_1` = LEFT = `/dev/video2` (usb-2.2), `camera_2` = RIGHT = `/dev/video0` (usb-2.1) — confirmed via `v4l2-ctl --list-devices`. `save_folder` is `/home/nemo/ros_ws/bags/camera1` / `camera2`.
5. **Build the package** so the new `camera_info_publisher` executable, the `config/` install, and the `frame_id` parameter are picked up:
   ```
   colcon build --packages-select auv_camera_bringup
   source install/setup.bash
   ```
6. **Launch both cameras**:
   ```
   ros2 launch auv_camera_bringup dwe_ros2_dual.launch.py
   ```
   This brings up four nodes: `dwe_ros2_parser` and `camera_info_publisher` for each of `camera_1`/`camera_2`. `publish_compressed:=true` is the default (see "Getting 60fps" below), so confirm with `ros2 topic list` that you see `/dwe/camera_1/image_raw/compressed`, `/dwe/camera_1/camera_info`, `/dwe/camera_2/image_raw/compressed`, and `/dwe/camera_2/camera_info` — not `image_raw` itself, which isn't published in this mode.
   - Note: the `image_sub` debug node subscribes to a decoded `sensor_msgs/Image` (`/dwe/camera` hardcoded, remap as needed) and won't receive anything while `publish_compressed:=true`. Either run `dwe_ros2_dual.launch.py publish_compressed:=false` (lower fps, see "Getting 60fps"), or feed it a republished raw topic:
     ```
     ros2 run image_transport republish compressed raw --ros-args \
       -r in/compressed:=/dwe/camera_1/image_raw/compressed -r out:=/dwe/camera_1/image_raw
     ros2 run auv_camera_bringup image_sub --ros-args -r /dwe/camera:=/dwe/camera_1/image_raw
     ```
7. **(Optional) Record both streams to a rosbag** — with `dwe_ros2_dual.launch.py` running, capture `image_raw/compressed`/`camera_info` from both cameras to disk for later calibration/offline processing (see "Recording Rosbags" below).
8. **Replace the placeholder calibration** — run a real calibration against each camera's raw stream, e.g.:
   ```
   ros2 run camera_calibration cameracalibrator --size 8x6 --square 0.025 \
     image:=/dwe/camera_1/image_raw camera:=/dwe/camera_1
   ```
   and copy the resulting `camera_matrix`/`distortion_coefficients`/`rectification_matrix`/`projection_matrix` into `config/camera_1.yaml` (repeat for `camera_2.yaml`). Restart the launch file afterwards so `camera_info_publisher` picks up the real values.

   Note: `cameracalibrator` needs the decoded `image_raw` (`sensor_msgs/Image`) topic, which `publish_compressed:=true` (the launch file's default -- see "Getting 60fps" below) stops publishing. Run calibration with `publish_compressed:=false` on the node(s) being calibrated (a one-off, low-fps-tolerant step), then restore `true` for normal operation.
9. **For stereo/extrinsic calibration downstream** — a static transform between `camera_1_frame` and `camera_2_frame` (the physical baseline/extrinsics between the two cameras) is not yet published anywhere in this package. That transform (e.g. via `tf2_ros static_transform_publisher`, populated from a stereo extrinsic calibration) is required before feeding both streams into `stereo_image_proc` or similar.

## Getting 60fps

The stellarHD cameras on this vehicle have **no native 1920x1080 mode**. Confirmed via `v4l2-ctl --list-formats-ext` on the actual hardware, MJPEG (the only format worth using — see below) is limited to discrete sizes **1600x1200, 1280x720, 800x600, 640x480**, all of which support up to 60fps. `dwe_ros2_dual.launch.py` defaults to 1600x1200 (more pixels, 4:3) rather than 1280x720 (true 16:9 "720p").

**YUYV is a dead end above 320x240.** Same enumeration shows YUYV capped at 5fps for every resolution above 320x240 — this is a USB 2.0 (480Mbps) bandwidth limit on the uncompressed format, not a driver bug, matching DWE.ai support's guidance. `dwe_ros2_parser` already requests MJPG by default (`use_h264:=false`) and sets `CAP_PROP_FOURCC` before `CAP_PROP_FRAME_WIDTH`/`HEIGHT`, matching the order DWE.ai's OpenCV guide requires.

**MJPG alone isn't enough — the JPEG software decode is the actual bottleneck.** Measured live on this vehicle, at 1600x1200 with both cameras running:

| Path | Measured fps |
|---|---|
| Raw V4L2/OpenCV capture only (no ROS) | ~50-60 fps |
| Through `dwe_ros2_parser`, decoded to `sensor_msgs/Image`, published (no bag) | ~22-32 fps |
| Same, **with** `ros2 bag record` subscribed and writing | **~1.1-1.2 fps** |

Decoding every frame to BGR8 costs CPU, and the decoded message is ~6x larger (5.76MB vs ~130KB/frame at 1600x1200) — `ros2 bag record`'s sqlite3 storage backend chokes on writing that much per message at 60fps.

**Fix: skip the decode, publish the compressed bytes.** Set `publish_compressed:=true` (the default in `dwe_ros2_dual.launch.py`) to have `dwe_ros2_parser` set `CAP_PROP_CONVERT_RGB` off and publish the raw encoded JPEG straight from the driver as `sensor_msgs/CompressedImage` on `<image_topic>/compressed` (e.g. `/dwe/camera_1/image_raw/compressed`), instead of decoding to `image_raw`. Measured live with this enabled: **a sustained 60fps on both cameras simultaneously, including with `ros2 bag record` running.** `camera_info_publisher` needs `use_compressed:=true` to match (it triggers off whichever image topic is actually being published); `dwe_ros2_dual.launch.py` sets both together.

Only requires `use_h264:=false` (the default) — `publish_compressed` has no effect with H264 and is disabled with a warning if both are set.

## Recording Rosbags

`launch/dwe_ros2_record.launch.py` records both cameras' compressed image and camera_info topics (`/dwe/camera_1/image_raw/compressed`, `/dwe/camera_1/camera_info`, `/dwe/camera_2/image_raw/compressed`, `/dwe/camera_2/camera_info`) to a rosbag2 bag via `ros2 bag record`. It only records — it assumes `dwe_ros2_dual.launch.py` (or equivalent) is already running and publishing those topics with `publish_compressed:=true` (see "Getting 60fps" above; this is the default).

```
ros2 launch auv_camera_bringup dwe_ros2_dual.launch.py    # in one terminal
ros2 launch auv_camera_bringup dwe_ros2_record.launch.py bag_output:=/data/bags/run_01   # in another
```

Decoding the recorded `/compressed` topics back to viewable video/images afterward (offline, not on the vehicle) — e.g. per-frame with Python:
```python
import cv2, numpy as np
image = cv2.imdecode(np.frombuffer(msg.data, dtype=np.uint8), cv2.IMREAD_COLOR)
```
or via `ros2 run image_transport republish compressed raw --ros-args -r in/compressed:=/dwe/camera_1/image_raw/compressed -r out:=/dwe/camera_1/image_raw` to get a normal `image_raw` topic back for tools that expect one.

`bag_output` is a launch argument (default `dwe_dual_bag` in the current directory) — `ros2 bag record` refuses to write into a directory that already exists, so pass a fresh path per recording session. Stop recording with `Ctrl+C`; the bag is finalized on shutdown.
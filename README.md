# DeepWater Explorer - ROS2 Parser


## Overview

Simple ROS2 package that reads in a DeepWater Explorer camera stream using V4L and publishes it to a ros2 topic. Camera settings and topic names can be set in the launch file. 

Start with the following command:
```
ros2 launch dwe_ros2_parser dwe_ros2_parser.launch.py
```

The `ros2 topic hz <topic_name>`and inbuilt tools like `ros2 run image_view image_view` seems to use a python subscriber instead of C++. This can lead to the percived frequency and quality of the images being significantly reduced compared to what the topic is acctually providing. In order to see the "proper" output from the topic the image_sub node in this repository can be run. It will display the video stream to screen using OPENCV, and print the frequency of recieved images every 5 seconds. Just be aware that this node subscribes to `/dwe/camera/`.

```
ros2 run dwe_ros2_parser image_sub
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
4. **Set the real device indices** (and any camera-specific `width`/`height`/`framerate`/`exposure`/`save_folder`/`image_prefix` you need) for `camera_1` and `camera_2` in `launch/dwe_ros2_dual.launch.py`, replacing the current placeholder values (`device: 0` / `device: 2`).
5. **Build the package** so the new `camera_info_publisher` executable, the `config/` install, and the `frame_id` parameter are picked up:
   ```
   colcon build --packages-select dwe_ros2_parser
   source install/setup.bash
   ```
6. **Launch both cameras**:
   ```
   ros2 launch dwe_ros2_parser dwe_ros2_dual.launch.py
   ```
   This brings up four nodes: `dwe_ros2_parser` and `camera_info_publisher` for each of `camera_1`/`camera_2`. Confirm with `ros2 topic list` that you see `/dwe/camera_1/image_raw`, `/dwe/camera_1/camera_info`, `/dwe/camera_2/image_raw`, and `/dwe/camera_2/camera_info`.
   - Note: the `image_sub` debug node still has `/dwe/camera` hardcoded as its subscription topic (`src/image_subscriber.cc`). To use it against the new namespaced topics, remap it, e.g.:
     ```
     ros2 run dwe_ros2_parser image_sub --ros-args -r /dwe/camera:=/dwe/camera_1/image_raw
     ```
7. **Replace the placeholder calibration** — run a real calibration against each camera's raw stream, e.g.:
   ```
   ros2 run camera_calibration cameracalibrator --size 8x6 --square 0.025 \
     image:=/dwe/camera_1/image_raw camera:=/dwe/camera_1
   ```
   and copy the resulting `camera_matrix`/`distortion_coefficients`/`rectification_matrix`/`projection_matrix` into `config/camera_1.yaml` (repeat for `camera_2.yaml`). Restart the launch file afterwards so `camera_info_publisher` picks up the real values.
8. **For stereo/extrinsic calibration downstream** — a static transform between `camera_1_frame` and `camera_2_frame` (the physical baseline/extrinsics between the two cameras) is not yet published anywhere in this package. That transform (e.g. via `tf2_ros static_transform_publisher`, populated from a stereo extrinsic calibration) is required before feeding both streams into `stereo_image_proc` or similar.
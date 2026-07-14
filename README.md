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
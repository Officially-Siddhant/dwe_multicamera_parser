# Copyright 2024 - Urlaxle
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import datetime

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, ExecuteProcess,
                             IncludeLaunchDescription, RegisterEventHandler,
                             TimerAction)
from launch.conditions import IfCondition
from launch.event_handlers import OnProcessStart
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():

    pkg_share = get_package_share_directory('auv_camera_bringup')

    # Same root/timestamp convention as dwe_ros2_record.launch.py's own
    # default, and as ocean_test_N.launch.py's control/telemetry bags
    # (~/auv_bags) -- so all rosbags from a run live together.
    bags_root = os.path.expanduser('~/auv_bags')
    os.makedirs(bags_root, exist_ok=True)
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    default_bag_output = os.path.join(bags_root, f'dwe_dual_bag_{stamp}')

    # =========================================================================
    # Two kinds of V4L2 control, see docs/exposure.md:
    #  - "Camera Controls" (auto_exposure, exposure_time_absolute, ...):
    #    dwe_ros2_parser already manages these as ROS parameters (via
    #    cv::VideoCapture::set), so their values are just passed down through
    #    this launch file as ordinary launch arguments below.
    #  - "User Controls" (backlight_compensation, brightness, ...): NOT
    #    touched by dwe_ros2_parser at all -- these are set directly on the
    #    device with v4l2-ctl once each camera process has started, via the
    #    RegisterEventHandler/OnProcessStart blocks further down. This is
    #    also where scripts/set_exposure and scripts/exposure_tuner.py's live
    #    trial values should graduate to once you've settled on them.
    # =========================================================================

    # Left DWE camera (stellarHD Follower usb-2.2). Uses the
    # udev-symlinked path (see udev/99-dwe-cameras.rules) instead of a raw
    # /dev/videoN index, which is NOT stable across USB replug/reboot.
    dwe_camera_1 = Node(
        package='auv_camera_bringup',
        executable='dwe_ros2_parser',
        name='dwe_ros2_parser',
        namespace='dwe/camera_1',
        parameters=[{
          'device_path': '/dev/dwe_camera_left',
          'image_topic': 'image_raw',
          'width': 1280,
          'height': 720,
          'framerate': 30,
          'auto_exposure': ParameterValue(LaunchConfiguration('auto_exposure'), value_type=bool),
          'exposure': ParameterValue(LaunchConfiguration('exposure'), value_type=int),
          'show_image': False,
          'use_h264': False,
          'publish_compressed': True,
          'save_images': False,
          'save_folder': '/home/nemo/ros_ws/bags/camera1',
          'image_prefix': 'camera_1',
          'frame_id': 'camera_1_frame',
        }],
        output='screen'
    )

    # Right DWE Camera (stellarHD Follower usb-2.1). Uses the
    # udev-symlinked path (see udev/99-dwe-cameras.rules) instead of a raw
    # /dev/videoN index, which is NOT stable across USB replug/reboot.
    dwe_camera_2 = Node(
        package='auv_camera_bringup',
        executable='dwe_ros2_parser',
        name='dwe_ros2_parser',
        namespace='dwe/camera_2',
        parameters=[{
          'device_path': '/dev/dwe_camera_right',
          'image_topic': 'image_raw',
          'width': 1280,
          'height': 720,
          'framerate': 30,
          'auto_exposure': ParameterValue(LaunchConfiguration('auto_exposure'), value_type=bool),
          'exposure': ParameterValue(LaunchConfiguration('exposure'), value_type=int),
          'show_image': False,
          'use_h264': False,
          'publish_compressed': True,
          'save_images': False,
          'save_folder': '/home/nemo/ros_ws/bags/camera2',
          'image_prefix': 'camera_2',
          'frame_id': 'camera_2_frame',
        }],
        output='screen'
    )

    # CameraInfo publisher for the first DWE camera
    camera_info_1 = Node(
        package='auv_camera_bringup',
        executable='camera_info_publisher',
        name='camera_info_publisher',
        namespace='dwe/camera_1',
        parameters=[{
          'camera_name': 'camera_1',
          'camera_info_url': 'file://' + os.path.join(pkg_share, 'config', 'camera_1.yaml'),
          'image_topic': 'image_raw',
          'camera_info_topic': 'camera_info',
          'use_compressed': True,
        }],
        output='screen'
    )

    # CameraInfo publisher for the second DWE camera
    camera_info_2 = Node(
        package='auv_camera_bringup',
        executable='camera_info_publisher',
        name='camera_info_publisher',
        namespace='dwe/camera_2',
        parameters=[{
          'camera_name': 'camera_2',
          'camera_info_url': 'file://' + os.path.join(pkg_share, 'config', 'camera_2.yaml'),
          'image_topic': 'image_raw',
          'camera_info_topic': 'camera_info',
          'use_compressed': True,
        }],
        output='screen'
    )

    # Optional: fold rosbag recording into this same launch instead of running
    # dwe_ros2_record.launch.py separately in a second terminal. ROS2 launch
    # args use name:=value, not --flags, e.g.:
    #   ros2 launch auv_camera_bringup dwe_ros2_dual.launch.py record:=true \
    #       bag_output:=/home/nemo/ros_ws/bags/dive_01
    # The bag starts record_delay_s AFTER the cameras, not immediately:
    # skips the open/auto-exposure warm-up (and any watchdog reopen) so the
    # bag doesn't lead with garbage or a dead-topic head.
    record_include = TimerAction(
        period=5.0,
        actions=[IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(pkg_share, 'launch', 'dwe_ros2_record.launch.py')),
            launch_arguments={'bag_output': LaunchConfiguration('bag_output')}.items(),
        )],
        condition=IfCondition(LaunchConfiguration('record')),
    )

    # ------------------------------------------------------------------ #
    # User Controls -- applied with v4l2-ctl once each camera has started #
    # ------------------------------------------------------------------ #
    # "sleep 0.4" gives the device a moment to be fully opened by
    # dwe_ros2_parser before v4l2-ctl touches it (OnProcessStart fires as
    # soon as the OS process launches, not once the camera is actually
    # open). Add further --set-ctrl=name=value terms here for any other
    # User Control you need (see docs/exposure.md for the full list).
    camera_1_user_controls = RegisterEventHandler(
        OnProcessStart(
            target_action=dwe_camera_1,
            on_start=[
                ExecuteProcess(
                    cmd=['bash', '-lc',
                         ['sleep 0.4; v4l2-ctl --device=/dev/dwe_camera_left '
                          '--set-ctrl=backlight_compensation=',
                          LaunchConfiguration('backlight_compensation')]],
                    shell=False,
                )
            ],
        )
    )
    camera_2_user_controls = RegisterEventHandler(
        OnProcessStart(
            target_action=dwe_camera_2,
            on_start=[
                ExecuteProcess(
                    cmd=['bash', '-lc',
                         ['sleep 0.4; v4l2-ctl --device=/dev/dwe_camera_right '
                          '--set-ctrl=backlight_compensation=',
                          LaunchConfiguration('backlight_compensation')]],
                    shell=False,
                )
            ],
        )
    )

    return LaunchDescription([
        DeclareLaunchArgument('record', default_value='false',
                              description='Also start rosbag recording of '
                                          'both cameras (true|false)'),
        DeclareLaunchArgument('bag_output', default_value=default_bag_output,
                              description='Rosbag output dir when '
                                          'record:=true (must not already '
                                          'exist -- pass a fresh path)'),
        # Camera Controls (handled inside dwe_ros2_parser)
        DeclareLaunchArgument('auto_exposure', default_value='false',
                              description='true=leave the camera in its '
                                          'auto/Aperture-Priority exposure '
                                          'mode; false=force Manual Mode '
                                          'and apply "exposure" below.'),
        DeclareLaunchArgument('exposure', default_value='100',
                              description='exposure_time_absolute when '
                                          'auto_exposure:=false, in 100us '
                                          'units (range 1-5000). Lower for '
                                          'bright sun -- see '
                                          'docs/exposure.md.'),
        # User Controls (applied via v4l2-ctl, see block above)
        DeclareLaunchArgument('backlight_compensation', default_value='0',
                              description='V4L2 backlight_compensation '
                                          '(range 0-20). Confirmed root '
                                          'cause of ocean-test overexposure '
                                          'at its factory default of 5 -- '
                                          'see docs/exposure.md. 0 for '
                                          'bright/outdoor use.'),
        dwe_camera_1,
        dwe_camera_2,
        camera_info_1,
        camera_info_2,
        record_include,
        camera_1_user_controls,
        camera_2_user_controls,
    ])

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

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():

    pkg_share = get_package_share_directory('dwe_ros2_parser')

    # First DWE camera
    dwe_camera_1 = Node(
        package='dwe_ros2_parser',
        executable='dwe_ros2_parser',
        name='dwe_ros2_parser',
        namespace='dwe/camera_1',
        parameters=[{
          'device': 0,
          'image_topic': 'image_raw',
          'width': 1600,
          'height': 1200,
          'framerate': 60,
          'auto_exposure': False,
          'exposure': 100,
          'show_image': False,
          'use_h264': False,
          'save_images': False,
          'save_folder': '/home/urlaxle/data/camera_calibration/camera_1',
          'image_prefix': 'camera_1',
          'frame_id': 'camera_1_frame',
        }],
        output='screen'
    )

    # Second DWE camera
    dwe_camera_2 = Node(
        package='dwe_ros2_parser',
        executable='dwe_ros2_parser',
        name='dwe_ros2_parser',
        namespace='dwe/camera_2',
        parameters=[{
          'device': 2,
          'image_topic': 'image_raw',
          'width': 1600,
          'height': 1200,
          'framerate': 60,
          'auto_exposure': False,
          'exposure': 100,
          'show_image': False,
          'use_h264': False,
          'save_images': False,
          'save_folder': '/home/urlaxle/data/camera_calibration/camera_2',
          'image_prefix': 'camera_2',
          'frame_id': 'camera_2_frame',
        }],
        output='screen'
    )

    # CameraInfo publisher for the first DWE camera
    camera_info_1 = Node(
        package='dwe_ros2_parser',
        executable='camera_info_publisher',
        name='camera_info_publisher',
        namespace='dwe/camera_1',
        parameters=[{
          'camera_name': 'camera_1',
          'camera_info_url': 'file://' + os.path.join(pkg_share, 'config', 'camera_1.yaml'),
          'image_topic': 'image_raw',
          'camera_info_topic': 'camera_info',
        }],
        output='screen'
    )

    # CameraInfo publisher for the second DWE camera
    camera_info_2 = Node(
        package='dwe_ros2_parser',
        executable='camera_info_publisher',
        name='camera_info_publisher',
        namespace='dwe/camera_2',
        parameters=[{
          'camera_name': 'camera_2',
          'camera_info_url': 'file://' + os.path.join(pkg_share, 'config', 'camera_2.yaml'),
          'image_topic': 'image_raw',
          'camera_info_topic': 'camera_info',
        }],
        output='screen'
    )

    return LaunchDescription([
        dwe_camera_1,
        dwe_camera_2,
        camera_info_1,
        camera_info_2,
    ])

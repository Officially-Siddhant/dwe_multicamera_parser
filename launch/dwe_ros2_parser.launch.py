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
import yaml

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.actions import IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution

from launch_ros.actions import Node


def generate_launch_description():

    # Setup project paths
    dwe_parser = Node(
        package='auv_camera_bringup',
        executable='dwe_ros2_parser',
        parameters=[{
          'device': 9,
          'image_topic': '/dwe/camera',
          'width': 800,
          'height': 600,
          'framerate': 15,
          'auto_exposure': False,
          'exposure': 100,
          'show_image' : False, 
          'use_h264': False,
          'save_images': True,
          'save_folder': '/home/nemo/ros_ws/bags/left',
          'image_prefix': 'left',
        }],
        output='screen'
    )


    return LaunchDescription([
        dwe_parser,
    ])


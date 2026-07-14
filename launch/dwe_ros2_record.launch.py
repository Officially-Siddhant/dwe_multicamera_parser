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

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.substitutions import LaunchConfiguration

# Topics recorded from both DWE cameras (see launch/dwe_ros2_dual.launch.py).
# This launch file only records - the camera/camera_info nodes must already
# be running (or be launched alongside this one).
RECORD_TOPICS = [
    '/dwe/camera_1/image_raw',
    '/dwe/camera_1/camera_info',
    '/dwe/camera_2/image_raw',
    '/dwe/camera_2/camera_info',
]


def generate_launch_description():

    bag_output_arg = DeclareLaunchArgument(
        'bag_output',
        default_value='dwe_dual_bag',
        description=(
            'Output directory for the recorded rosbag2 '
            '(ros2 bag record refuses to overwrite an existing one, '
            'so pass a fresh path per run, e.g. bag_output:=/data/bags/run_01)'
        )
    )

    record_process = ExecuteProcess(
        cmd=['ros2', 'bag', 'record', '-o', LaunchConfiguration('bag_output')] + RECORD_TOPICS,
        output='screen'
    )

    return LaunchDescription([
        bag_output_arg,
        record_process,
    ])

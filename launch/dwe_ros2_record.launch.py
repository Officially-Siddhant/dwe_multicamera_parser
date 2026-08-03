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

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.substitutions import LaunchConfiguration

# This launch file only records - the camera/camera_info nodes must already
# be running (or be launched alongside this one).
#
# Records the /compressed (sensor_msgs/CompressedImage, raw MJPEG bytes)
# topics rather than /image_raw (sensor_msgs/Image, decoded BGR8). The
# decoded topic is ~6x larger per frame and, measured live on the vehicle,
# collapses ros2 bag record's throughput to ~1fps at 1600x1200 -- recording
# the still-compressed bytes instead confirmed a full 60fps for both cameras
# simultaneously. dwe_ros2_dual.launch.py sets publish_compressed:=true on
# both cameras to match. See auv_camera_bringup/README.md "Getting 60fps".
RECORD_TOPICS = [
    '/dwe/camera_1/image_raw/compressed',
    '/dwe/camera_1/camera_info',
    '/dwe/camera_2/image_raw/compressed',
    '/dwe/camera_2/camera_info',
]


def generate_launch_description():

    # Same root as the ocean_test_N.launch.py control/telemetry bags
    # (~/auv_bags), so all rosbags from a run live together. Timestamped like
    # those, since ros2 bag record refuses to overwrite an existing directory
    # and this default would otherwise collide on a second run.
    bags_root = os.path.expanduser('~/auv_bags')
    os.makedirs(bags_root, exist_ok=True)
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    default_bag_output = os.path.join(bags_root, f'dwe_dual_bag_{stamp}')

    bag_output_arg = DeclareLaunchArgument(
        'bag_output',
        default_value=default_bag_output,
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

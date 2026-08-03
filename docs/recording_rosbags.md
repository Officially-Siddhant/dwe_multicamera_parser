# Recording Rosbags

Both cameras publish compressed MJPEG (`publish_compressed:=true`, the
default — see README.md "Getting 60fps"). Recording those topics rather than
decoded `image_raw` is what makes 60fps recording possible at all.

Topics recorded either way:
```
/dwe/camera_1/image_raw/compressed   (sensor_msgs/CompressedImage)
/dwe/camera_1/camera_info            (sensor_msgs/CameraInfo)
/dwe/camera_2/image_raw/compressed   (sensor_msgs/CompressedImage)
/dwe/camera_2/camera_info            (sensor_msgs/CameraInfo)
```

## Cameras only, standalone

**One command** (cameras + recording together):
```bash
ros2 launch auv_camera_bringup dwe_ros2_dual.launch.py record:=true \
    bag_output:=/home/nemo/auv_bags/dive_01
```

**Two terminals** (cameras already running, e.g. from a separate launch):
```bash
# terminal 1
ros2 launch auv_camera_bringup dwe_ros2_dual.launch.py

# terminal 2
ros2 launch auv_camera_bringup dwe_ros2_record.launch.py \
    bag_output:=/home/nemo/auv_bags/dive_01
```

If `bag_output` is omitted, both default to a fresh
`~/auv_bags/dwe_dual_bag_<YYYYMMDD_HHMMSS>` — `ros2 bag record` refuses to
write into a directory that already exists, so pass an explicit path for
repeat runs in the same second, or just rely on the timestamp.

## Together with an ocean test (auv_bringup)

`ocean_test_1/2/3.launch.py` each take a `record_cameras` arg that brings up
both cameras and records them, alongside the mission's own control/telemetry
bag:

```bash
ros2 launch auv_bringup ocean_test_1.launch.py record_cameras:=true
```

This produces **two** bags, sharing one timestamp under `~/auv_bags/`:
```
~/auv_bags/ocean_test_1_<stamp>            # control/telemetry (always recorded)
~/auv_bags/ocean_test_1_<stamp>_cameras    # both cameras (only if record_cameras:=true)
```

They're kept separate on purpose — the camera stream is much higher
bandwidth, and mixing it into the control bag risks contending with (or
bloating) the recording that actually matters for tuning/debugging the
mission. Default is `record_cameras:=false`, so bench runs without cameras
attached are unaffected.

The camera bag's path is always derived from `bag_dir` (`<bag_dir>_cameras`)
— there's no separate override for it. To control where it lands, set
`bag_dir` explicitly:
```bash
ros2 launch auv_bringup ocean_test_1.launch.py record_cameras:=true \
    bag_dir:=/home/nemo/auv_bags/dive_01
# -> control bag:  /home/nemo/auv_bags/dive_01
# -> camera bag:   /home/nemo/auv_bags/dive_01_cameras
```

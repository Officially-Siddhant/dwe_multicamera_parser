# Exposure (overexposure in direct sunlight)

## What happened

Camera feed recorded during an ocean test in heavy afternoon sun came back
almost entirely white. Checked the actual recorded rosbags: ~99% of pixels
were at or above 250/255, on a properly-configured MJPEG feed already
running the fixes in "Getting 60fps" (README.md) -- this is a separate,
unrelated problem.

## Root cause (confirmed live, not white balance)

Per-channel stats on the real ocean frames: `R=254.6 G=250.1 B=253.0` --
all three channels clipped together, within a few units of each other. A
white-balance fault shows up as a *color cast* (one channel running well
ahead of the others); there isn't one here, and auto white balance was left
untouched throughout testing. This is a plain exposure/gain clip.

`v4l2-ctl --list-ctrls` on the live cameras showed why:
```
backlight_compensation  ... default=5  value=5
auto_exposure            ... value=1 (Manual Mode)      -- already correct
exposure_time_absolute   ... value=100                  -- already correct
```
`dwe_ros2_parser` already sets `auto_exposure`/`exposure_time_absolute`
correctly (confirmed live, both track the launch file's `auto_exposure`/
`exposure` params). But it never touches `backlight_compensation`, which
sits at its factory default of 5/20. Its documented purpose (DWE's
[camera-controls docs](https://docs.dwe.ai/dwe-os/pages/camera-controls)):
*"Adjusts the exposure to properly illuminate darker subjects positioned
against a bright background, preventing them from appearing as
silhouettes."* At the ocean surface (bright sky + sun-glared water filling
most of the frame), it fires and boosts exposure/gain across the whole
scene -- it's a blunt, scene-wide adjustment on this class of sensor, not a
masked, subject-only one, so it overshoots the entire frame, subject
included, rather than just brightening a silhouette.

Live A/B test, same camera, only `backlight_compensation` changed:

| | R | G | B | % pixels >= 250 |
|---|---|---|---|---|
| `backlight_compensation=5` (default) | 254.6 | 250.1 | 253.0 | ~99% |
| `backlight_compensation=0` | 107.5 | 107.9 | 107.6 | ~0% |

## Using `scripts/set_exposure`

```bash
scripts/set_exposure <video_index> <profile>
```

Profiles:
- `auto` -- factory default (auto exposure, backlight_compensation=5). Known to overexpose in direct sun.
- `manual` -- baseline fix: manual exposure, backlight_compensation off. Good for indoor/overcast.
- `bright-sun` -- `manual` + 5x shorter exposure (`exposure_time_absolute=20`), for direct sun/water glare.
- `bright-sun-dark` -- `bright-sun` + additional ISP-level darkening (`brightness=-30`), if `bright-sun` still clips.
- `custom` -- pass explicit values: `set_exposure <video_index> custom <auto_exposure> <exposure_time_absolute> <backlight_compensation> <brightness> <gain>`

Run once per camera (camera_1 = `/dev/video2`, camera_2 = `/dev/video0` on
this vehicle -- see main README "How to find device number"):
```bash
scripts/set_exposure 2 bright-sun
scripts/set_exposure 0 bright-sun
```

These are plain V4L2 controls on each camera's own onboard ISP/sensor (UVC
"Processing Unit" and "Camera Terminal" controls, reached over USB's control
endpoint) -- not USB-bus/bandwidth settings, and not shared between the two
cameras; each needs setting independently.

## Live tuning GUI (`exposure_tuner.py`)

matplotlib sliders/toggles for every control above, applied live via
`v4l2-ctl --set-ctrl` as you drag them. Watch the effect in `cheese` (or any
viewer) in another terminal.

```bash
cheese                                            # terminal 1: live preview
python3 scripts/exposure_tuner.py                 # terminal 2: tuner (starts on camera_1)
```
Switch camera with the radio button at the top. "Refresh" re-reads current
values (e.g. after using `set_exposure` elsewhere); "Reset defaults" restores
factory values.

## Trial-testing a profile

Apply a profile to both cameras, then record a short trial bag and check it:
```bash
scripts/set_exposure 2 bright-sun
scripts/set_exposure 0 bright-sun

ros2 launch auv_camera_bringup dwe_ros2_dual.launch.py record:=true \
    bag_output:=/home/nemo/auv_bags/exposure_trial_bright_sun

ros2 bag info /home/nemo/auv_bags/exposure_trial_bright_sun
```
Then check it -- no network needed, `rviz2`/`rqt_image_view` aren't
installed on this vehicle and can't be `apt install`ed on-site either.
`scripts/check_exposure.py` decodes a few sample frames straight from the
bag with OpenCV and reports the saturated-pixel percentage per camera:
```bash
python3 scripts/check_exposure.py /home/nemo/auv_bags/exposure_trial_bright_sun

# to actually look at a frame (needs eog, already installed):
python3 scripts/check_exposure.py /home/nemo/auv_bags/exposure_trial_bright_sun \
    --save-dir /tmp/frames && eog /tmp/frames
```
Exits 1 and prints `<-- OVEREXPOSED` on any frame >=20% saturated pixels
(the real ocean-test whiteout measured ~99%; a properly exposed frame
measured ~0.1%). If it's still blown out, step up to `bright-sun-dark`, or
use `custom` to dial in a value between `bright-sun`'s 20 and `manual`'s
100.

Note: setting these via `v4l2-ctl` (what `set_exposure` does) is the
reliable path. `dwe_ros2_parser` also has `auto_exposure`/`exposure`
parameters that set the same two controls through OpenCV, and those are
confirmed to work correctly too -- but `set_exposure` lets you iterate on
values live, on the spot, without restarting the ROS node each time.

# Camera sync (FSIN Leader / Follower)

## Current state

Both stellarHDs report as **Follower** (`0c45:6368`, `iProduct "stellarHD
Follower"`, both serial `DWE-0002`). The FSIN line between them is wired,
but a Follower never *drives* FSIN -- it only listens. So today the wire
carries nothing and the sensors are not phase-locked.

## Leader-Follower vs Follower-Follower

Both DWE topologies use the same single **FSIN** pin (5-pin pigtail:
`5V D- D+ GND FSIN`). Leader→Follower puts the clock on FSIN from one
camera; Follower-only puts it there from an external source (DWE Frame
Sync Module `3961:5000`, or an Arduino/FTDI PWM). The wiring you already
have is correct for either.

**Decision: Leader-Follower.** Two cameras, no external clock, sealed
hull -- no reason to add a board. Follower-only is only worth it for a 3rd
camera or syncing to an IMU/strobe.

## Flashing one camera to Leader

The role is baked into the firmware and changes the USB PID
(`6368` Follower → `6367` Leader). It is **not** a V4L2/UVC control and
cannot be set from Linux -- dweOS only *reads* the role. The only tool is
DWE's **Firmware Loader v1.0.4, Windows only** ("Linux coming soon").
The camera has to come out of the hull.

Flash the **LEFT** camera (`/dev/dwe_camera_left`, USB port `1-2.2`,
`/dev/video2`). Label the housing and the plug first -- the two units are
otherwise USB-identical, and the udev rules key on port path.

At the Windows box, with **every** camera-using app closed first
(Teams/Zoom/Camera/browser webcam tabs):

1. Plug in that one camera only. Loader → refresh → card says `Follower`.
2. Version dropdown → **Leader** → **Flash Firmware**. ~20–30 s.
3. Wait for *"Firmware burning success!"* Do not unplug or close the app.
4. Refresh → card says `Leader`.
5. **Never** use Recovery Mode unless a flash was actually interrupted --
   it skips the board-model check and can permanently brick the unit.

Reinstall into the **same** port (`1-2.2`). Sanity check:
`v4l2-ctl --list-devices` → one `Leader`, one `Follower`;
`lsusb` → one `0c45:6367`, one `0c45:6368`.

Both cameras must run the same mode (1600×1200 @ 60 MJPG in the launch)
-- the Follower's timing is dictated by the Leader.

## Verifying it actually works -- `scripts/check_sync.py`

**`header.stamp` cannot show sync.** Both cameras clock 60 fps off the
same USB host, so their publish-stamp offset is a flat constant whether
or not FSIN is doing anything -- verified: a Jul 30 bag (no FSIN wire)
and an Aug 14 bag (wire present, both Follower) both show <0.05 ms stamp
drift over 10+ minutes. Rate lock is free; **phase** lock is what FSIN
adds, and only the image content can show it.

A slow-blinking LED can't show it either: a 3 ms shift is <1% of a few-Hz
cycle, so any correlation is a broad flat peak (verified on a synthetic
model). The target must change on the **millisecond** scale.

So: point both cameras at one **phone ms stopwatch** (screen at max
brightness, in the frame centre) and record ~20 s:

```bash
ros2 launch auv_camera_bringup dwe_ros2_dual.launch.py record:=true
python3 scripts/check_sync.py ~/auv_bags/dwe_dual_bag_<stamp>
eog sync_pairs/
```

The tool prints stamp health (fps / dropouts -- confirms both were
streaming) and writes nearest-stamp frame **pairs** side by side. Read the
stopwatch on both halves:

- same ms reading in every pair (or a constant tiny diff) → **SYNCED**
- diff wanders pair to pair, or sits ~8 ms (half a frame) → **NOT SYNCED**

Run it once **before** the flash for a baseline, and once after.

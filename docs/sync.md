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

## Follower-only mode with a Jetson trigger (current setup)

Both cameras are Follower (`3961:1102`, fw `1014`). Both FSIN lines are
wound together and landed on **header pin 31** (`PQ.06` / GPIO11).

Pin 31 has **no hardware PWM** (only GPIO or `extperiph_clk4`, and the
latter cannot divide its 51 MHz parent down to 60 Hz -- `clk_summary`
shows it disabled at 51 MHz). So the trigger is a software-timed GPIO:
`scripts/fsin_trigger.py` -- absolute-deadline `clock_nanosleep`,
`SCHED_FIFO`, pinned to one core. Measured: period 16665.7 us, jitter
std ~50-70 us, 0 edges >500 us off, net drift ~0. Both cameras share the
one edge, so any jitter is common-mode -- the pair stays synced to each
other regardless.

```bash
sudo python3 scripts/fsin_trigger.py            # 60 Hz on pin 31; must print SCHED_FIFO
sudo python3 scripts/fsin_trigger.py --measure 30   # verify jitter under load first
```
The trigger must be running BEFORE the cameras open. Header GPIO is
1.8 V logic; FSIN's threshold is not documented by DWE -- if lock is
intermittent with a clean link and clean edge, a 1.8->3.3 V shifter is
the next thing to try.

## CHECK THE USB LINK FIRST -- before blaming sync

Every sync symptom chased on 2026-08-18 turned out to be a **flapping USB
link on one camera** wearing a disguise: "Follower streams ~12 frames then
stalls", "locks once, fails nine times", "0.0 fps with the trigger on" --
all were the right camera dropping off the bus (`error -71` EPROTO,
`USB disconnect`, re-enumerate). A camera that isn't enumerated reads as
0 fps in every tool, indistinguishable from a trigger fault. And a dead
`sudo` wrapper can make `pgrep` claim the trigger is running when the pin
is static.

So, in this order, every time:
```bash
lsusb | grep -c stellar                       # must be 2
sudo dmesg -w | grep -iE 'usb 1-2\.[12]|error -71'   # must stay QUIET under load
python3 scripts/check_lock.py -n 1 -s 30      # both ~60 fps, trigger OFF -> link is good
```
Only then start the trigger and re-run `check_lock.py`. `error -71` on
one port only, with the other camera fine on the same hub/trigger, means
that camera's connector or pigtail (`5V D- D+ GND FSIN` -- FSIN work can
disturb the adjacent data pins). Swap the cameras between ports: fault
follows the camera -> its cable/pigtail; fault stays on the port -> hub/power.

#!/usr/bin/env python3
# Objective: A GUI to Tune the stellarHD cams via V4L2 controls.
import re
import subprocess
import sys

import matplotlib.pyplot as plt
from matplotlib.widgets import Slider, RadioButtons, CheckButtons, Button

# camera_1 = LEFT = /dev/video2, camera_2 = RIGHT = /dev/video0
CAMERAS = [('camera_1 (/dev/video2)', 2), ('camera_2 (/dev/video0)', 0)]

# name, min, max, default
SLIDER_CONTROLS = [
    ('brightness', -64, 64, 0),
    ('contrast', 0, 64, 42),
    ('saturation',0, 128, 64),
    ('hue', -40, 40, 0),
    ('gamma', 72, 500,100),
    ('gain', 0, 100, 0),
    ('white_balance_temperature', 2800, 6500, 4600),
    ('sharpness', 0, 6, 3),
    ('backlight_compensation', 0, 20, 5),
    ('exposure_time_absolute', 1, 5000,  157),
]

# bool controls for CheckButtons
# menu controls for RadioButtons. Only 1 (Manual) and 3 (Aperture Priority) are valid for auto_exposure on this camera (confirmed via
# `v4l2-ctl --list-ctrls-menus`); power_line_frequency is the standard UVC 0=Disabled/1=50Hz/2=60Hz menu.
BOOL_CONTROLS = ['white_balance_automatic', 'exposure_dynamic_framerate']
AUTO_EXPOSURE_OPTIONS = [('Manual (1)', 1), ('Aperture Priority (3)', 3)]
PLF_OPTIONS = [('Disabled (0)', 0), ('50 Hz (1)', 1), ('60 Hz (2)', 2)]
VALUE_RE = re.compile(r'^\s*(\S+)\s+0x[0-9a-fA-F]+\s+\((\w+)\)\s*:.*?value=(-?\d+)')


def read_all_ctrls(video_index):
    # {control_name: int_value} for every control on /dev/video<video_index>
    out = subprocess.run(
        ['v4l2-ctl', f'--device=/dev/video{video_index}', '--list-ctrls'],
        capture_output=True, text=True, check=True).stdout
    values = {}
    for line in out.splitlines():
        m = VALUE_RE.match(line)
        if m:
            values[m.group(1)] = int(m.group(3))
    return values


def set_ctrl(video_index, name, value):
    subprocess.run(
        ['v4l2-ctl', f'--device=/dev/video{video_index}', f'--set-ctrl={name}={int(value)}'],
        capture_output=True, text=True)
    print(f"/dev/video{video_index}: {name}={int(value)}")


class ExposureTuner:
    def __init__(self, initial_index):
        self.video_index = initial_index
        self.fig = plt.figure(figsize=(7.5, 10.5))
        self.fig.canvas.manager.set_window_title('DWE exposure tuner')
        self.sliders = {}
        self._build_top_controls()
        self._build_sliders()
        self._sync_from_device()

    # ---- layout ----
    def _build_top_controls(self):
        self.fig.text(0.5, 0.975, 'DWE stellarHD live V4L2 tuner', ha='center', fontsize=13, fontweight='bold')

        ax_cam = self.fig.add_axes([0.04, 0.87, 0.32, 0.075])
        ax_cam.set_title('camera', fontsize=9)
        self.r_camera = RadioButtons(ax_cam, [c[0] for c in CAMERAS])
        self.r_camera.on_clicked(self._on_camera_change)

        ax_ae = self.fig.add_axes([0.40, 0.87, 0.27, 0.075])
        ax_ae.set_title('auto_exposure', fontsize=9)
        self.r_auto_exposure = RadioButtons(
            ax_ae, [o[0] for o in AUTO_EXPOSURE_OPTIONS])
        self.r_auto_exposure.on_clicked(self._on_auto_exposure_change)

        ax_plf = self.fig.add_axes([0.70, 0.87, 0.26, 0.075])
        ax_plf.set_title('power_line_frequency', fontsize=9)
        self.r_plf = RadioButtons(ax_plf, [o[0] for o in PLF_OPTIONS])
        self.r_plf.on_clicked(self._on_plf_change)

        ax_bool = self.fig.add_axes([0.04, 0.800, 0.5, 0.06])
        self.c_bool = CheckButtons(ax_bool, BOOL_CONTROLS, [True, False])
        self.c_bool.on_clicked(self._on_bool_change)

        ax_reset = self.fig.add_axes([0.62, 0.810, 0.16, 0.045])
        self.b_reset = Button(ax_reset, 'Reset defaults')
        self.b_reset.on_clicked(self._on_reset)

        ax_refresh = self.fig.add_axes([0.80, 0.810, 0.16, 0.045])
        self.b_refresh = Button(ax_refresh, 'Refresh')
        self.b_refresh.on_clicked(lambda _evt: self._sync_from_device())

    def _build_sliders(self):
        top, bottom, gap = 0.75, 0.04, 0.068
        n = len(SLIDER_CONTROLS)
        for i, (name, lo, hi, default) in enumerate(SLIDER_CONTROLS):
            y = top - i * gap
            ax = self.fig.add_axes([0.30, y, 0.62, 0.03])
            s = Slider(ax, name, lo, hi, valinit=default, valstep=1)
            s.on_changed(lambda val, n=name: self._on_slider_change(n, val))
            self.sliders[name] = s

    # ---- state sync :
    def _sync_from_device(self):
        values = read_all_ctrls(self.video_index)
        for name, slider in self.sliders.items():
            if name in values:
                slider.eventson = False
                slider.set_val(values[name])
                slider.eventson = True
        if 'white_balance_automatic' in values or 'exposure_dynamic_framerate' in values:
            states = self.c_bool.get_status()
            for idx, name in enumerate(BOOL_CONTROLS):
                want = bool(values.get(name, states[idx]))
                if want != states[idx]:
                    self.c_bool.set_active(idx)
        if 'auto_exposure' in values:
            label = next((l for l, v in AUTO_EXPOSURE_OPTIONS if v == values['auto_exposure']), None)
            if label:
                self.r_auto_exposure.set_active([l for l, _ in AUTO_EXPOSURE_OPTIONS].index(label))
        if 'power_line_frequency' in values:
            label = next((l for l, v in PLF_OPTIONS if v == values['power_line_frequency']), None)
            if label:
                self.r_plf.set_active([l for l, _ in PLF_OPTIONS].index(label))
        self.fig.canvas.draw_idle()
        print(f"-- synced from /dev/video{self.video_index} --")

    # ---- callbacks :
    def _on_camera_change(self, label):
        self.video_index = dict(CAMERAS)[label]
        self._sync_from_device()

    def _on_slider_change(self, name, val):
        set_ctrl(self.video_index, name, val)

    def _on_bool_change(self, label):
        states = dict(zip(BOOL_CONTROLS, self.c_bool.get_status()))
        set_ctrl(self.video_index, label, 1 if states[label] else 0)

    def _on_auto_exposure_change(self, label):
        set_ctrl(self.video_index, 'auto_exposure', dict(AUTO_EXPOSURE_OPTIONS)[label])

    def _on_plf_change(self, label):
        set_ctrl(self.video_index, 'power_line_frequency', dict(PLF_OPTIONS)[label])

    def _on_reset(self, _evt):
        for name, _lo, _hi, default in SLIDER_CONTROLS:
            set_ctrl(self.video_index, name, default)
        set_ctrl(self.video_index, 'white_balance_automatic', 1)
        set_ctrl(self.video_index, 'exposure_dynamic_framerate', 0)
        set_ctrl(self.video_index, 'auto_exposure', 3)
        set_ctrl(self.video_index, 'power_line_frequency', 2)
        self._sync_from_device()


def main():
    initial_index = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    tuner = ExposureTuner(initial_index)
    plt.show()


if __name__ == '__main__':
    main()

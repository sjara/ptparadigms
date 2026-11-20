"""
Run a 6-port paradigm on a computer without the rig.

Replaces the camera and the Arduino with simulated versions, so a paradigm
(e.g. click_only_6_port_shaping.py) can be tested end to end on a laptop.
Neither the paradigm file nor the phonotaxis package is modified: the
replacements are patched in at startup, before the paradigm is created.

USAGE
    python sim/simulate_rig.py PARADIGM_FILE [--mute]

    e.g.  python sim/simulate_rig.py click_only_6_port_shaping.py

A "Rig simulator" window opens next to the paradigm:
  - Simulated mouse: a black blob on a white arena (the frames fed to the
    paradigm's video tracking). Click and drag to move it. The paradigm's
    initiation zone is drawn on top for reference.
  - Pokes: with the simulator window focused, press keys 1-6 to poke ports
    A-F (key down = beam broken, key up = beam restored).
  - Port indicators light up while poked (blue) and while the paradigm has
    the port's valve open (green). The current trial's target is outlined.

Options
    --mute   Do not play sounds (everything else, including timing, is kept).

REQUIREMENTS / ASSUMPTIONS
  - phonotaxis on branch joanna_rig (paradigms use arduinomodule_6_port,
    videomodule and the ArduinoThread signal interface defined there).
  - Rig-specific settings needed by the 6-port paradigms (INPUT_PINS,
    OUTPUT_PINS, PORT_MAP, ...) are set here, in memory only; the local
    config.py is not modified. CAMERA_TYPE is forced to 'webcam' and
    HARDWARE_INTERFACE to 'arduino', so the paradigm takes its normal
    hardware path with the simulated devices.
  - Paths (DATA_PATH, VIDEO_PATH) still come from the local config.py.
    Sessions save data/video/journal there as on the rig.
"""

import argparse
import os
import runpy
import sys
import threading
import time

import cv2
import numpy as np
from PyQt6 import QtCore, QtGui, QtWidgets

from phonotaxis import config

FRAME_WIDTH = 640
FRAME_HEIGHT = 480
SIMULATED_FPS = 30
BLOB_HALF_AXES = (24, 12)     # pixels; ellipse ~ mouse seen from above
BLOB_ANGLE_DEG = 30
PORT_KEYS = ('A', 'B', 'C', 'D', 'E', 'F')
POKE_KEYBOARD_KEYS = ('1', '2', '3', '4', '5', '6')

# Settings of the 6-port rig that the paradigms expect (from JoAnna's rig
# config.py). Sound channels follow her PORT_MAP.
SOUND_CHANNEL_EACH_PORT = {'A': 1, 'B': 0, 'C': 2, 'D': 3, 'E': 5, 'F': 4}
VALVE_PIN_EACH_PORT = {'A': 10, 'B': 2, 'C': 3, 'D': 4, 'E': 5, 'F': 6}
RIG_CONFIG = {
    'CAMERA_TYPE': 'webcam',
    'CAMERA_INDEX': 0,
    'HARDWARE_INTERFACE': 'arduino',
    'ARDUINO_INPUTS_INVERTED': True,
    'GUI_DISPLAY_MAX_FPS': 60,
    'INPUT_PINS': {port: index + 1 for index, port in enumerate(PORT_KEYS)},
    'OUTPUT_PINS': {f'Valve{port}': VALVE_PIN_EACH_PORT[port]
                    for port in PORT_KEYS},
    'N_AUDIO_CHANNELS': 6,
    'ALL_PORTS': PORT_KEYS,
    'SPEAKER_SET_OPTION_1': ('A', 'C', 'E'),
    'SPEAKER_SET_OPTION_2': ('B', 'D', 'F'),
    'PORT_MAP': {
        port: {'valve': f'Valve{port}', 'input': port,
               'channel': SOUND_CHANNEL_EACH_PORT[port],
               'jack': 'simulated',
               'label': f'Port {port} (ch {SOUND_CHANNEL_EACH_PORT[port]})'}
        for port in PORT_KEYS
    },
}


class SimulatedMouse:
    """Position of the simulated mouse (shared by GUI and video threads)."""

    def __init__(self):
        self._lock = threading.Lock()
        self._position = (FRAME_WIDTH * 0.2, FRAME_HEIGHT * 0.2)

    def set_position(self, xpos, ypos):
        xpos = min(max(xpos, 0), FRAME_WIDTH - 1)
        ypos = min(max(ypos, 0), FRAME_HEIGHT - 1)
        with self._lock:
            self._position = (xpos, ypos)

    def get_position(self):
        with self._lock:
            return self._position


SIMULATED_MOUSE = SimulatedMouse()


class SimulatedCamera:
    """Stand-in for cv2.VideoCapture producing frames with a black blob."""

    def __init__(self, simulated_mouse):
        self.simulated_mouse = simulated_mouse
        self.frame_interval = 1.0 / SIMULATED_FPS
        self.next_frame_time = None

    def isOpened(self):
        return True

    def get(self, property_id):
        values = {cv2.CAP_PROP_FPS: SIMULATED_FPS,
                  cv2.CAP_PROP_FRAME_WIDTH: FRAME_WIDTH,
                  cv2.CAP_PROP_FRAME_HEIGHT: FRAME_HEIGHT}
        return values.get(property_id, 0)

    def set(self, property_id, value):
        return False

    def read(self):
        # Pace frames like a real camera (VideoThread.run does not throttle)
        now = time.perf_counter()
        if self.next_frame_time is None:
            self.next_frame_time = now
        if self.next_frame_time > now:
            time.sleep(self.next_frame_time - now)
        self.next_frame_time = max(self.next_frame_time + self.frame_interval,
                                   time.perf_counter() - self.frame_interval)
        frame = np.full((FRAME_HEIGHT, FRAME_WIDTH, 3), 255, dtype=np.uint8)
        (xpos, ypos) = self.simulated_mouse.get_position()
        cv2.ellipse(frame, (int(xpos), int(ypos)), BLOB_HALF_AXES,
                    BLOB_ANGLE_DEG, 0, 360, (0, 0, 0), thickness=-1)
        return (True, frame)

    def release(self):
        pass


def simulated_initialize_camera(video_thread):
    """Replacement for VideoThread.initialize_camera()."""
    video_thread.cap = SimulatedCamera(SIMULATED_MOUSE)


class SimulatedArduinoThread(QtCore.QObject):
    """
    Stand-in for arduinomodule_6_port.ArduinoThread.

    Same signals and the methods the paradigms call. Pokes are generated
    with poke(), which emits threshold_crossed like a real IR beam break
    (falling edge = beam broken, as the paradigms expect).
    """
    arduino_ready = QtCore.pyqtSignal()
    arduino_error = QtCore.pyqtSignal(str)
    threshold_crossed = QtCore.pyqtSignal(int, float, bool)  # pin, value, rising
    output_changed = QtCore.pyqtSignal(str, bool)            # simulator only

    latest_instance = None

    def __init__(self, port=None, n_inputs=None, thresholds=None, debug=False):
        super().__init__()
        self.thresholds = dict(thresholds or {})
        self.outputs = {}
        SimulatedArduinoThread.latest_instance = self

    def start(self):
        QtCore.QTimer.singleShot(0, self.arduino_ready.emit)

    def stop(self):
        pass

    def wait(self, *args):
        return True

    def isRunning(self):
        return False

    def set_threshold(self, pin_number, threshold_value):
        self.thresholds[pin_number] = threshold_value

    def remove_threshold(self, pin_number):
        self.thresholds.pop(pin_number, None)

    def get_current_values(self):
        return {}

    def set_digital_output(self, pin_name, state):
        self.outputs[pin_name] = bool(state)
        self.output_changed.emit(pin_name, bool(state))

    def poke(self, port_key, poke_in):
        input_name = config.PORT_MAP[port_key]['input']
        pin_number = config.INPUT_PINS[input_name]
        # Beam broken -> value drops (falling edge); restored -> rising edge
        value = 0.0 if poke_in else 1.0
        self.threshold_crossed.emit(pin_number, value, not poke_in)


class ArenaCanvas(QtWidgets.QWidget):
    """Shows the simulated arena; click and drag to move the mouse."""

    def __init__(self, paradigm, paradigm_globals, parent=None):
        super().__init__(parent)
        self.paradigm = paradigm
        self.display_mask = paradigm_globals.get('DEFAULT_MASK')
        self.setFixedSize(FRAME_WIDTH, FRAME_HEIGHT)
        self.setCursor(QtCore.Qt.CursorShape.CrossCursor)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._move_mouse_to(event.position())

    def mouseMoveEvent(self, event):
        if event.buttons() & QtCore.Qt.MouseButton.LeftButton:
            self._move_mouse_to(event.position())

    def _move_mouse_to(self, point):
        SIMULATED_MOUSE.set_position(point.x(), point.y())
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QtGui.QColor('white'))
        if self.display_mask:
            (mask_cx, mask_cy, mask_radius) = self.display_mask
            painter.setPen(QtGui.QPen(QtGui.QColor('#bbbbbb'), 1,
                                      QtCore.Qt.PenStyle.DashLine))
            painter.drawEllipse(QtCore.QPointF(mask_cx, mask_cy),
                                mask_radius, mask_radius)
        iz_tracker = getattr(self.paradigm, 'iz_tracker', None)
        if iz_tracker is not None and iz_tracker.radius > 0:
            iz_color = QtGui.QColor('#2e7d32' if iz_tracker.in_zone
                                    else '#1565c0')
            painter.setPen(QtGui.QPen(iz_color, 2))
            painter.drawEllipse(QtCore.QPointF(iz_tracker.cx, iz_tracker.cy),
                                iz_tracker.radius, iz_tracker.radius)
            painter.drawText(QtCore.QPointF(iz_tracker.cx - 8,
                                            iz_tracker.cy - iz_tracker.radius - 6),
                             'IZ')
        (xpos, ypos) = SIMULATED_MOUSE.get_position()
        painter.save()
        painter.translate(xpos, ypos)
        painter.rotate(BLOB_ANGLE_DEG)
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(QtGui.QColor('black'))
        painter.drawEllipse(QtCore.QPointF(0, 0),
                            BLOB_HALF_AXES[0], BLOB_HALF_AXES[1])
        painter.restore()
        painter.end()


class RigSimulatorWindow(QtWidgets.QWidget):
    """Arena canvas + keyboard pokes + port/valve indicators."""

    STYLE_IDLE = ('background: #eeeeee; border: 2px solid #999999; '
                  'border-radius: 4px; padding: 4px;')
    STYLE_POKED = ('background: #64b5f6; border: 2px solid #999999; '
                   'border-radius: 4px; padding: 4px;')
    STYLE_VALVE = ('background: #81c784; border: 2px solid #999999; '
                   'border-radius: 4px; padding: 4px;')

    def __init__(self, paradigm, paradigm_globals):
        super().__init__()
        self.paradigm = paradigm
        self.setWindowTitle('Rig simulator')
        self.poked_ports = set()
        self.open_valves = set()
        self.arduino = None

        self.canvas = ArenaCanvas(paradigm, paradigm_globals)
        help_label = QtWidgets.QLabel(
            'Click+drag: move mouse.   Keys 1-6: poke ports A-F '
            '(this window must have focus).')
        self.status_label = QtWidgets.QLabel('')
        indicator_layout = QtWidgets.QHBoxLayout()
        self.port_indicators = {}
        for port_key, keyboard_key in zip(PORT_KEYS, POKE_KEYBOARD_KEYS):
            indicator = QtWidgets.QLabel(f'{keyboard_key}: {port_key}')
            indicator.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            indicator.setStyleSheet(self.STYLE_IDLE)
            indicator_layout.addWidget(indicator)
            self.port_indicators[port_key] = indicator

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.canvas)
        layout.addWidget(help_label)
        layout.addLayout(indicator_layout)
        layout.addWidget(self.status_label)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)

        self._connect_arduino()
        self.refresh_timer = QtCore.QTimer(self)
        self.refresh_timer.timeout.connect(self._refresh)
        self.refresh_timer.start(int(1000 / SIMULATED_FPS))

    def _connect_arduino(self):
        self.arduino = SimulatedArduinoThread.latest_instance
        if self.arduino is not None:
            self.arduino.output_changed.connect(self._on_output_changed)

    def _on_output_changed(self, output_name, state):
        for port_key in PORT_KEYS:
            if config.PORT_MAP[port_key]['valve'] == output_name:
                if state:
                    self.open_valves.add(port_key)
                else:
                    self.open_valves.discard(port_key)

    def keyPressEvent(self, event):
        port_key = self._port_for_key(event)
        if port_key is None:
            return super().keyPressEvent(event)
        if not event.isAutoRepeat() and port_key not in self.poked_ports:
            self.poked_ports.add(port_key)
            if self.arduino is not None:
                self.arduino.poke(port_key, poke_in=True)

    def keyReleaseEvent(self, event):
        port_key = self._port_for_key(event)
        if port_key is None:
            return super().keyReleaseEvent(event)
        if not event.isAutoRepeat() and port_key in self.poked_ports:
            self.poked_ports.discard(port_key)
            if self.arduino is not None:
                self.arduino.poke(port_key, poke_in=False)

    @staticmethod
    def _port_for_key(event):
        key_text = event.text()
        if key_text in POKE_KEYBOARD_KEYS:
            return PORT_KEYS[POKE_KEYBOARD_KEYS.index(key_text)]
        return None

    def _refresh(self):
        target_port = (getattr(self.paradigm, 'current_trial_port', None)
                       if getattr(self.paradigm, 'trial_active', False)
                       else None)
        for port_key, indicator in self.port_indicators.items():
            if port_key in self.open_valves:
                style = self.STYLE_VALVE
            elif port_key in self.poked_ports:
                style = self.STYLE_POKED
            else:
                style = self.STYLE_IDLE
            if port_key == target_port:
                style = style.replace('border: 2px solid #999999',
                                      'border: 3px solid #d32f2f')
            indicator.setStyleSheet(style)
        if not getattr(self.paradigm, 'session_running', False):
            status = 'Session not running.'
        elif target_port is not None:
            status = f'Trial active: target port {target_port} (outlined in red).'
        elif getattr(self.paradigm, 'in_iti', False):
            status = 'ITI.'
        else:
            status = 'Waiting for the mouse to dwell in the IZ.'
        self.status_label.setText(status)
        self.canvas.update()


def main():
    parser = argparse.ArgumentParser(
        description='Run a 6-port paradigm with a simulated camera and Arduino.')
    parser.add_argument('paradigm_file', help='Paradigm script to run')
    parser.add_argument('--mute', action='store_true', help='Do not play sounds')
    args = parser.parse_args()
    paradigm_path = os.path.abspath(args.paradigm_file)

    for setting_name, setting_value in RIG_CONFIG.items():
        setattr(config, setting_name, setting_value)

    from phonotaxis import videomodule
    from phonotaxis import arduinomodule_6_port
    from phonotaxis import gui
    videomodule.VideoThread.initialize_camera = simulated_initialize_camera
    arduinomodule_6_port.ArduinoThread = SimulatedArduinoThread
    if args.mute:
        from phonotaxis import soundmodule
        soundmodule.SoundPlayer.play = lambda player, sound_id: None

    # Load the paradigm without running its __main__ block (which runs the
    # Qt event loop twice; see phonotaxis TODO about gui.create_app).
    sys.path.insert(0, os.path.dirname(paradigm_path))
    sys.argv = [paradigm_path]
    paradigm_globals = runpy.run_path(paradigm_path,
                                      run_name='simulated_paradigm')
    paradigm_class = paradigm_globals['Paradigm']

    class SimulatedParadigm(paradigm_class):
        def __init__(self, *init_args, **init_kwargs):
            super().__init__(*init_args, **init_kwargs)
            # The paradigm's own __main__ block maximizes the window; do it
            # here since that block is not run (create_app calls show()).
            self.setWindowState(QtCore.Qt.WindowState.WindowMaximized)
            self.setWindowTitle(self.windowTitle() + '  [SIMULATED RIG]')
            self.rig_simulator = RigSimulatorWindow(self, paradigm_globals)
            self.rig_simulator.show()

        def closeEvent(self, event):
            super().closeEvent(event)
            if event.isAccepted():
                self.rig_simulator.close()

    gui.create_app(SimulatedParadigm)


if __name__ == '__main__':
    main()

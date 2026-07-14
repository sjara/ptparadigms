"""
Locomotor Action Space Learning Paradigm.

This paradigm requires mice to explore their locomotion "action space" (velocity
and angular velocity contingencies) to earn points and trigger water rewards,
guided by auditory feedback.

The computational work is performed asynchronously in a background thread to prevent
GUI freeze, and the results are visualized in real time.
"""

import sys
import os
import time
import numpy as np
from bidict import bidict
from PyQt6.QtWidgets import QWidget, QMainWindow, QHBoxLayout, QVBoxLayout, QLabel, QCheckBox
from PyQt6.QtCore import QThread, pyqtSignal, pyqtSlot, QPointF, Qt
from PyQt6.QtGui import QPainter, QColor, QPen, QPolygonF

# Import phonotaxis framework
from phonotaxis import gui
from phonotaxis import widgets
from phonotaxis import soundmodule
from phonotaxis import controller
from phonotaxis import arduinomodule
from phonotaxis import videomodule
from phonotaxis import statematrix
from phonotaxis import utils
from phonotaxis import emulator
from phonotaxis import savedata
from phonotaxis import config

# Import locomotor processor
from locomotion_processor import LocomotionProcessor, LocomotionStrategy
from phonotaxis.videoworkers import ProcessWorker
from phonotaxis.sharedbuffer import ResultBuffer


try:
    import cv2
except ImportError:
    cv2 = None

PARADIGM_NAME = 'locomotion_action_space'

# --- Video tracking defaults ---
DEFAULT_MASK = [500, 360, 100]
DEFAULT_IZ_RADIUS_PX = 150

# --- Sound settings ---
SAMPLING_RATE = 44100

# --- Sound IDs ---
SOUND_ID_TICK = 10     # Point increment sound
SOUND_ID_BEACON = 11   # Sound indicating reward is available
SOUND_ID_REWARD = 12   # Sound played during water delivery

# --- Inputs and Outputs ---
# Virtual input 'Goal' creates 'Goalin' and 'Goalout' (indices 0 and 1)
VIDEO_INPUTS = ['Goal']
ARDUINO_INPUTS = list(config.INPUT_PINS.keys())
INPUTS = VIDEO_INPUTS + ARDUINO_INPUTS  # Goal, L, R
OUTPUTS = list(config.OUTPUT_PINS.keys())


class LocomotionWorker(QThread):
    """
    Background worker that receives raw camera tracking coordinates,
    updates the locomotion processor, and emits thread-safe signals for the GUI.
    """
    state_updated = pyqtSignal(dict)
    point_scored = pyqtSignal(int)
    goal_reached = pyqtSignal()

    def __init__(self, processor: LocomotionProcessor, loco_strategy: LocomotionStrategy = None):
        super().__init__()
        self.processor = processor
        self.loco_strategy = loco_strategy
        self.goal_notified = False
        self.last_points = 0.0

    def reset_goal(self):
        """Reset the goal flag to allow triggering a new goal."""
        self.goal_notified = False
        self.last_points = 0.0

    @pyqtSlot(float, object, tuple, object)
    def on_frame_processed(self, timestamp: float, frame: np.ndarray, points: tuple, contour: object):
        """
        Slot connected to VideoThread's frame_processed signal.
        Processes kinematics in a thread-safe background loop.
        """
        # Extract centroid coordinates
        centroid = points[0] if points and len(points) > 0 else (-1, -1)
        
        if self.loco_strategy is not None:
            state = self.loco_strategy.get_latest_state()
            if state is None:
                return
        else:
            state = self.processor.process_frame(timestamp, centroid)
            
        points_value = state.points
        prev_pts = self.last_points
        self.last_points = points_value
        
        # Emit calculated state
        self.state_updated.emit(state.to_dict())
        
        # Check if points increased
        if points_value > prev_pts:
            self.point_scored.emit(int(points_value))
            
        # Check if threshold reached
        if points_value >= self.processor.point_threshold and not self.goal_notified:
            self.goal_notified = True
            self.goal_reached.emit()



class RealTimePlotWidget(QWidget):
    """
    High-performance real-time scrolling visualization widget using QPainter.
    Avoids high CPU overhead of Matplotlib, plotting smooth rolling metrics.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(450, 450)
        
        # Trace buffers
        self.history_size = 300
        self.timestamps = []
        self.velocities = []
        self.angular_velocities = []
        self.points = []
        self.contingency_met = []
        
        # Copy of current thresholds
        self.v_thresh = 100.0
        self.w_min = 2.0
        self.w_max = 3.0
        self.p_thresh = 50
        
        # Modern, dark-mode aesthetics
        self.bg_color = QColor(30, 30, 36)
        self.grid_color = QColor(70, 70, 80, 120)
        self.text_color = QColor(230, 230, 240)
        
        self.color_vel = QColor(52, 152, 219)         # Tango Sky Blue
        self.color_omega = QColor(46, 204, 113)       # Chameleon Green
        self.color_pts = QColor(241, 196, 15)         # Bright Amber
        self.color_thresh = QColor(231, 76, 60, 180)   # Coral Red
        self.color_contingency = QColor(155, 89, 182, 35) # Translucent Lavender

    def set_params(self, v_thresh: float, w_min: float, w_max: float, p_thresh: int):
        """Update display boundaries dynamically."""
        self.v_thresh = v_thresh
        self.w_min = w_min
        self.w_max = w_max
        self.p_thresh = p_thresh
        self.update()

    def update_data(self, state_dict: dict):
        """Append incoming state metrics to scrolling trace."""
        self.timestamps.append(state_dict['timestamp'])
        self.velocities.append(state_dict['velocity'])
        self.angular_velocities.append(state_dict['angular_velocity'])
        self.points.append(state_dict['points'])
        self.contingency_met.append(state_dict['contingency_met'])
        
        if len(self.timestamps) > self.history_size:
            self.timestamps.pop(0)
            self.velocities.pop(0)
            self.angular_velocities.pop(0)
            self.points.pop(0)
            self.contingency_met.pop(0)
            
        self.update()

    def clear_data(self):
        """Flush plot data."""
        self.timestamps.clear()
        self.velocities.clear()
        self.angular_velocities.clear()
        self.points.clear()
        self.contingency_met.clear()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w = self.width()
        h = self.height()
        
        # Outer card background
        painter.setBrush(self.bg_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, w, h, 10.0, 10.0)
        
        # Sub-panel layout slices
        padding = 18
        plot_h = (h - 4 * padding) / 3
        
        max_vel = max(self.velocities) if self.velocities else 0.0
        max_omega = max(self.angular_velocities) if self.angular_velocities else 0.0
        max_pts = max(self.points) if self.points else 0
        
        # Draw three sub-axes
        self.draw_subplot(painter, 0, padding, w, plot_h, "Velocity", self.velocities, 
                          0.0, max(150.0, max_vel), self.color_vel, "px/s", 
                          thresh_val=self.v_thresh)
        
        self.draw_subplot(painter, 1, 2 * padding + plot_h, w, plot_h, "Angular Velocity", 
                          self.angular_velocities, 0.0, max(4.0, max_omega), 
                          self.color_omega, "rad/s", band_val=(self.w_min, self.w_max))
                          
        self.draw_subplot(painter, 2, 3 * padding + 2 * plot_h, w, plot_h, "Points Earned", 
                          self.points, 0.0, max(float(self.p_thresh), float(max_pts)), 
                          self.color_pts, "pts", thresh_val=self.p_thresh, 
                          highlight_threshold=True)

    def draw_subplot(self, painter, index, top, w, h, title, data, y_min, y_max, 
                     trace_color, units, thresh_val=None, band_val=None, 
                     highlight_threshold=False):
        left_margin = 70
        right_margin = 90
        plot_w = w - left_margin - right_margin
        
        # Border box
        painter.setPen(QPen(QColor(80, 80, 95), 1.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(int(left_margin), int(top), int(plot_w), int(h), 4.0, 4.0)
        
        # Panel Title
        painter.setPen(self.text_color)
        font = painter.font()
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(12, int(top + 18), title)
        
        # Current Value Display
        curr_val_str = f"0.0 {units}"
        if data:
            curr_val_str = f"{data[-1]:.1f} {units}" if not isinstance(data[-1], int) else f"{data[-1]} {units}"
            
        font.setPointSize(10)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(trace_color)
        painter.drawText(int(w - right_margin + 12), int(top + h/2 + 5), curr_val_str)
        
        y_range = y_max - y_min
        if y_range <= 0.0:
            y_range = 1.0
            
        def to_y_pixel(val):
            frac = (val - y_min) / y_range
            frac = max(0.0, min(1.0, frac))
            return top + h - (frac * h)
            
        # Draw dynamic axis ticks, labels, and grid lines
        ticks = np.linspace(y_min, y_max, 5)
        for i, tick in enumerate(ticks):
            y_py = to_y_pixel(tick)
            
            # Draw tick label on the left margin
            painter.setPen(QColor(130, 130, 140))
            font.setPointSize(7)
            font.setBold(False)
            painter.setFont(font)
            painter.drawText(12, int(y_py + 3), f"{tick:.1f}")
            
            # Draw small tick mark
            painter.drawLine(int(left_margin - 4), int(y_py), int(left_margin), int(y_py))
            
            # Draw dashed grid line for internal ticks
            if i > 0 and i < len(ticks) - 1:
                painter.setPen(QPen(self.grid_color, 1, Qt.PenStyle.DashLine))
                painter.drawLine(int(left_margin), int(y_py), int(left_margin + plot_w), int(y_py))
            
        # Draw threshold boundary
        if thresh_val is not None:
            y_py = to_y_pixel(thresh_val)
            if highlight_threshold and data and data[-1] >= thresh_val:
                painter.setPen(QPen(QColor(46, 204, 113, 200), 2))  # Glowing green success line
            else:
                painter.setPen(QPen(self.color_thresh, 1, Qt.PenStyle.DashDotLine))
            painter.drawLine(int(left_margin), int(y_py), int(left_margin + plot_w), int(y_py))
            
        # Draw contingency target band
        if band_val is not None:
            y_low = to_y_pixel(band_val[0])
            y_high = to_y_pixel(band_val[1])
            painter.setBrush(self.color_contingency)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(int(left_margin), int(y_high), int(plot_w), int(y_low - y_high))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            
        # Draw trace line
        if len(data) > 1:
            poly = QPolygonF()
            n = len(data)
            for i in range(n):
                frac_x = i / (self.history_size - 1)
                px = left_margin + frac_x * plot_w
                py = to_y_pixel(data[i])
                poly.append(QPointF(px, py))
                
            painter.setPen(QPen(trace_color, 2))
            painter.drawPolyline(poly)


class Paradigm(QMainWindow):
    """
    Main Paradigm subclass managing the locomotor learning task session.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Locomotor Action Space Paradigm")
        self.setWindowIcon(gui.create_icon())
        self.name = PARADIGM_NAME

        # -- Connect status logger --
        self.messagebar = gui.Messenger()
        self.messagebar.timed_message.connect(self._show_message)
        self.messagebar.collect('Locomotor Action Space Paradigm initialized')

        # -- Core state objects --
        self.session_running = False
        self.controller = controller.SessionController(debug=False)
        
        # Tracking video display widgetf
        self.video_widget = widgets.VideoWidget(
            controls=True, 
            threshold=config.DEFAULT_BLACK_THRESHOLD if hasattr(config, 'DEFAULT_BLACK_THRESHOLD') else 64,
            minarea=config.DEFAULT_MINIMUM_AREA if hasattr(config, 'DEFAULT_MINIMUM_AREA') else 2000,
            initzone_radius=DEFAULT_IZ_RADIUS_PX,
            mask_radius=DEFAULT_MASK[2]
        )
        self._uncheck_binary_mask_mode()
        self.savedata_widget = savedata.SaveData(datadir=config.DATA_PATH)

        # Real-time data visualization
        self.plot_widget = RealTimePlotWidget()

        # Connect controller signals
        self.controller.session_started.connect(self.start_session)
        self.controller.session_stopped.connect(self.stop_session)
        self.controller.prepare_next_trial.connect(self.prepare_next_trial)
        self.controller.log_message.connect(self.messagebar.collect)
        self.savedata_widget.button.clicked.connect(self.save_to_file)
        self.savedata_widget.log_message.connect(self.messagebar.collect)

        # -- Trial metrics choices container --
        self.results = utils.EnumContainer()
        self.results.labels['reward'] = bidict({'none': 0, 'left': 1, 'right': 2})
        self.results['reward'] = []

        # -- Parameters Container --
        self.session_info = widgets.SessionInfo()
        self.session_info.set_values({
            'subject': 'subject000',
            'trainer': '',
            'maxSessionDuration': float('inf'),
            'maxTrials': float('inf')
        })

        # Locomotor parameters
        self.params = gui.Container()
        self.params['velocityThreshold'] = gui.NumericParam('Velocity threshold', value=100.0, units='px/s',
                                                            group='Locomotion params')
        self.params['angularVelocityMin'] = gui.NumericParam('Angular velocity min', value=2.0, units='rad/s',
                                                            group='Locomotion params')
        self.params['angularVelocityMax'] = gui.NumericParam('Angular velocity max', value=10.0, units='rad/s',
                                                            group='Locomotion params')
        self.params['pointThreshold'] = gui.NumericParam('Point threshold', value=300, units='pts',
                                                            group='Locomotion params')
        self.params['growthRate'] = gui.NumericParam('Growth rate', value=300, units = 'pts/s',
                                                     group='Locomotion params')
        self.params['shrinkRate'] = gui.NumericParam('Shrink rate', value=100, units='pts/s',
                                                      group='Locomotion params')
        self.params['smoothingWindow'] = gui.NumericParam('Smoothing window', value=10, units='frames',
                                                           group='Locomotion params')
        self.loco_params = self.params.layout_group('Locomotion params')
        
        # Audio parameters
        self.params['soundDuration'] = gui.NumericParam('Sound duration', value=0.4, units='s',
                                                        group='Sound params')
        self.params['soundAmplitude'] = gui.NumericParam('Sound amplitude', value=0.5, units='0-1',
                                                        group='Sound params')
        self.sound_params = self.params.layout_group('Sound params')

        # Valve parameters
        self.params['valveDuration'] = gui.NumericParam('Valve duration', value=0.1, units='s', 
                                                        group='Valve params')
        self.valve_params = self.params.layout_group('Valve params')

        # -- Setup layout --
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QHBoxLayout(self.central_widget)

        left_col = QVBoxLayout()
        center_col = QVBoxLayout()
        right_col = QVBoxLayout()
        self.layout.addLayout(left_col, stretch=4)
        self.layout.addLayout(center_col, stretch=5)
        self.layout.addLayout(right_col, stretch=3)

        # Video feed goes to left column
        left_col.addWidget(self.video_widget)
        
        # Real-time plot goes to center column
        center_col.addWidget(self.plot_widget)

        # Session params and actions go to right column
        right_col.addWidget(self.controller.gui)
        right_col.addWidget(self.session_info)
        right_col.addWidget(self.savedata_widget)
        right_col.addWidget(self.loco_params)
        right_col.addWidget(self.valve_params)
        right_col.addWidget(self.sound_params)
        
        # Show configured save directories in the GUI
        paths_label = QLabel(
            f"<b>Data dir:</b> {config.DATA_PATH}<br>"
            f"<b>Video dir:</b> {config.VIDEO_PATH}"
        )
        paths_label.setWordWrap(True)
        paths_label.setStyleSheet("font-size: 10px; color: #555; margin-top: 5px;")
        right_col.addWidget(paths_label)
        
        right_col.addStretch()

        # -- Initialize cameras --
        self.start_video_thread()

        # -- Initialize processing pipeline --
        self.processor = LocomotionProcessor()
        self.loco_strategy = LocomotionStrategy(self.processor)
        
        # Create a bus-driven ProcessWorker for locomotion analysis
        loco_result_buffer = ResultBuffer()
        self.loco_process_worker = ProcessWorker(
            strategy=self.loco_strategy,
            result_buffer=loco_result_buffer,
            name='locomotion',
            bus=self.video_thread.result_bus,
            subscribe_to='contour_tracker',
        )
        self.video_thread.add_process_worker(self.loco_process_worker)
        
        self.worker = LocomotionWorker(self.processor, self.loco_strategy)

        
        # Connect signals
        self.worker.state_updated.connect(self.plot_widget.update_data)
        self.worker.point_scored.connect(self.on_point_scored)
        self.worker.goal_reached.connect(self.on_goal_reached)
        
        # Route frames into background worker thread
        self.video_thread.frame_processed.connect(self.worker.on_frame_processed)
        
        # Startup computation thread
        self.worker.start()

        # -- Audio interface --
        self.sound_player = soundmodule.SoundPlayer()
        self.sound_player.connect_state_machine(self.controller.state_machine)

        # -- State machine --
        self.sm = statematrix.StateMatrix(inputs=INPUTS, outputs=OUTPUTS)

        # Virtual input event offset is 2 because Goal has 2 events (Goalin, Goalout)
        virtual_event_offset = 2

        # Hardware connection
        if config.HARDWARE_INTERFACE == 'arduino':
            self.interface = arduinomodule.ArduinoInterface(inputs=ARDUINO_INPUTS, outputs=OUTPUTS, 
                                                            event_offset=virtual_event_offset,
                                                            debug=True)
            self.messagebar.collect("Connecting to Arduino...")
            self.interface.arduino_ready.connect(lambda: self.messagebar.collect("Arduino ready."))
            self.interface.arduino_error.connect(
                lambda err: self.messagebar.collect(f"Arduino error: {err}"))
        elif config.HARDWARE_INTERFACE == 'emulator':
            self.interface = emulator.EmulatorWidget(inputs=ARDUINO_INPUTS, outputs=OUTPUTS,
                                                     event_offset=virtual_event_offset)
            self.interface.show()
            
        self.interface.connect_state_machine(self.controller.state_machine)
        
        # Initialize processor parameters and plot widget parameters from the GUI settings
        self.update_processor_params()

        # Connect GUI parameters to update the processor and plot widget in real-time
        for key in ['velocityThreshold', 'angularVelocityMin', 'angularVelocityMax', 'pointThreshold', 'growthRate', 'shrinkRate', 'smoothingWindow']:
            self.params[key].editWidget.textChanged.connect(self.update_processor_params)

    def _show_message(self, msg):
        self.statusBar().showMessage(str(msg))
        print(msg)

    def _uncheck_binary_mask_mode(self):
        """Turn off the VideoWidget's binary/masked-view toggle."""
        if not hasattr(self, 'video_widget') or not self.video_widget.controls_visible:
            return
        try:
            for child in self.video_widget.findChildren(QCheckBox):
                txt = child.text().lower()
                if 'binary' in txt or 'mask' in txt:
                    child.setChecked(False)
        except Exception as e:
            print(f"[Paradigm] Could not reset binary/mask toggle: {e}")

    def start_video_thread(self):
        """Spawn the background frame grabbing thread."""
        video_source = getattr(config, 'VIDEO_PLAYBACK_PATH', None)
        fps_limit = getattr(config, 'VIDEO_PLAYBACK_FPS', None)
        loop = getattr(config, 'VIDEO_PLAYBACK_LOOP', False)
        
        if video_source is None:
            video_source = config.CAMERA_INDEX
            
        self.video_thread = videomodule.VideoThread(
            video_source,
            mode='binary',
            tracking=True,
            fps_limit=fps_limit,
            loop=loop,
            start_paused=isinstance(video_source, str)
        )
        # Apply standard settings
        self.video_thread.set_threshold(config.DEFAULT_BLACK_THRESHOLD if hasattr(config, 'DEFAULT_BLACK_THRESHOLD') else 128)
        self.video_thread.set_minarea(config.DEFAULT_MINIMUM_AREA if hasattr(config, 'DEFAULT_MINIMUM_AREA') else 4000)
        
        # Determine actual video dimensions and dynamically scale mask & initzone
        cap = self.video_thread.cap
        if cap is not None and cap.isOpened():
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cx = width // 2
            cy = height // 2
            # Scale mask radius relative to default 250 for 640 width
            radius = int(250 * (width / 640.0))
            mask = [cx, cy, radius]
            # Scale initzone radius relative to default
            iz_radius = int(DEFAULT_IZ_RADIUS_PX * (width / 640.0))
        else:
            mask = DEFAULT_MASK
            cx, cy, radius = DEFAULT_MASK
            iz_radius = DEFAULT_IZ_RADIUS_PX

        self.video_thread.set_circular_mask(mask)
        self.video_widget.connect_video_thread(self.video_thread)
        
        # Connect initzone slider to custom handler
        if self.video_widget.controls_visible:
            self.video_widget.initzone_radius_slider.value_changed.connect(
                self._on_iz_radius_changed
            )
            
        self.iz_radius = iz_radius
        self.iz_cx = cx
        self.iz_cy = cy
        
        self.video_thread.frame_processed.connect(self.update_image)
        self.video_thread.start()

    def _on_iz_radius_changed(self, radius):
        self.iz_radius = float(radius)

    def update_image(self, timestamp, frame, points, contour):
        """Slot for video frame widget refresh."""
        frame_out = self._draw_overlays(frame)
        self.video_widget.display_frame(frame_out, points, contour=contour)

    def _draw_overlays(self, frame):
        """Draw the IZ circle on the (grayscale) display frame."""
        if cv2 is None or frame is None:
            return frame
        try:
            out = frame
            
            # Draw IZ
            cx = int(self.iz_cx)
            cy = int(self.iz_cy)
            r = int(self.iz_radius)
            
            # Dynamic visualization depending on goal state
            if self.worker.goal_notified:
                intensity = 255
                thickness = 3
            elif getattr(self, 'session_running', False):
                intensity = 150
                thickness = 2
            else:
                intensity = 100
                thickness = 1
                
            cv2.circle(out, (cx, cy), r, intensity, thickness)
            cv2.drawMarker(out, (cx, cy), intensity,
                           markerType=cv2.MARKER_CROSS,
                           markerSize=8, thickness=1)
            return out
        except Exception:
            return frame

    def start_session(self):
        """Callback triggered when controller starting."""
        if not self.session_running:
            session_duration = self.session_info.get_value('maxSessionDuration')
            self.controller.set_session_duration(session_duration)
            self.session_running = True
            
            # Start video recording
            subject = self.session_info.get_value('subject')
            date_str = time.strftime('%Y%m%d_%H%M%S', time.localtime())
            filename = f"{subject}_{PARADIGM_NAME}_{date_str}.mp4"
            video_filepath = os.path.join(config.VIDEO_PATH, subject, filename)
            self.video_thread.start_recording(video_filepath)
            self.messagebar.collect(f"Video recording started: {video_filepath}")

    def stop_session(self):
        """Callback triggered when controller stopping."""
        if self.session_running:
            self.session_running = False
            self.video_thread.stop_recording()
            self.messagebar.collect("Video recording stopped.")

    def update_processor_params(self):
        """Sync GUI numeric parameters with computational engine."""
        try:
            v_thresh = float(self.params['velocityThreshold'].get_value())
            w_min = float(self.params['angularVelocityMin'].get_value())
            w_max = float(self.params['angularVelocityMax'].get_value())
            p_thresh = int(self.params['pointThreshold'].get_value())
            growth_rate = int(self.params['growthRate'].get_value())
            shrink_rate = int(self.params['shrinkRate'].get_value())
            smoothing_window = int(self.params['smoothingWindow'].get_value())
            
            self.processor.update_contingency_params(v_thresh, w_min, w_max, p_thresh, growth_rate, shrink_rate, smoothing_window)
            self.plot_widget.set_params(v_thresh, w_min, w_max, p_thresh)
        except (ValueError, TypeError):
            # Ignore temporary invalid parsing states while user is actively typing
            pass

    def prepare_sounds(self):
        """Re-generate waveforms matching adjustments."""
        duration = self.params['soundDuration'].get_value()
        amplitude = self.params['soundAmplitude'].get_value()
        
        # Static chime when reward zone becomes unlocked
        sound_beacon = soundmodule.Sound(duration=duration, srate=SAMPLING_RATE)
        sound_beacon.add_tone(600, amplitude, channel='all')
        sound_beacon.wave = soundmodule.apply_rise_fall(sound_beacon.wave, SAMPLING_RATE, 0.01, 0.01)
        self.sound_player.set_sound(SOUND_ID_BEACON, sound_beacon)
        
        # Water port reward click
        sound_reward = soundmodule.Sound(duration=0.5, srate=SAMPLING_RATE)
        sound_reward.add_tone(1200, amplitude, channel='all')
        sound_reward.wave = soundmodule.apply_rise_fall(sound_reward.wave, SAMPLING_RATE, 0.01, 0.01)
        self.sound_player.set_sound(SOUND_ID_REWARD, sound_reward)
        pass

    def on_point_scored(self, current_points):
        """Dynamically generate point-feedback beep."""
        if not self.session_running:
            return
            
        # Frequency scale based on points earned
        freq = 400 + 10 * current_points
        tick_sound = soundmodule.Sound(duration=0.06, srate=SAMPLING_RATE)
        tick_sound.add_tone(freq, amp=0.1)
        tick_sound.wave = soundmodule.apply_rise_fall(tick_sound.wave, SAMPLING_RATE, 0.003, 0.003)
        
        # Load and play on the fly
        self.sound_player.set_sound(SOUND_ID_TICK, tick_sound)
        self.sound_player.play(SOUND_ID_TICK)
        pass

    def on_goal_reached(self):
        """Locomotor contingency succeeded, trigger virtual event in state machine."""
        if not self.session_running:
            return
        self.messagebar.collect("Goal threshold reached! Water ports unlocked.")
        
        # Trigger 'Goalin' virtual input index (0)
        self.controller.state_machine.process_input(0)

    def save_to_file(self):
        """Export raw logs, FSM events, parameter values, and kinematics history to HDF5."""
        subject = self.session_info.get_value('subject')
        if self.controller.current_trial >= 0:
            # Ensure parameter history is not empty to avoid ValueError in Container.append_to_file
            for key in self.params._paramsToKeepHistory:
                if key not in self.params.history or not self.params.history[key]:
                    self.params.history[key] = [self.params[key].get_value()]

            containers = [
                self.params, self.controller, self.sm, 
                self.results, self.video_thread, self.processor
            ]
            self.savedata_widget.to_file(containers,
                                         subject=subject,
                                         paradigm=PARADIGM_NAME)
            self.messagebar.collect("Kinematics and tracking data saved successfully.")
        else:
            msg = 'No session has been run. Data saving skipped.'
            print(msg)
            self.messagebar.collect(msg)

    def prepare_next_trial(self, next_trial):
        """Compile state machine configurations for upcoming trial."""
        if next_trial > 0:
            self.params.update_history(next_trial - 1)
            self.process_results(next_trial - 1)
            print(self.controller.get_events_one_trial(next_trial - 1, use_names=True))

        # Clear buffers & flags
        self.processor.reset()
        self.worker.reset_goal()
        self.plot_widget.clear_data()
        self.update_processor_params()
        self.prepare_sounds()

        valve_duration = self.params['valveDuration'].get_value()

        # Build State FSM Matrix
        self.sm.reset_transitions()
        
        # Wait until kinematic goal is achieved
        self.sm.add_state(name='wait_for_goal', 
                          statetimer=np.inf,
                          transitions={'Goalin': 'reward_available'},
                          outputsOff=['ValveL', 'ValveR'])
                          
        # Goal hit: sound beacon turns on, waiting for poke on either port
        self.sm.add_state(name='reward_available',
                          statetimer=15.0,  # 15s window to collect water
                          transitions={'Lin': 'reward_left', 
                                       'Rin': 'reward_right',
                                       'Tup': 'reward_timeout'},
                          integerOut=SOUND_ID_BEACON)
                          
        # Open Left Valve
        self.sm.add_state(name='reward_left', 
                          statetimer=valve_duration,
                          transitions={'Tup': 'reward_off'},
                          outputsOn=['ValveL'],
                          integerOut=SOUND_ID_REWARD)
                          
        # Open Right Valve
        self.sm.add_state(name='reward_right', 
                          statetimer=valve_duration,
                          transitions={'Tup': 'reward_off'},
                          outputsOn=['ValveR'],
                          integerOut=SOUND_ID_REWARD)
                          
        # Clean up valves
        self.sm.add_state(name='reward_off', 
                          statetimer=0,
                          transitions={'Tup': 'END'},
                          outputsOff=['ValveL', 'ValveR'])
                          
        # Reached timeout, end trial
        self.sm.add_state(name='reward_timeout', 
                          statetimer=0,
                          transitions={'Tup': 'END'},
                          outputsOff=['ValveL', 'ValveR'])

        if next_trial == 0:
            print(self.sm)
            
        self.controller.set_state_matrix(self.sm)
        self.controller.ready_to_start_trial()

    def process_results(self, trial):
        """Analyze state transitions of finalized trial to categorize outcome."""
        events_df = self.controller.get_events_one_trial(trial)
        states = events_df.next_state.values
        
        if self.sm.states['reward_left'] in states:
            outcome = self.results.labels['reward']['left']
        elif self.sm.states['reward_right'] in states:
            outcome = self.results.labels['reward']['right']
        else:
            outcome = self.results.labels['reward']['none']
            
        self.results['reward'].append(outcome)

    def closeEvent(self, event):
        """Graceful thread cleanup on window closing."""
        self.worker.quit()
        self.worker.wait()
            
        self.interface.close()
        self.video_thread.stop()
        super().closeEvent(event)



if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Locomotor Action Space Paradigm")
    parser.add_argument("--video", type=str, default=None, help="Path to video file for playback testing")
    parser.add_argument("--fps-limit", type=float, default=None, help="FPS limit for video playback (0 or negative for benchmark mode)")
    parser.add_argument("--loop", action="store_true", help="Loop the video file playback")
    args, unknown = parser.parse_known_args()
    
    if args.video:
        config.VIDEO_PLAYBACK_PATH = args.video
    if args.fps_limit is not None:
        config.VIDEO_PLAYBACK_FPS = args.fps_limit
    if args.loop:
        config.VIDEO_PLAYBACK_LOOP = True

    (app, paradigm) = gui.create_app(Paradigm)

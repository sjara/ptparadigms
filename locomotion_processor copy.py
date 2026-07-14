"""
Real-time locomotion processor for locomotor action space paradigm.

This module is designed to be highly modular, thread-safe, and Cython-ready.
It does not import any GUI or PyQt modules, making it suitable for running in
a background worker thread or compiling to a C extension down the line.
"""

import numpy as np
from typing import Tuple, Dict, Any, Optional
import time
import threading

try:
    from phonotaxis.videoworkers import ProcessWorker
    from phonotaxis.sharedbuffer import SharedFrameBuffer, ResultBuffer
    from phonotaxis.resultbus import WorkerResult
except ImportError:
    # Fallback to base object if phonotaxis is not on the path
    ProcessWorker = object
    SharedFrameBuffer = object
    ResultBuffer = object
    WorkerResult = object


# Cython-compatible structure placeholder
class LocomotionState:
    """
    Lightweight, flat state container representing instantaneous kinematics.
    Uses primitive types for easy translation to C-structs/Cython definitions.
    """
    __slots__ = (
        'timestamp', 'x', 'y', 'velocity', 'heading', 
        'angular_velocity', 'contingency_met', 'points', 'orientation'
    )
    
    def __init__(self):
        self.timestamp: float = 0.0
        self.x: float = -1.0
        self.y: float = -1.0
        self.velocity: float = 0.0
        self.heading: float = 0.0
        self.angular_velocity: float = 0.0
        self.contingency_met: bool = False
        self.points: int = 0
        self.orientation: float = 0.0


    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary for convenient logging/Qt signals."""
        return {
            'timestamp': self.timestamp,
            'x': self.x,
            'y': self.y,
            'velocity': self.velocity,
            'heading': self.heading,
            'angular_velocity': self.angular_velocity,
            'contingency_met': self.contingency_met,
            'points': self.points,
            'orientation':self.orientation
        }


class LocomotionProcessor:
    """
    High-performance computational engine for real-time kinematics extraction.
    Uses pre-allocated NumPy ring buffers for memory alignment, suitable for
    GIL-free Cython memoryviews and multi-threaded calculations.
    """
    def __init__(self, buffer_size: int = 600, smoothing_window: int = 10):
        self.buffer_size = buffer_size
        self.smoothing_window = smoothing_window
        self.ptr = 0  # Write pointer
        self.count = 0  # Total processed frames
        
        # Pre-allocated circular buffers (Cython memoryview compatible)
        self.buf_timestamps = np.zeros(buffer_size, dtype=np.float64)
        self.buf_x = np.zeros(buffer_size, dtype=np.float64)
        self.buf_y = np.zeros(buffer_size, dtype=np.float64)
        self.buf_velocity = np.zeros(buffer_size, dtype=np.float64)
        self.buf_heading = np.zeros(buffer_size, dtype=np.float64)
        self.buf_angular_velocity = np.zeros(buffer_size, dtype=np.float64)
        self.buf_points = np.zeros(buffer_size, dtype=np.int64)
        self.buf_contingency_met = np.zeros(buffer_size, dtype=np.bool_)
        
        # Contingency thresholds (modifiable at runtime)
        self.velocity_threshold = 100.0  # px/s
        self.angular_velocity_min = 2.0  # rad/s
        self.angular_velocity_max = 10.0  # rad/s
        self.point_threshold = 50
        self.growth_rate = 300
        self.shrink_rate = 100
        
        # Current accumulated points
        self.current_points = 0
        
        # Keep track of previous state for delta calculations
        self.prev_time = 0.0
        self.prev_x = -1.0
        self.prev_y = -1.0
        self.prev_heading = 0.0
        self.prev_orientation = 0.0
        
        # History buffers for smoothing
        self.history_x = []
        self.history_y = []
        self.history_cos = []
        self.history_sin = []
        self.history_vel = []
        self.history_omega = []
        
    def reset(self):
        """Reset the processor state, points, and circular buffers."""
        self.ptr = 0
        self.count = 0
        self.current_points = 0
        self.prev_time = 0.0
        self.prev_x = -1.0
        self.prev_y = -1.0
        self.prev_heading = 0.0
        self.prev_orientation = 0.0
        
        self.buf_timestamps.fill(0)
        self.buf_x.fill(-1)
        self.buf_y.fill(-1)
        self.buf_velocity.fill(0)
        self.buf_heading.fill(0)
        self.buf_angular_velocity.fill(0)
        self.buf_points.fill(0)
        self.buf_contingency_met.fill(False)
        
        self.history_x.clear()
        self.history_y.clear()
        self.history_cos.clear()
        self.history_sin.clear()
        self.history_vel.clear()
        self.history_omega.clear()
        
    def update_contingency_params(self, 
                                  velocity_threshold: float,
                                  angular_velocity_min: float,
                                  angular_velocity_max: float,
                                  point_threshold: int,
                                  growth_rate: int = 300,
                                  shrink_rate: int = 100,
                                  smoothing_window: Optional[int] = None):
        """Update kinematic thresholds thread-safely."""
        self.velocity_threshold = velocity_threshold
        self.angular_velocity_min = angular_velocity_min
        self.angular_velocity_max = angular_velocity_max
        self.point_threshold = point_threshold
        self.growth_rate = growth_rate
        self.shrink_rate = shrink_rate
        if smoothing_window is not None:
            self.smoothing_window = smoothing_window

    def process_frame(self, timestamp: float, centroid: Tuple[int, int], orientation: float = 0.0) -> LocomotionState:
        """
        Process a single incoming video frame's coordinates.
        This function performs raw kinematics extraction, aligns temporal signals,
        checks if the animal meets target parameters, and updates running counts.
        
        Note: Designed to be fully compiled without Python runtime helpers in Cython.
        """
        state = LocomotionState()
        state.timestamp = timestamp
        state.x = float(centroid[0])
        state.y = float(centroid[1])
        state.orientation = orientation

        # Avoid division by zero and invalid tracking coordinates (-1, -1)
        if state.x >= 0 and state.y >= 0:
            if self.smoothing_window > 1:
                # 1. Update coordinate & orientation history
                self.history_x.append(state.x)
                self.history_y.append(state.y)
                self.history_cos.append(np.cos(2 * state.orientation))
                self.history_sin.append(np.sin(2 * state.orientation))
                
                if len(self.history_x) > self.smoothing_window:
                    self.history_x.pop(0)
                    self.history_y.pop(0)
                    self.history_cos.pop(0)
                    self.history_sin.pop(0)
                    
                # Compute smoothed coords & orientation
                smooth_x = np.mean(self.history_x)
                smooth_y = np.mean(self.history_y)
                smooth_cos = np.mean(self.history_cos)
                smooth_sin = np.mean(self.history_sin)
                smooth_orientation = np.arctan2(smooth_sin, smooth_cos) / 2.0
            else:
                smooth_x = state.x
                smooth_y = state.y
                smooth_orientation = state.orientation
            
            raw_vel = 0.0
            raw_omega = 0.0
            
            # If we have a previous smoothed position/orientation
            if self.prev_x >= 0 and self.prev_y >= 0:
                dt = timestamp - self.prev_time
                if dt < 0.1:
                    dt = 1/30
                if dt > 0.001:  # Prevent division by tiny time slices
                    # Compute velocity: pixel distance / dt using smoothed coordinates
                    dx = smooth_x - self.prev_x
                    dy = smooth_y - self.prev_y
                    distance = np.sqrt(dx * dx + dy * dy)
                    raw_vel = distance / dt
                    
                    # Compute heading (direction of movement velocity vector)
                    if distance > 0.1:  # Only compute heading if moving
                        state.heading = np.arctan2(dy, dx)
                        self.prev_heading = state.heading
                    else:
                        state.heading = self.prev_heading
                    
                    # Compute angular velocity: change in orientation / dt
                    d_orientation = smooth_orientation - self.prev_orientation
                    # Wrap difference to [-pi/2, pi/2] to handle ellipse orientation wrap-around
                    d_orientation = (d_orientation + np.pi/2) % np.pi - np.pi/2
                    raw_omega = abs(d_orientation) / dt
            else:
                state.heading = self.prev_heading
                dt = timestamp
            if self.smoothing_window > 1:
                # 2. Update velocity and omega history
                self.history_vel.append(raw_vel)
                self.history_omega.append(raw_omega)
                
                if len(self.history_vel) > self.smoothing_window:
                    self.history_vel.pop(0)
                    self.history_omega.pop(0)
                    
                # Compute smoothed velocity and omega
                state.velocity = np.mean(self.history_vel)
                state.angular_velocity = np.mean(self.history_omega)
            else:
                state.velocity = raw_vel
                state.angular_velocity = raw_omega
            
            # Update previous smoothed values
            self.prev_x = smooth_x
            self.prev_y = smooth_y
            self.prev_time = timestamp
            self.prev_orientation = smooth_orientation
        else:
            state.velocity = 0.0
            state.heading = self.prev_heading
            state.angular_velocity = 0.0
            dt = timestamp
            
        # Check contingencies
        v_ok = state.velocity >= self.velocity_threshold
        w_ok = self.angular_velocity_min <= state.angular_velocity <= self.angular_velocity_max
        state.contingency_met = v_ok and w_ok
        
        # Update point accumulation logic (e.g. 1 point for every frame contingency is met)
        if state.contingency_met:
            self.current_points += self.growth_rate*dt
        else:
            self.current_points = max(0,self.current_points - self.shrink_rate*dt)
            
        state.points = self.current_points
        
        # Write to circular buffers
        self.buf_timestamps[self.ptr] = state.timestamp
        self.buf_x[self.ptr] = state.x
        self.buf_y[self.ptr] = state.y
        self.buf_velocity[self.ptr] = state.velocity
        self.buf_heading[self.ptr] = state.heading
        self.buf_angular_velocity[self.ptr] = state.angular_velocity
        self.buf_points[self.ptr] = state.points
        self.buf_contingency_met[self.ptr] = state.contingency_met
        
        # Advance ring buffer write pointer
        self.ptr = (self.ptr + 1) % self.buffer_size
        self.count += 1
        
        return state

    def get_history(self, num_points: int = 100) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Retrieve aligned history slice in chronological order.
        Returns: (timestamps, velocities, angular_velocities, points)
        """
        n = min(num_points, self.count, self.buffer_size)
        if n == 0:
            empty = np.array([], dtype=np.float64)
            return empty, empty, empty, np.array([], dtype=np.int64)
            
        # Reconstruction slice indices
        indices = np.zeros(n, dtype=np.int32)
        start_idx = (self.ptr - n) % self.buffer_size
        for i in range(n):
            indices[i] = (start_idx + i) % self.buffer_size
            
        return (
            self.buf_timestamps[indices],
            self.buf_velocity[indices],
            self.buf_angular_velocity[indices],
            self.buf_points[indices]
        )

    def append_to_file(self, h5file):
        """Save history of locomotion data to HDF5."""
        if self.count == 0:
            return
        
        # Get all processed history
        n = min(self.count, self.buffer_size)
        indices = np.zeros(n, dtype=np.int32)
        start_idx = (self.ptr - n) % self.buffer_size
        for i in range(n):
            indices[i] = (start_idx + i) % self.buffer_size
            
        group = h5file.create_group('locomotion')
        group.create_dataset('timestamps', data=self.buf_timestamps[indices])
        group.create_dataset('x', data=self.buf_x[indices])
        group.create_dataset('y', data=self.buf_y[indices])
        group.create_dataset('velocity', data=self.buf_velocity[indices])
        group.create_dataset('heading', data=self.buf_heading[indices])
        group.create_dataset('angular_velocity', data=self.buf_angular_velocity[indices])
        group.create_dataset('points', data=self.buf_points[indices])
        group.create_dataset('contingency_met', data=self.buf_contingency_met[indices])


class LocomotionStrategy:
    """
    Strategy callable for kinematic processing via the generic
    ``ProcessWorker``.

    Subscribes to contour-tracker results via the ``ResultBus``
    (bus mode), eliminating the need for monkey-patching or direct
    internal buffer access.

    Call signature (bus mode): ``(WorkerResult) -> dict``
    """

    def __init__(self, processor: LocomotionProcessor):
        self.processor = processor
        self.state_lock = threading.Lock()
        self.latest_state: Optional[LocomotionState] = None

    def __call__(self, msg) -> dict:
        """
        Process a contour-tracker result message.

        Args:
            msg: ``WorkerResult`` from the contour-tracker worker.

        Returns:
            dict with the computed ``LocomotionState`` fields.
        """
        data = msg.data
        points = data.get('points', ())
        orientations = data.get('orientations', (0.0,))

        centroid = points[0] if points and len(points) > 0 else (-1, -1)
        orientation = orientations[0] if orientations else 0.0

        state = self.processor.process_frame(msg.timestamp, centroid, orientation)

        with self.state_lock:
            self.latest_state = state

        return state.to_dict()

    def get_latest_state(self) -> Optional[LocomotionState]:
        """Retrieve the last calculated locomotion state thread-safely."""
        with self.state_lock:
            return self.latest_state

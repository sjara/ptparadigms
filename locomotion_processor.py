"""
Real-time locomotion processor for locomotor action space paradigm.

This module is designed to be highly modular, thread-safe, and GIL-free.
It does not import any GUI or PyQt modules, making it suitable for running in
a background worker thread. The numeric core is JIT-compiled via Numba with
nogil=True so that ProcessWorker threads achieve true CPU parallelism.
"""

import numpy as np
from typing import Tuple, Dict, Any, Optional
import time
import threading

try:
    from numba import njit
    _NUMBA_AVAILABLE = True
except ImportError:
    _NUMBA_AVAILABLE = False
    def njit(*args, **kwargs):
        """No-op decorator fallback when Numba is not installed."""
        def decorator(func):
            return func
        if len(args) == 1 and callable(args[0]):
            return args[0]
        return decorator

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


# ---------------------------------------------------------------------------
# Numba JIT core — runs entirely without the GIL
# ---------------------------------------------------------------------------

@njit(nogil=True)
def _compute_kinematics_core(
    x, y, timestamp, orientation,
    prev_x, prev_y, prev_time, prev_heading, prev_orientation,
    hist_x, hist_y, hist_cos, hist_sin, hist_vel, hist_omega,
    hist_ptr, hist_count, smoothing_window,
    vel_thresh, omega_min, omega_max,
    current_points, growth_rate, shrink_rate,
):
    """
    Pure-numeric kinematics computation.

    All inputs are scalars or 1-D float64 arrays.  The function mutates
    the history arrays *in place* and returns updated scalar state as a
    flat tuple.

    Returns
    -------
    tuple of (velocity, heading, angular_velocity, contingency_met,
              current_points, new_prev_x, new_prev_y, new_prev_orientation,
              new_prev_heading, hist_ptr, hist_count)
    """
    velocity = 0.0
    heading = prev_heading
    angular_velocity = 0.0
    dt = timestamp  # fallback for first frame / invalid tracking

    if x >= 0.0 and y >= 0.0:
        # --- Smooth coordinates and orientation ---
        if smoothing_window > 1:
            idx = hist_ptr % smoothing_window
            hist_x[idx] = x
            hist_y[idx] = y
            hist_cos[idx] = np.cos(2.0 * orientation)
            hist_sin[idx] = np.sin(2.0 * orientation)
            hist_ptr += 1
            if hist_count < smoothing_window:
                hist_count += 1

            n = hist_count
            sx = 0.0
            sy = 0.0
            sc = 0.0
            ss = 0.0
            for i in range(n):
                sx += hist_x[i]
                sy += hist_y[i]
                sc += hist_cos[i]
                ss += hist_sin[i]
            smooth_x = sx / n
            smooth_y = sy / n
            smooth_orientation = np.arctan2(ss / n, sc / n) / 2.0
        else:
            smooth_x = x
            smooth_y = y
            smooth_orientation = orientation

        raw_vel = 0.0
        raw_omega = 0.0

        if prev_x >= 0.0 and prev_y >= 0.0:
            dt = timestamp - prev_time
            if dt < 0.1:
                dt = 1.0 / 30.0
            if dt > 0.001:
                dx = smooth_x - prev_x
                dy = smooth_y - prev_y
                distance = np.sqrt(dx * dx + dy * dy)
                raw_vel = distance / dt

                if distance > 0.1:
                    heading = np.arctan2(dy, dx)
                else:
                    heading = prev_heading

                d_orient = smooth_orientation - prev_orientation
                d_orient = (d_orient + np.pi / 2.0) % np.pi - np.pi / 2.0
                raw_omega = abs(d_orient) / dt
        else:
            heading = prev_heading
            dt = timestamp

        # --- Smooth velocity and angular velocity ---
        if smoothing_window > 1:
            vel_idx = (hist_ptr - 1) % smoothing_window
            hist_vel[vel_idx] = raw_vel
            hist_omega[vel_idx] = raw_omega

            n = hist_count
            sv = 0.0
            so = 0.0
            for i in range(n):
                sv += hist_vel[i]
                so += hist_omega[i]
            velocity = sv / n
            angular_velocity = so / n
        else:
            velocity = raw_vel
            angular_velocity = raw_omega

        new_prev_x = smooth_x
        new_prev_y = smooth_y
        new_prev_orientation = smooth_orientation
    else:
        # Invalid tracking coordinates
        velocity = 0.0
        angular_velocity = 0.0
        new_prev_x = prev_x
        new_prev_y = prev_y
        new_prev_orientation = prev_orientation
        dt = timestamp

    # --- Contingency check ---
    v_ok = velocity >= vel_thresh
    w_ok = (omega_min <= angular_velocity) and (angular_velocity <= omega_max)
    contingency_met = v_ok and w_ok

    # --- Point accumulation ---
    if contingency_met:
        current_points += growth_rate * dt
    else:
        current_points = max(0.0, current_points - shrink_rate * dt)

    return (
        velocity, heading, angular_velocity, contingency_met,
        current_points, new_prev_x, new_prev_y, new_prev_orientation,
        heading,  # new_prev_heading
        hist_ptr, hist_count,
    )


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
        self.current_points = 0.0
        
        # Keep track of previous state for delta calculations
        self.prev_time = 0.0
        self.prev_x = -1.0
        self.prev_y = -1.0
        self.prev_heading = 0.0
        self.prev_orientation = 0.0
        
        # Thread-safe latest-state cache for GUI polling
        self._state_lock = threading.Lock()
        self._latest_state: Optional[LocomotionState] = None
        
        # Pre-allocated smoothing history ring buffers (Numba-compatible)
        self._hist_x = np.zeros(smoothing_window, dtype=np.float64)
        self._hist_y = np.zeros(smoothing_window, dtype=np.float64)
        self._hist_cos = np.zeros(smoothing_window, dtype=np.float64)
        self._hist_sin = np.zeros(smoothing_window, dtype=np.float64)
        self._hist_vel = np.zeros(smoothing_window, dtype=np.float64)
        self._hist_omega = np.zeros(smoothing_window, dtype=np.float64)
        self._hist_ptr = 0
        self._hist_count = 0
        
        # Trigger JIT compilation before the session starts to avoid
        # warmup latency on the first real frame.
        if _NUMBA_AVAILABLE:
            _dummy = np.zeros(smoothing_window, dtype=np.float64)
            _compute_kinematics_core(
                0.0, 0.0, 0.0, 0.0,
                -1.0, -1.0, 0.0, 0.0, 0.0,
                _dummy.copy(), _dummy.copy(), _dummy.copy(), _dummy.copy(),
                _dummy.copy(), _dummy.copy(),
                0, 0, smoothing_window,
                100.0, 2.0, 10.0,
                0.0, 300.0, 100.0,
            )
        
    def reset(self):
        """Reset the processor state, points, and circular buffers."""
        self.ptr = 0
        self.count = 0
        self.current_points = 0.0
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
        
        self._hist_x.fill(0)
        self._hist_y.fill(0)
        self._hist_cos.fill(0)
        self._hist_sin.fill(0)
        self._hist_vel.fill(0)
        self._hist_omega.fill(0)
        self._hist_ptr = 0
        self._hist_count = 0
        
        with self._state_lock:
            self._latest_state = None
        
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
        if smoothing_window is not None and smoothing_window != self.smoothing_window:
            self.smoothing_window = smoothing_window
            # Re-allocate history buffers for the new window size
            self._hist_x = np.zeros(smoothing_window, dtype=np.float64)
            self._hist_y = np.zeros(smoothing_window, dtype=np.float64)
            self._hist_cos = np.zeros(smoothing_window, dtype=np.float64)
            self._hist_sin = np.zeros(smoothing_window, dtype=np.float64)
            self._hist_vel = np.zeros(smoothing_window, dtype=np.float64)
            self._hist_omega = np.zeros(smoothing_window, dtype=np.float64)
            self._hist_ptr = 0
            self._hist_count = 0

    def process_frame(self, timestamp: float, centroid: Tuple[int, int], orientation: float = 0.0) -> LocomotionState:
        """
        Process a single incoming video frame's coordinates.

        The heavy numeric work is delegated to ``_compute_kinematics_core``
        which is JIT-compiled by Numba with ``nogil=True``, allowing this
        worker thread to run in parallel with other ProcessWorker threads.
        """
        state = LocomotionState()
        state.timestamp = timestamp
        state.x = float(centroid[0])
        state.y = float(centroid[1])
        state.orientation = orientation

        # --- GIL-free numeric core ---
        result = _compute_kinematics_core(
            state.x, state.y, timestamp, orientation,
            self.prev_x, self.prev_y, self.prev_time,
            self.prev_heading, self.prev_orientation,
            self._hist_x, self._hist_y, self._hist_cos, self._hist_sin,
            self._hist_vel, self._hist_omega,
            self._hist_ptr, self._hist_count, self.smoothing_window,
            self.velocity_threshold, self.angular_velocity_min,
            self.angular_velocity_max,
            float(self.current_points), float(self.growth_rate),
            float(self.shrink_rate),
        )

        # Unpack JIT results into state and processor fields
        (state.velocity, state.heading, state.angular_velocity,
         contingency_met, self.current_points,
         self.prev_x, self.prev_y, self.prev_orientation,
         self.prev_heading,
         self._hist_ptr, self._hist_count) = result

        state.contingency_met = bool(contingency_met)
        state.points = self.current_points
        self.prev_time = timestamp
        
        # Write to circular buffers (NumPy indexing — also GIL-free)
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
    def __call__(self, msg) -> dict:
        """
        ProcessWorker strategy callable (bus mode).

        Unpacks a contour-tracker ``WorkerResult``, computes kinematics
        via the Numba-accelerated core, and returns a state dict.

        Call signature: ``(WorkerResult) -> dict``
        """
        data = msg.data
        points = data.get('points', ())
        orientations = data.get('orientations', (0.0,))

        centroid = points[0] if points and len(points) > 0 else (-1, -1)
        orientation = orientations[0] if orientations else 0.0

        state = self.process_frame(msg.timestamp, centroid, orientation)

        with self._state_lock:
            self._latest_state = state

        return state.to_dict()

    def get_latest_state(self) -> Optional[LocomotionState]:
        """Retrieve the last calculated locomotion state thread-safely."""
        with self._state_lock:
            return self._latest_state

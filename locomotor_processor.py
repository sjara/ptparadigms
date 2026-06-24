"""
Real-time locomotion processor for locomotor action space paradigm.

This module is designed to be highly modular, thread-safe, and Cython-ready.
It does not import any GUI or PyQt modules, making it suitable for running in
a background worker thread or compiling to a C extension down the line.
"""

import numpy as np
from typing import Tuple, Dict, Any, Optional

# Cython-compatible structure placeholder
class LocomotionState:
    """
    Lightweight, flat state container representing instantaneous kinematics.
    Uses primitive types for easy translation to C-structs/Cython definitions.
    """
    __slots__ = (
        'timestamp', 'x', 'y', 'velocity', 'heading', 
        'angular_velocity', 'contingency_met', 'points'
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
            'points': self.points
        }


class LocomotionProcessor:
    """
    High-performance computational engine for real-time kinematics extraction.
    Uses pre-allocated NumPy ring buffers for memory alignment, suitable for
    GIL-free Cython memoryviews and multi-threaded calculations.
    """
    def __init__(self, buffer_size: int = 600):
        self.buffer_size = buffer_size
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
        self.angular_velocity_max = 3.0  # rad/s
        self.point_threshold = 50
        
        # Current accumulated points
        self.current_points = 0
        
        # Keep track of previous state for delta calculations
        self.prev_time = 0.0
        self.prev_x = -1.0
        self.prev_y = -1.0
        self.prev_heading = 0.0
        
    def reset(self):
        """Reset the processor state, points, and circular buffers."""
        self.ptr = 0
        self.count = 0
        self.current_points = 0
        self.prev_time = 0.0
        self.prev_x = -1.0
        self.prev_y = -1.0
        self.prev_heading = 0.0
        
        self.buf_timestamps.fill(0)
        self.buf_x.fill(-1)
        self.buf_y.fill(-1)
        self.buf_velocity.fill(0)
        self.buf_heading.fill(0)
        self.buf_angular_velocity.fill(0)
        self.buf_points.fill(0)
        self.buf_contingency_met.fill(False)
        
    def update_contingency_params(self, 
                                  velocity_threshold: float,
                                  angular_velocity_min: float,
                                  angular_velocity_max: float,
                                  point_threshold: int):
        """Update kinematic thresholds thread-safely."""
        self.velocity_threshold = velocity_threshold
        self.angular_velocity_min = angular_velocity_min
        self.angular_velocity_max = angular_velocity_max
        self.point_threshold = point_threshold

    def process_frame(self, timestamp: float, centroid: Tuple[int, int]) -> LocomotionState:
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
        
        # Avoid division by zero and invalid tracking coordinates (-1, -1)
        if state.x >= 0 and state.y >= 0 and self.prev_x >= 0 and self.prev_y >= 0:
            dt = timestamp - self.prev_time
            if dt > 0.001:  # Prevent division by tiny time slices
                # Compute velocity: pixel distance / dt
                dx = state.x - self.prev_x
                dy = state.y - self.prev_y
                distance = np.sqrt(dx * dx + dy * dy)
                state.velocity = distance / dt
                
                # Compute heading (direction of movement velocity vector)
                if distance > 0.1:  # Only compute heading if moving
                    state.heading = np.arctan2(dy, dx)
                    
                    # Compute angular velocity: change in heading / dt
                    d_heading = state.heading - self.prev_heading
                    # Wrap difference to [-pi, pi] to handle wrap-around
                    d_heading = (d_heading + np.pi) % (2 * np.pi) - np.pi
                    state.angular_velocity = abs(d_heading) / dt
                    
                    # Update previous heading
                    self.prev_heading = state.heading
                else:
                    state.heading = self.prev_heading
                    state.angular_velocity = 0.0
        else:
            state.velocity = 0.0
            state.heading = self.prev_heading
            state.angular_velocity = 0.0
            
        # Check contingencies
        v_ok = state.velocity >= self.velocity_threshold
        w_ok = self.angular_velocity_min <= state.angular_velocity <= self.angular_velocity_max
        state.contingency_met = v_ok and w_ok
        
        # Update point accumulation logic (e.g. 1 point for every frame contingency is met)
        if state.contingency_met:
            self.current_points += 1
            
        state.points = self.current_points
        
        # Save previous frame tracking values
        if state.x >= 0 and state.y >= 0:
            self.prev_x = state.x
            self.prev_y = state.y
            self.prev_time = timestamp
            
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


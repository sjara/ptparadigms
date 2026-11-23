"""
6-Port Poke Training Paradigm
=============================

Earliest training stage for the 6-port arena: mice learn to drink from the
ports. Derived from ``click_only_6_port_shaping.py`` (rig, sound, valves,
video, journal and saving are unchanged); the trial logic is replaced:

- No initiation zone. The IZ is never armed (video and centroid tracking
  are still recorded).
- A poke at any ALLOWED port is rewarded immediately: that port's valve
  opens and the click train plays from that port's speaker for the
  "Reward sound duration" (default 1 s). Each reward is one trial, with
  the poked port as the trial's port (``port_triggered``) and outcome
  'correct'.
- Pokes while the sound plays (and during the optional ITI) are logged
  but ignored, so the next reward can only happen after the sound ends.
- After a reward, some ports are BLOCKED for the next trial, set by the
  "Blocked after reward" menu (locked at session start):
    'last_port'                : the last rewarded port
    'last_port_and_neighbors'  : the last rewarded port and its two
                                 neighbors (ports are labelled clockwise
                                 A-F, so the neighbors of A are F and B)
  All 6 ports are allowed for the first trial. Pokes at blocked ports are
  logged and counted, but do nothing.

Data (in addition to the inherited fields):
  task_params/blocked_ports_rule          'last_port' or
                                          'last_port_and_neighbors'
  task_params/task_type                   'poke_training'
  trials/n_blocked_pokes_before_reward    pokes at blocked ports between
                                          the previous trial's end and
                                          this reward
  trials/blocked_ports_mask               (n_trials x 6) int8, 1 if the
                                          port was blocked when this reward
                                          was earned (columns: attr
                                          'port_order')
  Inherited fields that do NOT apply here: IZ/dwell fields (dwell
  duration, mouse_in_iz_at_end, iz_* params), latency (always 0), the
  trial timeout and error-ITI settings, and incorrect_poke_ends_trial.
  The CSV summary goes to session_summary_log_poke_training.csv when the
  shared log's columns differ (see _append_csv_summary).

The rest of this docstring is inherited from the parent paradigms.

-------------------------------------------------------------------------

Self-initiated 6-port sound-localization task in a hexagonal arena, with
a BROADBAND CLICK TRAIN as the only target sound.

Adapted from ``6_port_localization.py``. Everything about the task —
rig, wiring, initiation-zone logic, trial structure, reward delivery,
video/journal machinery, dashboard, HDF5 group layout — is identical.
The ONLY difference is the stimulus:

    6_port_localization.py        FM (chord) warble, with an OPTIONAL
                                  broadband click train superimposed
    THIS FILE                     broadband click train ALONE; no FM
                                  warble is generated at all

This gives a stimulus whose localization cues are almost entirely
wideband-transient (ITD/ILD/HRTF-notch) rather than narrowband-tonal,
so performance here can be compared against the warble paradigm to ask
which cues the animal is actually using.

ARENA LAYOUT
------------
The hexagonal arena has 6 walls, each with an associated port and
speaker. Walls/ports/speakers are labelled clockwise A, B, C, D, E, F.

TASK DESCRIPTION
----------------
- ALL 6 speakers/ports are active in every session. There is no
  speaker-set choice to make and no inactive ports.
- A circular Initiation Zone is drawn at the center of the video view.
- When the mouse's tracked centroid remains inside the IZ for a set
  dwell time, a trial is initiated.
- The target port for each trial is drawn INDEPENDENTLY AND UNIFORMLY
  AT RANDOM from all 6 ports. There is no no-repeat rule: the previous
  trial's target port and the port the mouse last poked are BOTH
  eligible again, so an immediate repeat occurs with p = 1/6.
- The target port plays a broadband click train. A poke at the target
  port delivers water and stops (or extends) the sound. A poke at ANY
  of the other 5 ports ends the trial as incorrect: the sound stops
  immediately and no reward is delivered.
- If no poke occurs within the trial timeout, the sound stops and no
  reward is delivered.

THE STIMULUS
------------
A train of brief broadband (white-noise burst) clicks, played on the
target port's channel only. GUI-adjustable parameters:

    Click rate          default  20 Hz
    Click amplitude     default  0.180   (0-1 peak)
    Click duration      default  0.50 ms
    Pulsed segments     default  OFF     (continuous train)

The amplitude default (0.180) is much higher than the warble paradigm's
sound amplitude (0.03). That is expected: a 0.5 ms click at 20 Hz has a
duty cycle of ~1%, so its RMS/perceived level is far below its peak.
Do NOT assume the two paradigms are level-matched — verify with a
calibrated microphone before comparing performance across them.

When "pulse the train into segments" is enabled, the click train is
gated into on/off epochs (segment duration / gap duration, both
adjustable). This reproduces the on/off rhythm the warble paradigm had,
in case a gated envelope matters for the comparison. It is OFF by
default, giving a continuous train.

CHANGES FROM THE PARENT 6-PORT PARADIGM
---------------------------------------
1. No FM warble. The "FM Warble Parameters" group (min/max frequency,
   segment duration, gap, cycles per segment, start direction, chord
   options) is gone entirely, along with the chord-frequency helpers.
2. No click enable/disable toggle. In the parent paradigm the click
   train was an optional additive layer; here it is the whole stimulus,
   so a disable toggle would just produce silent trials.
3. The old master "Sound amplitude" spin (which set the warble level)
   is gone. "Click amplitude" is now the one level control.
4. Segment/gap durations for click gating are now their own controls
   inside the click group; they used to be borrowed from the warble's
   segment/gap spins.

SCHEMA NOTES (v6)
-----------------
The HDF5 group/dataset LAYOUT is unchanged from v5, so trial-level
readers keep working untouched. What differs is /task_params:

    ADDED
        sound_type                'broadband_click_train'
        fm_enabled                0
        click_segment_duration_sec
        click_gap_duration_sec
    CHANGED
        sound_amplitude           now mirrors click_amplitude (there is
                                  no separate warble level)
        click_train_enabled       always 1 (structurally — it is the
                                  only sound)
    REMOVED (not written at all)
        fm_freq_min_hz            fm_freq_max_hz
        fm_segment_duration_sec   fm_gap_duration_sec
        fm_cycles_per_segment     fm_start_direction
        fm_as_chord               fm_chord_ntones
        fm_chord_freqs_hz         fm_chord_freqs_source

IMPORTANT for downstream code: the fm_* attributes are ABSENT, not
zero-filled. This is deliberate — a NaN or 0 placeholder would silently
propagate into plots as if it were a real stimulus parameter, whereas an
absent key fails loudly. Any analyzer that reads
``tp.attrs['fm_freq_min_hz']`` directly will raise KeyError on these
files. Switch those reads to ``tp.attrs.get('fm_freq_min_hz')`` and
branch on ``sound_type`` (or ``fm_enabled``) to detect the click-only
mode. Detect the 6-port task family from ``n_active_ports`` (== 6) or
``active_set_name`` (== 'ABCDEF') as before.

The session summary CSV is written to a paradigm-specific filename
(``session_summary_log_poke_training.csv``), so its
changed column set will not corrupt the parent paradigm's log.

SPEAKER -> SOUND CHANNEL MAPPING
--------------------------------
The Xonar SE sound card exposes 6 output channels. Speakers are
wired so that (verified via sound_device_tester.py):
    Port A -> channel 1   (Xonar green/front jack)
    Port B -> channel 0   (Xonar green/front jack)
    Port C -> channel 2   (Xonar orange center/sub jack)
    Port D -> channel 3   (Xonar orange center/sub jack)
    Port E -> channel 5   (Xonar grey/side jack)
    Port F -> channel 4   (Xonar grey/side jack)
Every port drives its own distinct channel - there are no shared
speakers, so all 6 can be targeted independently. The pink input jack is
not used.

The canonical mapping lives in ``config.PORT_MAP`` so all tools
(paradigm, calibration GUI, analysis scripts) stay consistent.

USAGE
-----
1. Enter subject ID and trainer initials.
2. Set session duration, IZ radius, dwell time, trial timeout, and ITI.
3. Enter per-port valve calibration values for all 6 ports.
4. Check the click-train parameters (rate / amplitude / duration).
5. Click Start Session - trials are now fully automatic.
6. Session auto-saves when the session-duration timer expires.

Based on phonotaxis framework: https://github.com/sjara/phonotaxis
"""

import sys
import os
import csv
import json
import time
import subprocess
import h5py
import numpy as np
from datetime import datetime
from typing import Dict, Optional, List, Tuple
from bidict import bidict

try:
    import cv2
except ImportError:
    cv2 = None  # IZ overlay will be skipped if cv2 isn't importable here

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QGroupBox, QLabel, QPushButton, QDoubleSpinBox,
    QSpinBox, QCheckBox, QComboBox, QLineEdit, QFrame, QMessageBox,
    QScrollArea, QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit,
    QProgressBar, QDialog, QSizePolicy, QRadioButton, QButtonGroup,
    QFileDialog
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QBrush

from phonotaxis import gui
from phonotaxis import widgets
from phonotaxis import soundmodule
from phonotaxis import arduinomodule_6_port as arduinomodule
from phonotaxis import utils
from phonotaxis import savedata
from phonotaxis import config

# sounddevice is used directly for resilient sound playback (catching
# transient PortAudioError stream-start failures and force-stopping the
# device before a retry). soundmodule imports it too; importing it here
# as well is harmless and keeps the retry logic self-contained.
import sounddevice as sd

# Crash-safe session journal (lives in the phonotaxis package alongside
# videomodule_spinnaker, soundmodule, etc.).
from phonotaxis.session_journal import SessionJournal, make_journal_path

# Camera backend: import Spinnaker module if configured, else fall back to webcam
if getattr(config, 'CAMERA_TYPE', 'webcam') == 'spinnaker':
    from phonotaxis import videomodule_spinnaker as videomodule
    print("[Paradigm] Using Spinnaker (FLIR Blackfly S) camera backend")
else:
    from phonotaxis import videomodule
    print("[Paradigm] Using webcam (OpenCV) camera backend")


# ============================================================================
# CONSTANTS
# ============================================================================

PARADIGM_NAME = 'poke_training'
PARADIGM_VERSION = '1'
SCHEMA_VERSION = 6                   # h5 file-schema version; bumped from v5 because
                                     # the stimulus changed: broadband click train
                                     # only, no FM warble. The fm_* task_params
                                     # attrs are ABSENT in these files (not zeroed)
                                     # and sound_type/fm_enabled are new.
                                     # Group/dataset LAYOUT is unchanged from v5 -
                                     # see SCHEMA NOTES in the module docstring.
SAMPLING_RATE = 44100
N_AUDIO_CHANNELS = 6                 # Xonar SE — all 6 channels (0-5) used, one per port
STOP_ALL_SOUNDS = -1
MAX_TRIALS = 2000

# Sound-playback resilience. On Windows, PortAudio (esp. via the WDM-KS
# host API) intermittently fails to start an output stream with
# "Unanticipated host error [-9999]" / ERROR_BUSY when a new stream is
# started before the OS has fully released the previous one. Rather
# than letting that crash a session mid-run, _play_sound retries the
# stream start a few times, force-stopping the device between attempts.
SOUND_PLAY_MAX_ATTEMPTS = 4          # total tries before giving up
SOUND_PLAY_RETRY_DELAY_S = 0.06      # pause between attempts (lets the
                                     # audio device finish releasing)

# ----------------------------------------------------------------------------
# Port identifiers, active speaker sets, and physical wiring map.
#
# These are the canonical hardware-mapping constants. They live in
# config.py so that other tools (calibration GUI, volume tester,
# analysis scripts) see the same wiring. The paradigm imports them from
# config; the fallbacks below match the most recent verified mapping
# from sound_device_tester.py and are used only if config.py doesn't
# define them (e.g. an older config file).
# ----------------------------------------------------------------------------
_FALLBACK_PORT_MAP: Dict[str, dict] = {
    'A': {'valve': 'ValveA', 'input': 'A', 'channel': 1,
          'jack': 'green/front',
          'label': 'Port A (ch 1, green/front)'},
    'B': {'valve': 'ValveB', 'input': 'B', 'channel': 0,
          'jack': 'green/front',
          'label': 'Port B (ch 0, green/front)'},
    'C': {'valve': 'ValveC', 'input': 'C', 'channel': 2,
          'jack': 'orange/center-sub',
          'label': 'Port C (ch 2, orange/center-sub)'},
    'D': {'valve': 'ValveD', 'input': 'D', 'channel': 3,
          'jack': 'orange/center-sub',
          'label': 'Port D (ch 3, orange/center-sub)'},
    'E': {'valve': 'ValveE', 'input': 'E', 'channel': 5,
          'jack': 'grey/side',
          'label': 'Port E (ch 5, grey/side)'},
    'F': {'valve': 'ValveF', 'input': 'F', 'channel': 4,
          'jack': 'grey/side',
          'label': 'Port F (ch 4, grey/side)'},
}

ALL_PORTS: Tuple[str, ...] = tuple(
    getattr(config, 'ALL_PORTS', ('A', 'B', 'C', 'D', 'E', 'F'))
)

# ----------------------------------------------------------------------------
# ACTIVE SET.
#
# The 3-port paradigm chose one of two alternating-wall triplets each
# session (ACE or BDF) via a radio-button widget. The 6-port paradigm has
# no such choice: every port is active in every session. These constants
# replace SPEAKER_SET_OPTION_1 / SPEAKER_SET_OPTION_2 / SPEAKER_SETS.
# ----------------------------------------------------------------------------
ACTIVE_PORTS: Tuple[str, ...] = ALL_PORTS
ACTIVE_SET_NAME: str = ''.join(ALL_PORTS)      # 'ABCDEF'
N_ACTIVE_PORTS: int = len(ACTIVE_PORTS)
# Probability of a correct poke by chance, as a percentage. Used to
# annotate the dashboard and to scale its performance colour thresholds.
# 6-port: 100/6 = 16.7%  (the 3-port task's chance level was 33.3%)
CHANCE_LEVEL_PCT: float = 100.0 / N_ACTIVE_PORTS

if N_ACTIVE_PORTS != 6:
    print(f"[Paradigm] WARNING: expected 6 ports, config.ALL_PORTS gives "
          f"{N_ACTIVE_PORTS} ({ALL_PORTS}). The task will still run with "
          f"whatever ports are defined, but chance level is now "
          f"{CHANCE_LEVEL_PCT:.1f}%.")

PORT_MAP: Dict[str, dict] = getattr(config, 'PORT_MAP', _FALLBACK_PORT_MAP)

# Log which source was used (helps debug mismatched config files)
if hasattr(config, 'PORT_MAP'):
    print(f"[Paradigm] PORT_MAP loaded from config (SOUND_DEVICE="
          f"{getattr(config, 'SOUND_DEVICE', '?')})")
else:
    print("[Paradigm] WARNING: config.PORT_MAP not defined — using "
          "built-in fallback. Update config.py for consistency with "
          "other tools.")
for _p in ALL_PORTS:
    _ch = PORT_MAP[_p]['channel']
    print(f"  Port {_p} → audio channel {_ch}  "
          f"(valve {PORT_MAP[_p]['valve']}, input {PORT_MAP[_p]['input']})")

# Stable sound IDs (one per port) — used to route prebuilt waveforms
# through SoundPlayer.set_sound() / play().
PORT_TO_SOUND_ID = {p: (i + 1) for i, p in enumerate(ALL_PORTS)}

# Video tracking defaults
BLACK_THRESHOLD = 70
MIN_AREA = 247
# Mask coords are in display-frame space (~640x480 for both webcam and
# Spinnaker downsampled display). Adjust if SPINNAKER_DISPLAY_WIDTH changes.
DEFAULT_MASK = [320, 240, 250]           # [cx, cy, radius] in pixels
DEFAULT_IZ_RADIUS_PX = 150               # IZ radius in display-frame pixels
DEFAULT_DWELL_SEC = 0.20                  # Time centroid must be in IZ to trigger
DEFAULT_INCORRECT_POKE_ENDS_TRIAL = False  # Shaping: wrong pokes are ignored

# Poke training: which ports are blocked for the trial after a reward.
# Ports are physically labelled clockwise A-F around the hexagonal arena;
# neighbors are taken from this fixed order (wrapping around).
PORTS_CLOCKWISE: Tuple[str, ...] = ('A', 'B', 'C', 'D', 'E', 'F')
BLOCKED_PORTS_RULES: Dict[str, str] = {
    'last_port': 'Last rewarded port',
    'last_port_and_neighbors': 'Last rewarded port + its 2 neighbors',
}
DEFAULT_BLOCKED_PORTS_RULE = 'last_port'
DEFAULT_REWARD_SOUND_SEC = 1.0


def blocked_ports_after_reward(rewarded_port: str, rule: str) -> Tuple[str, ...]:
    """Ports that cannot be rewarded on the trial after ``rewarded_port``."""
    if rule == 'last_port':
        return (rewarded_port,)
    if rule == 'last_port_and_neighbors':
        port_index = PORTS_CLOCKWISE.index(rewarded_port)
        n_ports = len(PORTS_CLOCKWISE)
        return (PORTS_CLOCKWISE[(port_index - 1) % n_ports],
                rewarded_port,
                PORTS_CLOCKWISE[(port_index + 1) % n_ports])
    raise ValueError(f'Unknown blocked-ports rule: {rule}')

# Arduino inputs/outputs from config
ARDUINO_INPUTS = list(config.INPUT_PINS.keys())
OUTPUTS = list(config.OUTPUT_PINS.keys())

# Per-port colors. Dark variants used for status indicator + active poke
# styles; light variants used for trial-log row backgrounds.
#
# This palette is kept deliberately in sync with the session analyzer
# (session_analyzer.py PORT_COLORS_RGB) so a port reads as the same
# color everywhere — paradigm GUI, trajectory plots, cross-session
# plots, etc. Canonical mapping:
#     A red · B orange · C yellow · D green · E blue · F purple
PORT_COLORS_DARK: Dict[str, str] = {
    'A': '#DC2626',   # Red
    'B': '#EA7C14',   # Orange
    'C': '#EAC823',   # Yellow
    'D': '#22A03C',   # Green
    'E': '#1E64DC',   # Blue
    'F': '#8232BE',   # Purple
}
PORT_COLORS_DARK_BORDER: Dict[str, str] = {
    'A': '#991B1B',   # Darker red
    'B': '#B45309',   # Darker orange
    'C': '#A98A00',   # Darker yellow/amber
    'D': '#15602A',   # Darker green
    'E': '#13418F',   # Darker blue
    'F': '#5A1F86',   # Darker purple
}
PORT_COLORS_LIGHT: Dict[str, QColor] = {
    'A': QColor(248, 200, 200),   # Light red
    'B': QColor(250, 224, 190),   # Light orange
    'C': QColor(250, 240, 190),   # Light yellow
    'D': QColor(200, 235, 207),   # Light green
    'E': QColor(200, 218, 248),   # Light blue
    'F': QColor(224, 200, 240),   # Light purple
}
COLOR_POKE_YES = QColor(200, 230, 201)  # Light green (legacy; kept for reference)
COLOR_TRIAL_CORRECT = QColor(255, 255, 255)   # White background for correct rows
COLOR_TRIAL_INCORRECT = QColor(80, 80, 80)    # Dark grey background for incorrect rows

# CSV summary file
CSV_SUMMARY_FILENAME = 'session_summary_log.csv'


# ============================================================================
# STYLE CONSTANTS
# ============================================================================

STYLE_BTN_START = """
    QPushButton {
        background-color: #4CAF50; border: 2px solid #2E7D32;
        border-radius: 8px; padding: 10px 16px;
        font-size: 13px; font-weight: bold; color: white;
    }
    QPushButton:hover { background-color: #66BB6A; }
    QPushButton:disabled { background-color: #808080; border-color: #606060; }
"""

STYLE_BTN_STOP = """
    QPushButton {
        background-color: #f44336; border: 2px solid #c62828;
        border-radius: 8px; padding: 10px 16px;
        font-size: 13px; font-weight: bold; color: white;
    }
    QPushButton:hover { background-color: #ef5350; }
"""

# Highlight for the "Set every session" sub-box (Subject / Trainer /
# Speaker set). A warm amber border + faint tint draws the eye to the
# only three entries that must be changed before every session.
STYLE_PER_SESSION_BOX = """
    QGroupBox {
        border: 2px solid #F9A825;
        border-radius: 6px;
        margin-top: 10px;
        background-color: #FFFDF5;
        font-weight: bold;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 8px; padding: 0 4px;
        color: #E65100;
    }
"""

# Subtle styling for the fixed/rarely-changed session parameters box so
# it visually recedes relative to the highlighted per-session box.
STYLE_FIXED_BOX = """
    QGroupBox {
        border: 1px solid #cccccc;
        border-radius: 6px;
        margin-top: 10px;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 8px; padding: 0 4px;
        color: #777777;
    }
"""

def _text_on(hex_color: str) -> str:
    """Pick black or white text for legibility on a given background.

    Needed because the port palette now spans both dark colors (red,
    blue, purple — want white text) and light ones (yellow, orange —
    want black text). Uses the standard perceived-luminance threshold.
    """
    h = hex_color.lstrip('#')
    try:
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    except (ValueError, IndexError):
        return 'white'
    # Rec. 601 luma; > 150 is "light enough" to need dark text.
    luma = 0.299 * r + 0.587 * g + 0.114 * b
    return 'black' if luma > 150 else 'white'


# Idle and active styles for a poke indicator, parameterised by port colors.
# Returns a (idle, active) stylesheet pair.
def _poke_indicator_styles(port_key: str) -> Tuple[str, str]:
    fill = PORT_COLORS_DARK[port_key]
    border = PORT_COLORS_DARK_BORDER[port_key]
    idle = (
        "background-color: #37474F; color: #90A4AE; "
        "border: 2px solid #546E7A; "
        "border-radius: 8px; padding: 8px; "
        "font-weight: bold; font-size: 11px;"
    )
    # A lighter, washed-out version of the dark color works well for the
    # "active" flash. We just use the dark color directly — it stays visible
    # against the dark idle background and unmistakably identifies the port.
    # Text color flips to black on light fills (e.g. yellow port C) so the
    # label stays readable.
    active = (
        f"background-color: {fill}; color: {_text_on(fill)}; "
        f"border: 2px solid {border}; "
        "border-radius: 8px; padding: 8px; "
        "font-weight: bold; font-size: 11px;"
    )
    return idle, active


def _reward_btn_style(port_key: str) -> str:
    """Stylesheet for a manual-reward button for a given port."""
    fill = PORT_COLORS_DARK_BORDER[port_key]
    hover = PORT_COLORS_DARK[port_key]
    return (
        "QPushButton {"
        f" background-color: {fill}; border: 2px solid {fill};"
        " border-radius: 6px; padding: 6px 12px;"
        f" font-size: 11px; font-weight: bold; color: {_text_on(fill)};"
        "}"
        f"QPushButton:hover {{ background-color: {hover};"
        f" color: {_text_on(hover)}; }}"
        f"QPushButton:pressed {{ background-color: {fill}; }}"
    )


# ============================================================================
# INITIATION ZONE TRACKER
# ============================================================================

class InitiationZoneTracker:
    """
    Tracks how long the mouse's centroid has been continuously inside
    a circular initiation zone, with a short dropout grace period so
    brief tracking lapses don't reset the dwell clock.

    A trial is "triggered" the first frame the accumulated dwell time
    crosses ``required_sec`` (while the tracker is enabled). After a
    trigger, the tracker disables itself; the paradigm must call
    ``enable()`` again to look for the next trial.
    """

    def __init__(self, dropout_grace_sec=0.12):
        self.cx = 0.0
        self.cy = 0.0
        self.radius = 0.0
        self.required_sec = 1.0
        self.dropout_grace_sec = float(dropout_grace_sec)
        self.enabled = False
        self.in_zone = False
        self.dwell_start_time = None
        self.last_in_zone_time = None
        self.last_transition = None  # 'enter' | 'exit' | None on each update

    def set_zone(self, cx, cy, radius):
        self.cx = float(cx)
        self.cy = float(cy)
        self.radius = float(radius)

    def set_required_sec(self, required_sec):
        self.required_sec = float(required_sec)

    def set_dropout_grace_sec(self, sec):
        self.dropout_grace_sec = float(sec)

    def reset(self):
        self.in_zone = False
        self.dwell_start_time = None
        self.last_in_zone_time = None
        self.last_transition = None

    def enable(self):
        self.reset()
        self.enabled = True

    def disable(self):
        self.enabled = False
        self.reset()

    def point_in_zone(self, point):
        if point is None:
            return False
        dx = point[0] - self.cx
        dy = point[1] - self.cy
        return (dx * dx + dy * dy) <= (self.radius * self.radius)

    def update(self, centroid, now=None):
        """Update tracker with the current centroid.

        Returns a dict with:
            in_zone:    bool — is the centroid currently inside the zone?
            dwell_sec:  float — continuous time accumulated in zone
            trigger:    bool — True on the single frame dwell crosses
                        ``required_sec`` (tracker then disables itself)
        """
        if now is None:
            now = time.time()
        result = {'in_zone': False, 'dwell_sec': 0.0, 'trigger': False}
        self.last_transition = None

        if not self.enabled:
            return result

        in_zone_now = self.point_in_zone(centroid)

        if in_zone_now:
            if not self.in_zone:
                # Entering the zone (either fresh or recovering from a
                # brief dropout). If the dropout was within grace, keep
                # the accumulated dwell.
                if (self.dwell_start_time is not None
                        and self.last_in_zone_time is not None
                        and (now - self.last_in_zone_time)
                            <= self.dropout_grace_sec):
                    # Within grace — keep the existing clock running.
                    self.in_zone = True
                else:
                    # Fresh entry
                    self.in_zone = True
                    self.dwell_start_time = now
                    self.last_transition = 'enter'
            self.last_in_zone_time = now
        else:
            if self.in_zone:
                # Just left the zone; allow a brief grace before
                # resetting the clock.
                if self.last_in_zone_time is not None and (
                        (now - self.last_in_zone_time)
                        <= self.dropout_grace_sec):
                    # Still within grace — pretend we're still in the
                    # zone for dwell-clock purposes. We just don't
                    # advance dwell during the dropout window.
                    pass
                else:
                    self.in_zone = False
                    self.dwell_start_time = None
                    self.last_in_zone_time = None
                    self.last_transition = 'exit'

        if self.in_zone and self.dwell_start_time is not None:
            dwell = now - self.dwell_start_time
            result['in_zone'] = True
            result['dwell_sec'] = dwell
            if dwell >= self.required_sec:
                # Trigger! Disable so the paradigm can take over.
                result['trigger'] = True
                self.disable()
        else:
            result['in_zone'] = False
            result['dwell_sec'] = 0.0

        return result


# ============================================================================
# PERFORMANCE DASHBOARD (all 6 ports)
# ============================================================================

class PerformanceDashboard(QGroupBox):
    """
    Live session statistics: trial counts, correct-poke rate, water delivered,
    and session timer with countdown.

    All 6 ports are active in this paradigm, so all 6 are always displayed.
    The four separate per-port label rows used by the 3-port paradigm
    (trials / correct% / incorrect / timeouts, each a run-on string) become
    illegible with six entries, so they are replaced here by a single compact
    monospace breakdown table with one row per port.

    Performance colour thresholds are scaled to the 6-port chance level
    (16.7%), not the 3-port one (33.3%).
    """

    # Correct-rate colour thresholds, as multiples of chance (16.7%):
    #   >= 3.5x chance (~58%) -> green
    #   >= 2.0x chance (~33%) -> orange
    #   otherwise             -> red
    RATE_GOOD_PCT = 3.5 * CHANCE_LEVEL_PCT
    RATE_OK_PCT = 2.0 * CHANCE_LEVEL_PCT

    # Trial-balance thresholds. With 6 ports the ideal share per port is
    # only 16.7%, so the 3-port paradigm's ABSOLUTE percentage-point
    # thresholds (>10 pts orange, >20 pts red) would essentially never
    # fire. Judge the worst per-port deviation RELATIVE to the ideal
    # share instead, and don't colour it at all until enough trials have
    # accumulated for the estimate to mean anything.
    BALANCE_MIN_TRIALS = 24
    BALANCE_WARN_REL = 0.40      # worst port off by >40% of its ideal share
    BALANCE_BAD_REL = 0.75       # ... by >75%

    def __init__(self, parent=None):
        super().__init__("Session Performance", parent)
        self.setMinimumWidth(300)
        self._active_ports: List[str] = list(ACTIVE_PORTS)
        self._reset()
        self._setup_ui()
        self._update_display()

    def _reset(self):
        self.n_trials = {p: 0 for p in ALL_PORTS}
        self.n_correct = {p: 0 for p in ALL_PORTS}
        self.n_incorrect = {p: 0 for p in ALL_PORTS}
        self.n_timeouts = {p: 0 for p in ALL_PORTS}
        self.n_rewards = {p: 0 for p in ALL_PORTS}
        self.elapsed_sec = 0.0
        self.session_duration = 1800
        # Per-port valve calibration volume (µL per open)
        self.vol_per = {p: 0.0 for p in ALL_PORTS}

    def _setup_ui(self):
        layout = QGridLayout()
        layout.setSpacing(6)

        # Paradigm label
        lbl = QLabel("6-Port Poke Training")
        lbl.setStyleSheet(
            "font-weight: bold; font-size: 12pt; color: #FF9800;"
        )
        layout.addWidget(lbl, 0, 0, 1, 2)

        # Active set indicator (fixed — all 6 ports, every session)
        layout.addWidget(QLabel("Active ports:"), 1, 0)
        self.active_set_display = QLabel(" / ".join(ACTIVE_PORTS))
        self.active_set_display.setStyleSheet(
            "font-weight: bold; color: #555;"
        )
        layout.addWidget(self.active_set_display, 1, 1)

        # Session timer
        layout.addWidget(QLabel("Session Time:"), 2, 0)
        self.timer_display = QLabel("00:00 / 30:00")
        self.timer_display.setStyleSheet(
            "font-weight: bold; font-size: 11pt;"
        )
        layout.addWidget(self.timer_display, 2, 1)

        self.time_progress = QProgressBar()
        self.time_progress.setRange(0, 100)
        self.time_progress.setValue(0)
        self.time_progress.setTextVisible(False)
        self.time_progress.setMaximumHeight(10)
        layout.addWidget(self.time_progress, 3, 0, 1, 2)

        layout.addWidget(self._sep(), 4, 0, 1, 2)

        # Trial counts
        layout.addWidget(QLabel("Total Trials:"), 5, 0)
        self.total_display = QLabel("0")
        self.total_display.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.total_display, 5, 1)

        layout.addWidget(self._sep(), 6, 0, 1, 2)

        # Poke training: every trial is rewarded, so show the reward rate
        # (rewards so far / elapsed session minutes) instead of a correct
        # rate. The widget keeps its inherited name.
        layout.addWidget(QLabel("Rewards per minute:"), 7, 0)
        self.correct_rate_display = QLabel("--")
        self.correct_rate_display.setStyleSheet(
            "font-size: 14pt; font-weight: bold;"
        )
        layout.addWidget(self.correct_rate_display, 7, 1)

        rate_note_lbl = QLabel("  (rewards so far / elapsed minutes)")
        rate_note_lbl.setStyleSheet("color: #888; font-size: 9pt;")
        layout.addWidget(rate_note_lbl, 8, 0, 1, 2)

        layout.addWidget(self._sep(), 9, 0, 1, 2)

        # Per-port breakdown — one monospace table instead of four
        # run-on label rows (see class docstring).
        breakdown_lbl = QLabel("Per-port breakdown:")
        breakdown_lbl.setStyleSheet("font-weight: bold;")
        layout.addWidget(breakdown_lbl, 10, 0, 1, 2)

        self.per_port_display = QLabel("--")
        mono = QFont("Consolas")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        mono.setPointSize(9)
        self.per_port_display.setFont(mono)
        self.per_port_display.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.per_port_display, 11, 0, 1, 2)

        layout.addWidget(self._sep(), 12, 0, 1, 2)

        # Trial balance
        layout.addWidget(QLabel("Trial Balance:"), 13, 0)
        self.balance_display = QLabel("--")
        self.balance_display.setWordWrap(True)
        layout.addWidget(self.balance_display, 13, 1)

        layout.addWidget(self._sep(), 14, 0, 1, 2)

        # Water delivered
        layout.addWidget(QLabel("Water Delivered:"), 15, 0)
        self.water_display = QLabel("-- µL")
        self.water_display.setStyleSheet(
            "font-weight: bold; color: #2196F3;"
        )
        layout.addWidget(self.water_display, 15, 1)

        self.setLayout(layout)

    def _sep(self):
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        return line

    def set_active_ports(self, ports):
        """Configure which ports the dashboard displays.

        In the 6-port paradigm this is always all 6 and is called once at
        startup; the setter is retained so the widget stays reusable (and
        so the call sites inherited from the 3-port paradigm keep working).
        """
        self._active_ports = list(ports)
        self.active_set_display.setText(" / ".join(self._active_ports))
        self._update_display()

    def set_session_duration(self, seconds):
        self.session_duration = seconds

    def set_volume_calibration(self, vols: dict):
        """Update per-port calibration volumes (µL per open).

        ``vols`` is a dict like {'A': 9.06, 'C': 9.18, 'E': 8.95}; ports
        not in the dict keep their previous value.
        """
        for k, v in vols.items():
            if k in self.vol_per:
                self.vol_per[k] = float(v)
        self._update_water()

    def record_trial(self, port_key, outcome, reward_delivered=False):
        """outcome: 'correct', 'incorrect', or 'timeout'."""
        if port_key not in self.n_trials:
            return
        self.n_trials[port_key] += 1
        if outcome == 'correct':
            self.n_correct[port_key] += 1
        elif outcome == 'incorrect':
            self.n_incorrect[port_key] += 1
        elif outcome == 'timeout':
            self.n_timeouts[port_key] += 1
        if reward_delivered:
            self.n_rewards[port_key] += 1
        self._update_display()

    def update_timer(self, elapsed):
        self.elapsed_sec = elapsed
        self._update_reward_rate()
        remaining = max(0, self.session_duration - elapsed)
        e_m, e_s = int(elapsed // 60), int(elapsed % 60)
        t_m, t_s = (int(self.session_duration // 60),
                    int(self.session_duration % 60))
        r_m, r_s = int(remaining // 60), int(remaining % 60)
        self.timer_display.setText(
            f"{e_m:02d}:{e_s:02d} / {t_m:02d}:{t_s:02d}  "
            f"({r_m:02d}:{r_s:02d} left)"
        )
        if self.session_duration > 0:
            pct = int((elapsed / self.session_duration) * 100)
            self.time_progress.setValue(min(100, pct))
            color = ("#4CAF50" if pct < 50 else
                     "#FF9800" if pct < 80 else "#F44336")
            self.time_progress.setStyleSheet(
                f"QProgressBar::chunk {{ background-color: {color}; }}"
            )

    def _update_reward_rate(self):
        """Show rewards per minute of elapsed session time."""
        total_rewards = sum(self.n_rewards[port] for port in ALL_PORTS)
        if self.elapsed_sec > 0:
            rewards_per_min = total_rewards / (self.elapsed_sec / 60.0)
            self.correct_rate_display.setText(f"{rewards_per_min:.1f}")
        else:
            self.correct_rate_display.setText("--")

    def _format_per_port_table(self, active) -> str:
        """Compact monospace per-port breakdown, one row per port.

            Port    n   corr   inc   t/o
            A      12    83%     2     0
            ...
        """
        header = f"{'Port':<5}{'n':>4}{'corr':>7}{'inc':>6}{'t/o':>6}"
        lines = [header]
        for p in active:
            n = self.n_trials[p]
            if n > 0:
                pct_s = f"{(self.n_correct[p] / n) * 100:.0f}%"
            else:
                pct_s = "--"
            lines.append(
                f"{p:<5}{n:>4}{pct_s:>7}"
                f"{self.n_incorrect[p]:>6}{self.n_timeouts[p]:>6}"
            )
        return "\n".join(lines)

    def _update_display(self):
        active = self._active_ports if self._active_ports else list(ALL_PORTS)
        total = sum(self.n_trials[p] for p in active)
        total_correct = sum(self.n_correct[p] for p in active)

        self.total_display.setText(str(total))

        self._update_reward_rate()

        # Per-port breakdown table (trials / correct% / incorrect / timeouts)
        self.per_port_display.setText(self._format_per_port_table(active))

        # Trial balance — how evenly the uniform-random draw has actually
        # distributed targets so far. With i.i.d. sampling this WILL be
        # lumpy early in a session; the deviation is judged relative to the
        # ideal share and left uncoloured until BALANCE_MIN_TRIALS trials.
        if total > 0 and len(active) > 0:
            pcts = [(self.n_trials[p] / total * 100) for p in active]
            ideal = 100.0 / len(active)
            max_rel_dev = max(abs(pct - ideal) for pct in pcts) / ideal
            self.balance_display.setText(
                "  ".join(f"{p}:{pct:.0f}%"
                          for p, pct in zip(active, pcts))
            )
            if total < self.BALANCE_MIN_TRIALS:
                self.balance_display.setStyleSheet("color: #888;")
            elif max_rel_dev > self.BALANCE_BAD_REL:
                self.balance_display.setStyleSheet(
                    "color: #F44336; font-weight: bold;"
                )
            elif max_rel_dev > self.BALANCE_WARN_REL:
                self.balance_display.setStyleSheet(
                    "color: #FF9800; font-weight: bold;"
                )
            else:
                self.balance_display.setStyleSheet(
                    "color: #4CAF50; font-weight: bold;"
                )
        else:
            self.balance_display.setText("--")
            self.balance_display.setStyleSheet("")

        self._update_water()

    def _update_water(self):
        active = self._active_ports if self._active_ports else list(ALL_PORTS)
        vol = sum(self.n_rewards[p] * self.vol_per[p] for p in active)
        any_cal = any(self.vol_per[p] > 0 for p in active)
        if any_cal:
            self.water_display.setText(
                f"{vol:.1f} µL ({vol/1000:.3f} g)"
            )
        else:
            self.water_display.setText("-- µL (set calibration)")

    def get_summary_stats(self):
        """Return per-port stats for the active ports plus session totals."""
        active = self._active_ports if self._active_ports else list(ALL_PORTS)
        total = sum(self.n_trials[p] for p in active)
        total_correct = sum(self.n_correct[p] for p in active)
        total_incorrect = sum(self.n_incorrect[p] for p in active)
        total_timeouts = sum(self.n_timeouts[p] for p in active)
        total_rewards = sum(self.n_rewards[p] for p in active)
        return {
            'active_ports': list(active),
            'total_trials': total,
            'n_trials': {p: self.n_trials[p] for p in ALL_PORTS},
            'n_correct': {p: self.n_correct[p] for p in ALL_PORTS},
            'n_incorrect': {p: self.n_incorrect[p] for p in ALL_PORTS},
            'n_timeouts': {p: self.n_timeouts[p] for p in ALL_PORTS},
            'n_rewards': {p: self.n_rewards[p] for p in ALL_PORTS},
            'total_correct': total_correct,
            'total_incorrect': total_incorrect,
            'total_timeouts': total_timeouts,
            'total_rewards': total_rewards,
            'correct_rate': ((total_correct / total * 100)
                             if total > 0 else 0),
            'correct_rate_per_port': {
                p: ((self.n_correct[p] / self.n_trials[p] * 100)
                    if self.n_trials[p] > 0 else 0)
                for p in ALL_PORTS
            },
            'reward_rate': ((total_rewards / total * 100)
                            if total > 0 else 0),
            'vol_per': dict(self.vol_per),
            'total_water_ul': sum(self.n_rewards[p] * self.vol_per[p]
                                  for p in active),
        }

    def reset(self):
        self._reset()
        self._update_display()
        self.time_progress.setValue(0)
        self.timer_display.setText("00:00 / 30:00")


# ============================================================================
# STATUS INDICATOR
# ============================================================================

class StatusIndicator(QGroupBox):
    """Color-coded indicator of current paradigm state."""

    def __init__(self, parent=None):
        super().__init__("Trial Status", parent)
        self.setMinimumWidth(200)
        self.setMaximumWidth(340)
        layout = QVBoxLayout()
        self.status_label = QLabel("Idle")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        self.status_label.setFont(font)
        self.detail_label = QLabel("Press Start to begin session")
        self.detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail_label.setWordWrap(True)

        # Dwell progress bar (visible only while dwelling)
        self.dwell_bar = QProgressBar()
        self.dwell_bar.setRange(0, 1000)  # in milliseconds, scaled
        self.dwell_bar.setValue(0)
        self.dwell_bar.setTextVisible(False)
        self.dwell_bar.setMaximumHeight(10)
        self.dwell_bar.setStyleSheet(
            "QProgressBar::chunk { background-color: #EC9EC0; }"
        )

        layout.addWidget(self.status_label)
        layout.addWidget(self.detail_label)
        layout.addWidget(self.dwell_bar)
        self.setLayout(layout)
        self._apply('#808080')

    def _apply(self, bg, fg=None):
        # Auto-pick a legible text color from the background unless the
        # caller forces one (e.g. the pink "dwelling" state wants black).
        if fg is None:
            fg = _text_on(bg)
        self.status_label.setStyleSheet(
            f"background-color: {bg}; color: {fg}; padding: 12px; "
            "border-radius: 8px; font-weight: bold;"
        )

    def set_idle(self):
        self._apply('#808080')
        self.status_label.setText("Idle")
        self.detail_label.setText("Press Start to begin session")
        self.dwell_bar.setValue(0)

    def set_waiting_for_iz(self, trial_num=0):
        self._apply('#9E9E9E')  # Grey
        self.status_label.setText("Waiting for IZ")
        self.detail_label.setText(
            f"Mouse must enter initiation zone\n"
            f"(Trial {trial_num + 1} next)"
        )
        self.dwell_bar.setValue(0)

    def set_waiting_for_poke(self, blocked_ports, trial_num=0):
        self._apply('#9E9E9E')  # Grey
        self.status_label.setText("Waiting for poke")
        if blocked_ports:
            blocked_text = f"Blocked: {', '.join(blocked_ports)}"
        else:
            blocked_text = "All ports available"
        self.detail_label.setText(
            f"{blocked_text}\n(Reward {trial_num + 1} next)"
        )
        self.dwell_bar.setValue(0)

    def set_dwelling(self, dwell_sec, required_sec, trial_num=0):
        self._apply('#EC9EC0')  # Pink
        self.status_label.setText("Dwelling in IZ")
        pct = (min(1.0, dwell_sec / required_sec)
               if required_sec > 0 else 0.0)
        self.detail_label.setText(
            f"{dwell_sec:.2f} / {required_sec:.2f} s\n"
            f"(Trial {trial_num + 1} initiating)"
        )
        self.dwell_bar.setValue(int(pct * 1000))

    def set_active(self, port_key, trial_num=0):
        color = PORT_COLORS_DARK.get(port_key, '#1976D2')
        self._apply(color)
        self.status_label.setText(
            f"Trial {trial_num} Active — Port {port_key}"
        )
        label = PORT_MAP.get(port_key, {}).get('label', f"Port {port_key}")
        self.detail_label.setText(f"Sound playing from {label}")
        self.dwell_bar.setValue(0)

    def set_iti(self, seconds_remaining, trial_num=0):
        self._apply('#000000')  # Black
        self.status_label.setText("Inter-trial interval")
        self.detail_label.setText(
            f"{seconds_remaining:.1f} s remaining\n"
            f"(Trial {trial_num + 1} next)"
        )
        self.dwell_bar.setValue(0)

    def set_error_iti(self, seconds_remaining, trial_num=0):
        self._apply('#000000')  # Black — same as standard ITI
        self.status_label.setText("Error ITI")
        self.detail_label.setText(
            f"Penalty: {seconds_remaining:.1f} s remaining\n"
            f"(incorrect trial — Trial {trial_num + 1} next)"
        )
        self.dwell_bar.setValue(0)

    def set_ended(self):
        self._apply('#212121')
        self.status_label.setText("Session Complete")
        self.detail_label.setText("Data and video saved")
        self.dwell_bar.setValue(0)


# ============================================================================
# POKE INDICATORS (one per port; only the active set is shown)
# ============================================================================

class PokeIndicatorPanel(QGroupBox):
    """
    Six color-coded indicators (one per port) that light up when a poke
    is detected. Each indicator stays lit for ``flash_ms`` milliseconds.

    All 6 ports are active in this paradigm, so all 6 indicators are
    always shown. ``set_active_ports`` is retained as a no-op so the
    widget keeps the same API as its 3-port ancestor.
    """

    def __init__(self, flash_ms=300, parent=None):
        super().__init__("Poke Indicators", parent)
        self.flash_ms = flash_ms

        layout = QHBoxLayout()
        layout.setSpacing(8)

        self._indicators: Dict[str, QLabel] = {}
        self._idle_styles: Dict[str, str] = {}
        self._active_styles: Dict[str, str] = {}
        self._timers: Dict[str, QTimer] = {}

        for port_key in ALL_PORTS:
            idle, active = _poke_indicator_styles(port_key)
            self._idle_styles[port_key] = idle
            self._active_styles[port_key] = active

            lbl = QLabel(f"Port {port_key}")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setMinimumHeight(36)
            lbl.setStyleSheet(idle)
            layout.addWidget(lbl)
            self._indicators[port_key] = lbl

            t = QTimer()
            t.setSingleShot(True)
            # Default closure captures port_key
            t.timeout.connect(
                lambda pk=port_key: self._indicators[pk].setStyleSheet(
                    self._idle_styles[pk]
                )
            )
            self._timers[port_key] = t

        self.setLayout(layout)
        # All 6 indicators are always visible; set_active_ports is a no-op.

    def set_active_ports(self, ports):
        """No-op — all 6 indicators are always visible."""
        return

    def flash(self, port_key):
        """Light up the indicator for the given port (no-op if unknown)."""
        if port_key not in self._indicators:
            return
        self._indicators[port_key].setStyleSheet(
            self._active_styles[port_key]
        )
        self._timers[port_key].start(self.flash_ms)


# ============================================================================
# MANUAL REWARD PANEL (priming / flushing; active ports only)
# ============================================================================

class ManualRewardPanel(QGroupBox):
    """Per-port buttons for delivering water manually without starting a trial.

    Useful for priming valves and flushing lines between sessions. All 6
    ports are active in this paradigm, so all 6 buttons are always shown.
    """

    reward_requested = pyqtSignal(str)  # Emits the port key

    def __init__(self, parent=None):
        super().__init__("Manual Reward (priming / flushing)", parent)
        layout = QHBoxLayout()
        layout.setSpacing(8)

        self._buttons: Dict[str, QPushButton] = {}
        for port_key in ALL_PORTS:
            btn = QPushButton(f"Water → {port_key}")
            btn.setStyleSheet(_reward_btn_style(port_key))
            btn.clicked.connect(
                lambda _=False, pk=port_key: self.reward_requested.emit(pk)
            )
            layout.addWidget(btn)
            self._buttons[port_key] = btn

        self.setLayout(layout)

    def set_active_ports(self, ports):
        """No-op — all 6 buttons are always visible."""
        return


# ============================================================================
# INITIATION ZONE CONFIG WIDGET
# ============================================================================

class InitiationZoneConfigWidget(QGroupBox):
    """Spinners for IZ radius and dwell time, plus a live dwell readout."""

    radius_changed = pyqtSignal(float)
    dwell_changed = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__("Initiation Zone (IZ)", parent)
        layout = QGridLayout()
        layout.setSpacing(6)

        layout.addWidget(QLabel("IZ radius:"), 0, 0)
        self.iz_radius_spin = QDoubleSpinBox()
        self.iz_radius_spin.setRange(5.0, 400.0)
        self.iz_radius_spin.setDecimals(0)
        self.iz_radius_spin.setSingleStep(5.0)
        self.iz_radius_spin.setValue(DEFAULT_IZ_RADIUS_PX)
        self.iz_radius_spin.setSuffix(" px")
        self.iz_radius_spin.setToolTip(
            "Radius of the circular initiation zone, in display-frame "
            "pixels.\nCentered on the middle of the video view."
        )
        self.iz_radius_spin.valueChanged.connect(self.radius_changed)
        layout.addWidget(self.iz_radius_spin, 0, 1)

        layout.addWidget(QLabel("Dwell time:"), 1, 0)
        self.dwell_spin = QDoubleSpinBox()
        self.dwell_spin.setRange(0.05, 30.0)
        self.dwell_spin.setDecimals(2)
        self.dwell_spin.setSingleStep(0.1)
        self.dwell_spin.setValue(DEFAULT_DWELL_SEC)
        self.dwell_spin.setSuffix(" s")
        self.dwell_spin.setToolTip(
            "Continuous time the centroid must remain in the IZ to\n"
            "trigger a trial."
        )
        self.dwell_spin.valueChanged.connect(self.dwell_changed)
        layout.addWidget(self.dwell_spin, 1, 1)

        # Live dwell readout
        layout.addWidget(QLabel("Current dwell:"), 2, 0)
        self.live_dwell_label = QLabel("--")
        self.live_dwell_label.setStyleSheet("font-family: monospace;")
        layout.addWidget(self.live_dwell_label, 2, 1)

        self.setLayout(layout)

    def set_live_dwell(self, in_zone, dwell_sec, required_sec):
        if in_zone:
            self.live_dwell_label.setText(
                f"{dwell_sec:.2f} / {required_sec:.2f} s"
            )
            self.live_dwell_label.setStyleSheet(
                "font-family: monospace; color: #FF9800; font-weight: bold;"
            )
        else:
            self.live_dwell_label.setText("out of zone")
            self.live_dwell_label.setStyleSheet(
                "font-family: monospace; color: #777;"
            )

    def get_radius(self):
        return float(self.iz_radius_spin.value())

    def get_dwell_sec(self):
        return float(self.dwell_spin.value())


# ============================================================================
# ACTIVE PORTS DISPLAY (fixed: all 6)
# ============================================================================

class ActivePortsDisplay(QWidget):
    """Read-only banner showing the fixed 6-port active set.

    Replaces the 3-port paradigm's ACE/BDF ``SpeakerSetWidget``. There is
    nothing to choose here — every port is active in every session — so
    this is a static label rather than a control. It sits in the same slot
    inside the "Set every session" box, which now contains only Subject
    and Trainer as things the experimenter must actually fill in.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        chips = QHBoxLayout()
        chips.setSpacing(4)
        for port_key in ACTIVE_PORTS:
            fill = PORT_COLORS_DARK[port_key]
            chip = QLabel(port_key)
            chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chip.setFixedWidth(22)
            chip.setStyleSheet(
                f"background-color: {fill}; color: {_text_on(fill)}; "
                f"border: 1px solid {PORT_COLORS_DARK_BORDER[port_key]}; "
                "border-radius: 4px; padding: 2px; "
                "font-weight: bold; font-size: 10px;"
            )
            chips.addWidget(chip)
        layout.addLayout(chips)

        note = QLabel("all 6 active")
        note.setStyleSheet("color: #777; font-style: italic;")
        layout.addWidget(note)
        layout.addStretch()
        self.setLayout(layout)
        self.setToolTip(
            "All 6 ports are active in every session of this paradigm.\n\n"
            "The target port for each trial is drawn independently and "
            "uniformly at random\nfrom all 6 ports — there is no "
            "no-repeat rule, so the previous trial's target\nand the port "
            "the mouse last poked are both eligible again "
            "(p = 1/6 of an\nimmediate repeat)."
        )

    # --- API kept compatible with the 3-port SpeakerSetWidget ---------
    def has_selection(self) -> bool:
        """Always True — the active set is fixed, nothing to select."""
        return True

    def get_active_ports(self) -> Tuple[str, ...]:
        return ACTIVE_PORTS

    def get_set_name(self) -> str:
        return ACTIVE_SET_NAME


# ============================================================================
# SESSION SETUP WIDGET (Subject / Trainer + fixed params)
# ============================================================================

class SessionSetupWidget(QGroupBox):
    """Session-info panel for this paradigm.

    Drop-in replacement for ``phonotaxis.widgets.SessionInfo`` that
    groups the entries which MUST be set every session — Subject and
    Trainer — into a single highlighted "Set every session" box at the
    top, visually separated from the fixed session parameters (session
    duration) below. The highlight makes it obvious at a glance which
    fields the experimenter is responsible for each run, so none gets
    forgotten.

    The 3-port paradigm also required a Speaker-set choice here. That is
    gone: all 6 ports are active every session, so the active set is
    shown as a read-only banner (``ActivePortsDisplay``) rather than a
    control, and only Subject + Trainer gate the Start button.

    Exposes the minimal API the paradigm relies on, so it slots in
    wherever ``widgets.SessionInfo`` was used:
        get_value('subject' | 'trainer' | 'maxSessionDuration' | 'maxTrials')
        set_values({...})
        setEnabled(bool)            # inherited from QGroupBox; cascades
                                    # to children, locking the panel
                                    # mid-session
    plus a ``values_changed`` signal that fires whenever subject or
    trainer changes (used by the paradigm to gate the Start button).
    """

    values_changed = pyqtSignal()

    def __init__(self, active_ports_widget: ActivePortsDisplay, parent=None):
        super().__init__("Session Info", parent)
        self.active_ports_widget = active_ports_widget
        # maxTrials is retained for API compatibility (read via get_value
        # elsewhere); the session ends on the duration timer, so it has
        # no dedicated spinbox.
        self._max_trials = float('inf')

        outer = QVBoxLayout()
        outer.setSpacing(8)

        bold = QFont()
        bold.setBold(True)

        # --- Highlighted "Set every session" box ---------------------
        self.per_session_box = QGroupBox("Set every session")
        self.per_session_box.setStyleSheet(STYLE_PER_SESSION_BOX)
        ps_grid = QGridLayout()
        ps_grid.setSpacing(6)
        ps_grid.setColumnStretch(1, 1)

        subject_lbl = QLabel("Subject:")
        subject_lbl.setFont(bold)
        self.subject_edit = QLineEdit()
        self.subject_edit.setPlaceholderText("subject ID")
        ps_grid.addWidget(subject_lbl, 0, 0)
        ps_grid.addWidget(self.subject_edit, 0, 1)

        trainer_lbl = QLabel("Trainer:")
        trainer_lbl.setFont(bold)
        self.trainer_edit = QLineEdit()
        self.trainer_edit.setPlaceholderText("trainer initials")
        ps_grid.addWidget(trainer_lbl, 1, 0)
        ps_grid.addWidget(self.trainer_edit, 1, 1)

        ports_lbl = QLabel("Ports:")
        ports_lbl.setFont(bold)
        ps_grid.addWidget(ports_lbl, 2, 0)
        ps_grid.addWidget(self.active_ports_widget, 2, 1)

        self.per_session_box.setLayout(ps_grid)
        outer.addWidget(self.per_session_box)

        # --- Fixed / rarely-changed parameters -----------------------
        fixed_box = QGroupBox("Fixed (rarely changed)")
        fixed_box.setStyleSheet(STYLE_FIXED_BOX)
        fx_grid = QGridLayout()
        fx_grid.setSpacing(6)
        fx_grid.setColumnStretch(1, 1)

        fx_grid.addWidget(QLabel("Session duration:"), 0, 0)
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(1, 86400)
        self.duration_spin.setSingleStep(60)
        self.duration_spin.setSuffix(" s")
        self.duration_spin.setValue(1800)
        self.duration_spin.setToolTip(
            "Maximum session length in seconds. The session auto-saves "
            "and ends when this many seconds have elapsed."
        )
        fx_grid.addWidget(self.duration_spin, 0, 1)

        fixed_box.setLayout(fx_grid)
        outer.addWidget(fixed_box)

        self.setLayout(outer)

        # Fire values_changed on any change to the two per-session
        # entries so the paradigm can enable/disable the Start button.
        self.subject_edit.textChanged.connect(
            lambda *_: self.values_changed.emit()
        )
        self.trainer_edit.textChanged.connect(
            lambda *_: self.values_changed.emit()
        )

    # ----- API compatible with phonotaxis widgets.SessionInfo --------
    def get_value(self, key: str):
        if key == 'subject':
            return self.subject_edit.text()
        if key == 'trainer':
            return self.trainer_edit.text()
        if key == 'maxSessionDuration':
            return self.duration_spin.value()
        if key == 'maxTrials':
            return self._max_trials
        raise KeyError(f"Unknown session parameter: {key!r}")

    def set_values(self, values: dict):
        if 'subject' in values:
            self.subject_edit.setText(str(values['subject']))
        if 'trainer' in values:
            self.trainer_edit.setText(str(values['trainer']))
        if 'maxSessionDuration' in values:
            self.duration_spin.setValue(int(values['maxSessionDuration']))
        if 'maxTrials' in values:
            self._max_trials = values['maxTrials']

    def is_ready(self) -> bool:
        """True iff Subject and Trainer are both set.

        Used to gate the Start button so the experimenter cannot start a
        session with either per-session entry left blank. (The 3-port
        paradigm also gated on a Speaker-set choice; there is no such
        choice here.)
        """
        return (
            bool(self.subject_edit.text().strip())
            and bool(self.trainer_edit.text().strip())
        )


# ============================================================================
# POKE TRACKER (Non-visual logic module)
# ============================================================================

class PokeTracker:
    """
    Tracks poke events during an active trial.

    Records the first poke at the target (correct) port and the first
    poke at any other port (incorrect), plus a complete log of every
    poke received during the trial in ``all_pokes`` as ``(time, port)``.

    ``active_set`` (passed in via ``start_trial``) is all 6 ports in this
    paradigm, so ``n_pokes_inactive_ports`` is structurally always 0. The
    field is kept — rather than deleted — so the HDF5 layout stays
    identical to v4 and existing readers don't need a special case.
    """

    def __init__(self):
        self.trial_active = False
        self.active_port = None             # the trial's target port
        self.active_set: Tuple[str, ...] = ()  # all currently-active ports
        self.trial_onset_time = None
        # "First of each type" for outcome logic
        self.active_poke_detected = False
        self.active_poke_time = None
        self.other_poke_detected = False
        self.other_poke_time = None
        # Complete trial poke log: list of (absolute_time, port_key)
        self.all_pokes: List[tuple] = []
        # Shaping: first port poked in the trial (None if no poke), and
        # number of non-target pokes BEFORE the first target poke (pokes
        # after the reward, e.g. during post-poke sound, are not counted).
        self.first_poked_port = None
        self.n_incorrect_before_correct = 0

    def start_trial(self, port_key, onset_time, active_set):
        self.trial_active = True
        self.active_port = port_key
        self.active_set = tuple(active_set)
        self.trial_onset_time = onset_time
        self.active_poke_detected = False
        self.active_poke_time = None
        self.other_poke_detected = False
        self.other_poke_time = None
        self.all_pokes = []
        self.first_poked_port = None
        self.n_incorrect_before_correct = 0

    def on_poke(self, port_key, poke_time):
        if not self.trial_active:
            return
        # Always record in the per-trial log
        self.all_pokes.append((poke_time, port_key))
        if self.first_poked_port is None:
            self.first_poked_port = port_key
        if port_key != self.active_port and not self.active_poke_detected:
            self.n_incorrect_before_correct += 1
        # First-of-type bookkeeping (target vs other-active)
        if port_key == self.active_port and not self.active_poke_detected:
            self.active_poke_detected = True
            self.active_poke_time = poke_time
        elif (port_key != self.active_port
              and port_key in self.active_set
              and not self.other_poke_detected):
            self.other_poke_detected = True
            self.other_poke_time = poke_time

    def end_trial(self, end_time):
        latency = None
        if self.active_poke_detected and self.active_poke_time is not None:
            latency = self.active_poke_time - self.trial_onset_time
        result = {
            'active_port': self.active_port,
            'trial_onset_time': self.trial_onset_time,
            'trial_end_time': end_time,
            'poke_detected': self.active_poke_detected,
            'poke_time': self.active_poke_time,
            'latency': latency,
            'other_poke_detected': self.other_poke_detected,
            'other_poke_time': self.other_poke_time,
            'first_poked_port': self.first_poked_port,
            'n_incorrect_before_correct': self.n_incorrect_before_correct,
            'all_pokes': list(self.all_pokes),
            'n_pokes_active_port': sum(
                1 for _, p in self.all_pokes if p == self.active_port
            ),
            'n_pokes_other_port': sum(
                1 for _, p in self.all_pokes
                if p != self.active_port and p in self.active_set
            ),
            # Always 0 in the 6-port paradigm (every port is active).
            # Retained for schema compatibility with v4 files.
            'n_pokes_inactive_ports': sum(
                1 for _, p in self.all_pokes if p not in self.active_set
            ),
        }
        self.trial_active = False
        return result


# ============================================================================
# EVENT LOG (long-format, one row per event)
# ============================================================================

# Canonical event-type vocabulary. Saved as a JSON string attr on the
# enum dataset so the h5 is self-describing.
EVENT_TYPES: Dict[str, int] = {
    'session_start':          0,
    'session_end':            1,
    'trial_start':            2,
    'trial_end':              3,
    'iti_start':              4,
    'iti_end':                5,
    'dwell_enter':            6,
    'dwell_exit':             7,
    'poke_A':                 8,
    'poke_B':                 9,
    'poke_C':                10,
    'poke_D':                11,
    'poke_E':                12,
    'poke_F':                13,
    'sound_on':              14,
    'sound_off':             15,
    'valve_open_A':          16,
    'valve_open_B':          17,
    'valve_open_C':          18,
    'valve_open_D':          19,
    'valve_open_E':          20,
    'valve_open_F':          21,
    'valve_close_A':         22,
    'valve_close_B':         23,
    'valve_close_C':         24,
    'valve_close_D':         25,
    'valve_close_E':         26,
    'valve_close_F':         27,
    'manual_reward_A':       28,
    'manual_reward_B':       29,
    'manual_reward_C':       30,
    'manual_reward_D':       31,
    'manual_reward_E':       32,
    'manual_reward_F':       33,
    'post_poke_sound_start': 34,
    'post_poke_sound_end':   35,
    'error_iti_start':       36,
    'error_iti_end':         37,
}

# Numeric port enum, used for the `port` column of /events and elsewhere.
PORT_TO_INT: Dict[Optional[str], int] = {
    'A': 0, 'B': 1, 'C': 2, 'D': 3, 'E': 4, 'F': 5, None: -1,
}
PORT_ENUM_MAP: Dict[str, int] = {p: PORT_TO_INT[p] for p in ALL_PORTS}


class EventLog:
    """
    Long-format event log. One row per event with:
        time_sec   : float, seconds relative to session_start_time
        event_type : int (see EVENT_TYPES)
        port       : int (0=A,1=B,...,5=F, -1=not applicable)
        trial_num  : int (0-indexed trial; -1 if no trial active)

    Captures everything that happens during a session, including events
    that don't fit per-trial arrays (between-trial pokes, multiple
    pokes per trial, manual rewards, dwell enter/exit, pokes at
    inactive ports, etc.).
    """

    def __init__(self):
        self.times: List[float] = []
        self.event_types: List[int] = []
        self.ports: List[int] = []
        self.trial_nums: List[int] = []
        # Optional crash-safe journal. When set (by the paradigm at session
        # start), every logged event is also mirrored to the journal.
        self._journal = None

    def clear(self):
        self.times.clear()
        self.event_types.clear()
        self.ports.clear()
        self.trial_nums.clear()

    def log(self, event_name, time_rel, port=None, trial_num=-1):
        """Log an event. ``time_rel`` must already be relative to session start."""
        if event_name not in EVENT_TYPES:
            print(f"[EventLog] WARNING: unknown event '{event_name}' — skipped")
            return
        self.times.append(float(time_rel))
        self.event_types.append(EVENT_TYPES[event_name])
        self.ports.append(PORT_TO_INT.get(port, -1))
        self.trial_nums.append(int(trial_num))

        # Mirror to the crash-safe journal, if one is attached.
        if self._journal is not None:
            try:
                self._journal.log_event({
                    'event': event_name,
                    'time_sec': float(time_rel),
                    'port': port,
                    'trial_num': int(trial_num),
                })
            except Exception:
                pass

    def __len__(self):
        return len(self.times)

    def as_arrays(self):
        """Return (times, event_types, ports, trial_nums) as numpy arrays."""
        return (
            np.array(self.times, dtype=np.float64),
            np.array(self.event_types, dtype=np.int32),
            np.array(self.ports, dtype=np.int8),
            np.array(self.trial_nums, dtype=np.int32),
        )


# ============================================================================
# FRAME TRACKER (per-frame phase + IZ state, co-indexed with video)
# ============================================================================

# Phase enum — what the paradigm was doing at each frame.
PHASES = {
    'idle':            0,
    'waiting_for_iz':  1,
    'dwelling':        2,
    'trial_active':    3,
    'post_poke_sound': 4,
    'iti':             5,
    'waiting_for_poke': 6,   # poke training: no IZ, waiting for a poke
}


class FrameTracker:
    """
    Per-frame stream of paradigm state. Written to by ``_display_frame``
    on every frame the video thread emits.

    Each entry is time-aligned with the corresponding video-thread
    frame (same timestamp), and includes the tracked mouse centroid
    (x, y, valid) co-indexed with the rest of the per-frame state.
    This is what gets saved as the canonical ``/tracking`` group in
    the HDF5 file (centroid_x_display_px, centroid_y_display_px,
    centroid_valid alongside phase, in_iz, dwell_sec, etc.).
    """

    def __init__(self):
        self.timestamps: List[float] = []   # absolute time.time()
        self.phases: List[int] = []
        self.trial_nums: List[int] = []
        self.in_iz: List[bool] = []
        self.dwell_secs: List[float] = []
        # Centroid in display-frame pixels. ``valid`` is False for frames
        # where tracking didn't detect a mouse (centroid is undefined).
        self.centroid_x: List[float] = []
        self.centroid_y: List[float] = []
        self.centroid_valid: List[bool] = []

    def clear(self):
        self.timestamps.clear()
        self.phases.clear()
        self.trial_nums.clear()
        self.in_iz.clear()
        self.dwell_secs.clear()
        self.centroid_x.clear()
        self.centroid_y.clear()
        self.centroid_valid.clear()

    def record(self, timestamp, phase_name, trial_num, in_iz, dwell_sec,
               centroid=None):
        """Append one per-frame record.

        ``centroid`` is an (x, y) tuple or None. None / invalid coords
        are recorded as NaN with ``centroid_valid=False`` so the array
        stays a fixed-length time series (no gaps in the timestamps).
        """
        self.timestamps.append(float(timestamp))
        self.phases.append(PHASES.get(phase_name, PHASES['idle']))
        self.trial_nums.append(int(trial_num))
        self.in_iz.append(bool(in_iz))
        self.dwell_secs.append(float(dwell_sec))
        if centroid is not None:
            try:
                cx = float(centroid[0])
                cy = float(centroid[1])
                if cx >= 0 and cy >= 0 and np.isfinite(cx) and np.isfinite(cy):
                    self.centroid_x.append(cx)
                    self.centroid_y.append(cy)
                    self.centroid_valid.append(True)
                    return
            except (TypeError, IndexError, ValueError):
                pass
        # No valid centroid this frame
        self.centroid_x.append(float('nan'))
        self.centroid_y.append(float('nan'))
        self.centroid_valid.append(False)

    def __len__(self):
        return len(self.timestamps)


# ============================================================================
# TRIAL EVENT LOG (Rolling Table)
# ============================================================================

class TrialEventLog(QGroupBox):
    """Scrolling table showing every trial with outcome and latency."""

    def __init__(self, parent=None):
        super().__init__("Trial Log", parent)
        layout = QVBoxLayout()

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        # Poke training: the last two columns show the time since the
        # previous reward and the pokes at blocked ports before this one
        # (passed in as ``latency`` and ``dwell_sec`` by the paradigm).
        self.table.setHorizontalHeaderLabels([
            "Trial", "Time", "Port", "Outcome", "Since prev (s)",
            "Blocked pokes"
        ])
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(False)
        self.table.setMinimumHeight(180)
        self.table.verticalHeader().setVisible(False)

        layout.addWidget(self.table)
        self.setLayout(layout)

    def add_trial(self, trial_num, time_str, port_key, outcome,
                  latency, dwell_sec, poked_port=None,
                  n_errors_before_correct=0):
        """Add a completed trial row to the table.

        ``port_key`` is the trial's TARGET port. ``poked_port``, when
        given, is the port the mouse actually poked to end the trial —
        for an incorrect trial this is the (wrong) port that was poked,
        and it is shown in the Outcome column as e.g. "Incorrect (D)".
        With all 6 ports active it may be any of the 5 non-target ports.
        ``poked_port`` is ignored for correct/timeout outcomes.
        """
        row = self.table.rowCount()
        self.table.insertRow(row)

        outcome_str = {'correct': 'Correct',
                       'incorrect': 'Incorrect',
                       'timeout': 'Timeout'}.get(outcome, outcome)
        # For incorrect trials, annotate with the port that was wrongly
        # poked so the experimenter can see the error pattern at a glance.
        if outcome == 'incorrect' and poked_port:
            outcome_str = f"Incorrect ({poked_port})"
        # Shaping: correct after poking elsewhere first (kept short to fit
        # the column), e.g. "2err+Correct"
        if outcome == 'correct' and n_errors_before_correct > 0:
            outcome_str = f"{n_errors_before_correct}err+Correct"

        items = [
            QTableWidgetItem(str(trial_num + 1)),
            QTableWidgetItem(time_str),
            QTableWidgetItem(f"Port {port_key}"),
            QTableWidgetItem(outcome_str),
            QTableWidgetItem(
                f"{latency:.2f}" if latency is not None else "--"
            ),
            QTableWidgetItem(
                "--" if dwell_sec is None
                else (str(dwell_sec) if isinstance(dwell_sec, int)
                      else f"{dwell_sec:.2f}")
            ),
        ]

        port_bg = PORT_COLORS_LIGHT.get(port_key, QColor(220, 220, 220))
        # For incorrect trials, the Outcome cell (col 3) is tinted with
        # the *poked* port's color so the error port stands out.
        poked_bg = (PORT_COLORS_LIGHT.get(poked_port)
                    if (outcome == 'incorrect' and poked_port) else None)
        for col, item in enumerate(items):
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            # Column 2 (Port) always uses the per-port default color.
            # For all other columns:
            #   correct   → white background, black text
            #   incorrect → dark grey background, white text, EXCEPT the
            #               Outcome cell which is tinted with the poked
            #               port's color (black text) to flag the error
            #   timeout   → per-port default color (same as Port column)
            if col == 2:
                item.setBackground(QBrush(port_bg))
            elif outcome == 'correct':
                item.setBackground(QBrush(COLOR_TRIAL_CORRECT))
                item.setForeground(QBrush(QColor(0, 0, 0)))
            elif outcome == 'incorrect':
                if col == 3 and poked_bg is not None:
                    item.setBackground(QBrush(poked_bg))
                    item.setForeground(QBrush(QColor(0, 0, 0)))
                else:
                    item.setBackground(QBrush(COLOR_TRIAL_INCORRECT))
                    item.setForeground(QBrush(QColor(255, 255, 255)))
            else:  # timeout
                item.setBackground(QBrush(port_bg))
            self.table.setItem(row, col, item)

        self.table.scrollToBottom()


# ============================================================================
# VOLUME CALIBRATION WIDGET (per-port; only active ports shown)
# ============================================================================

# Default per-port valve durations / volumes. All 6 ports are used every
# session in this paradigm, so all 6 must be calibrated — these defaults
# are only a starting point and should be re-measured for each rig.
DEFAULT_VALVE_DUR_SEC: Dict[str, float] = {
    'A': 0.054, 'B': 0.054,
    'C': 0.056, 'D': 0.052,
    'E': 0.052, 'F': 0.052,
}
DEFAULT_VALVE_VOL_UL: Dict[str, float] = {
    'A': 7.76, 'B': 7.80,
    'C': 7.64, 'D': 7.64,
    'E': 7.70, 'F': 7.80,
}


class VolumeCalibrationWidget(QGroupBox):
    """Per-port spinboxes for water volume calibration and valve open
    durations.

    All 6 ports are active in this paradigm, so all 6 rows are always
    shown and all 6 must be calibrated (the 3-port version hid the rows
    for the inactive triplet).

    Emits ``calibration_changed`` whenever any µL value changes; the
    handler can read all 6 via ``get_values()``.
    """

    calibration_changed = pyqtSignal(dict)  # {port_key: vol_ul, ...}

    def __init__(self, parent=None):
        super().__init__("Water Calibration & Valve Durations", parent)
        layout = QGridLayout()
        layout.setSpacing(6)

        # Header row
        layout.addWidget(QLabel(""), 0, 0)
        dur_hdr = QLabel("Valve open duration")
        dur_hdr.setStyleSheet("font-weight: bold;")
        layout.addWidget(dur_hdr, 0, 1)
        vol_hdr = QLabel("µL per valve open")
        vol_hdr.setStyleSheet("font-weight: bold;")
        layout.addWidget(vol_hdr, 0, 2)

        # Per-port rows
        self._port_labels: Dict[str, QLabel] = {}
        self._dur_spins: Dict[str, QDoubleSpinBox] = {}
        self._vol_spins: Dict[str, QDoubleSpinBox] = {}

        for i, port_key in enumerate(ALL_PORTS):
            row = i + 1
            lbl = QLabel(f"Valve {port_key}:")
            layout.addWidget(lbl, row, 0)
            self._port_labels[port_key] = lbl

            dur = QDoubleSpinBox()
            dur.setRange(0.001, 5.0)
            dur.setDecimals(3)
            dur.setSingleStep(0.005)
            dur.setValue(DEFAULT_VALVE_DUR_SEC[port_key])
            dur.setSuffix(" s")
            layout.addWidget(dur, row, 1)
            self._dur_spins[port_key] = dur

            vol = QDoubleSpinBox()
            vol.setRange(0.0, 100.0)
            vol.setDecimals(2)
            vol.setSingleStep(0.1)
            vol.setValue(DEFAULT_VALVE_VOL_UL[port_key])
            vol.setSuffix(" µL")
            vol.valueChanged.connect(self._emit)
            layout.addWidget(vol, row, 2)
            self._vol_spins[port_key] = vol

        self.setLayout(layout)

    def set_active_ports(self, ports):
        """No-op — all 6 rows are always visible. Re-emits the current
        calibration so downstream widgets (e.g. the dashboard water
        tally) pick it up."""
        self._emit()

    def _emit(self):
        self.calibration_changed.emit(self.get_values())

    def get_values(self) -> Dict[str, float]:
        """Return {port_key: µL_per_open} for all 6 ports."""
        return {p: float(self._vol_spins[p].value()) for p in ALL_PORTS}

    def get_valve_durations(self) -> Dict[str, float]:
        """Return {port_key: valve_open_seconds} for all 6 ports."""
        return {p: float(self._dur_spins[p].value()) for p in ALL_PORTS}


# ============================================================================
# SESSION SUMMARY DIALOG
# ============================================================================

class SessionSummaryDialog(QDialog):
    """Modal dialog showing session summary when session ends."""

    def __init__(self, stats, subject, trainer, session_minutes,
                 mean_lat, median_lat, mean_lat_per_port,
                 speaker_set_name, active_ports,
                 data_fp, video_fp, notes, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Session Complete")
        self.setMinimumSize(560, 660)

        layout = QVBoxLayout()

        header = QLabel("Session Complete!")
        header.setStyleSheet(
            "font-size: 18pt; font-weight: bold; color: #4CAF50;"
        )
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        info = QLabel(
            f"Subject: {subject}  |  Paradigm: {PARADIGM_NAME}"
        )
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setStyleSheet("font-size: 11pt; color: #666;")
        layout.addWidget(info)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        txt = QTextEdit()
        txt.setReadOnly(True)
        txt.setStyleSheet("font-family: monospace; font-size: 10pt;")

        total = stats['total_trials']
        correct_rate_str = (f"{stats['correct_rate']:.1f}%"
                            if total > 0 else "N/A")
        reward_rate_str = (f"{stats['reward_rate']:.1f}%"
                           if total > 0 else "N/A")
        mean_str = f"{mean_lat:.2f}s" if mean_lat is not None else "N/A"
        median_str = (f"{median_lat:.2f}s"
                      if median_lat is not None else "N/A")

        # Per-port lines for the active set
        trials_lines = "\n".join(
            f"  Port {p}:          {stats['n_trials'][p]}"
            for p in active_ports
        )
        correct_per_port = "  ".join(
            f"{p}:{stats['n_correct'][p]}" for p in active_ports
        )
        incorrect_per_port = "  ".join(
            f"{p}:{stats['n_incorrect'][p]}" for p in active_ports
        )
        timeouts_per_port = "  ".join(
            f"{p}:{stats['n_timeouts'][p]}" for p in active_ports
        )
        rewards_per_port = "  ".join(
            f"{p}:{stats['n_rewards'][p]}" for p in active_ports
        )
        per_port_lat_strs = []
        for p in active_ports:
            v = mean_lat_per_port.get(p)
            per_port_lat_strs.append(f"{p}:{v:.2f}s" if v is not None
                                     else f"{p}:N/A")
        per_port_lat_line = "  ".join(per_port_lat_strs)
        cal_line = "  ".join(
            f"{p}={stats['vol_per'][p]:.2f}µL" for p in active_ports
        )

        summary = f"""
===============================================
             SESSION SUMMARY
===============================================

Trainer: {trainer}
Session Duration: {session_minutes:.1f} min
Active ports: {speaker_set_name} ({' / '.join(active_ports)})
Chance level: {CHANCE_LEVEL_PCT:.1f}%  (uniform random over {len(active_ports)} ports)

TRIALS
-----------------------------------------------
  Total:           {total}
{trials_lines}

OUTCOMES
-----------------------------------------------
  Correct-poke rate: {correct_rate_str}  (chance {CHANCE_LEVEL_PCT:.1f}%)
  Correct per port:  {correct_per_port}
  Incorrect:         {incorrect_per_port}
  Timeouts:          {timeouts_per_port}

REWARDS
-----------------------------------------------
  Reward Rate:       {reward_rate_str}
  Per port:          {rewards_per_port}
  Total:             {stats['total_rewards']} / {total}

LATENCY TO CORRECT POKE
-----------------------------------------------
  Mean (overall):    {mean_str}
  Median:            {median_str}
  Per port (mean):   {per_port_lat_line}

WATER DELIVERED
-----------------------------------------------
  Total:             {stats['total_water_ul']:.1f} µL ({stats['total_water_ul']/1000:.3f} g)
  Calibration:       {cal_line}

FILES SAVED
-----------------------------------------------
  Data:  {os.path.basename(data_fp) if data_fp else 'Not saved'}
  Video: {os.path.basename(video_fp) if video_fp else 'Not saved'}

NOTES
-----------------------------------------------
{notes if notes else '(none)'}

===============================================
"""
        txt.setText(summary)
        layout.addWidget(txt)

        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(STYLE_BTN_START)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        self.setLayout(layout)


# ============================================================================
# DATA PATHS WIDGET
# ============================================================================

class DataPathsWidget(QGroupBox):
    """Adjustable file paths for where session data and video will be saved.

    Shows the current data and video directories with Browse buttons.
    Changes are applied to the live paradigm via signals — paths take
    effect at the next session start.
    """

    paths_changed = pyqtSignal(str, str)  # data_path, video_path

    def __init__(self, data_path: str, video_path: str, parent=None):
        super().__init__("Save Locations", parent)
        layout = QGridLayout()
        layout.setSpacing(6)

        # --- Data path row ---
        layout.addWidget(QLabel("Data folder:"), 0, 0)
        self.data_edit = QLineEdit(data_path)
        self.data_edit.setMinimumWidth(280)
        self.data_edit.editingFinished.connect(self._emit)
        layout.addWidget(self.data_edit, 0, 1)
        self.data_browse_btn = QPushButton("Browse…")
        self.data_browse_btn.clicked.connect(self._browse_data)
        layout.addWidget(self.data_browse_btn, 0, 2)

        # --- Video path row ---
        layout.addWidget(QLabel("Video folder:"), 1, 0)
        self.video_edit = QLineEdit(video_path)
        self.video_edit.setMinimumWidth(280)
        self.video_edit.editingFinished.connect(self._emit)
        layout.addWidget(self.video_edit, 1, 1)
        self.video_browse_btn = QPushButton("Browse…")
        self.video_browse_btn.clicked.connect(self._browse_video)
        layout.addWidget(self.video_browse_btn, 1, 2)

        self.setLayout(layout)

    def _browse_data(self):
        path = QFileDialog.getExistingDirectory(
            self, "Select data folder", self.data_edit.text()
        )
        if path:
            self.data_edit.setText(path)
            self._emit()

    def _browse_video(self):
        path = QFileDialog.getExistingDirectory(
            self, "Select video folder", self.video_edit.text()
        )
        if path:
            self.video_edit.setText(path)
            self._emit()

    def _emit(self):
        self.paths_changed.emit(self.get_data_path(), self.get_video_path())

    def get_data_path(self) -> str:
        return self.data_edit.text().strip()

    def get_video_path(self) -> str:
        return self.video_edit.text().strip()

    def setEnabled(self, enabled):  # type: ignore[override]
        super().setEnabled(enabled)
        for w in (self.data_edit, self.video_edit,
                  self.data_browse_btn, self.video_browse_btn):
            w.setEnabled(enabled)


# ============================================================================
# MAIN PARADIGM
# ============================================================================

class Paradigm(QMainWindow):
    """
    Main window for the 6-Port Poke Training paradigm.

    No initiation zone: a poke at any allowed port delivers water and
    plays the click train from that port for the reward sound duration.
    The rewarded port (and optionally its neighbors) is blocked for the
    next trial. See the module docstring.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("6-Port Poke Training — Automated")
        self.setWindowIcon(gui.create_icon())
        self.setMinimumSize(900, 600)

        # --- State variables ---
        self.session_running = False
        # Set True once a session has ended; keeps the Start button
        # permanently disabled afterward (one session per launch) so the
        # Start-button gating logic never re-enables it.
        self._session_finished = False
        self.session_start_time = None
        self.session_start_epoch = None
        self.session_end_epoch = None
        self.trial_active = False
        self.in_iti = False
        self._current_iti_is_error = False
        self.current_trial = 0
        self.data_saved = False
        self.current_data_filepath = None
        self.current_video_filepath = None
        self.sound_playing = False
        self._sounds_prebuilt = False
        self.arduino_connected = False

        # Trial outcome bookkeeping
        self.reward_delivered_this_trial = False
        self.current_trial_port: Optional[str] = None
        self.current_trial_dwell = None
        self.current_trial_outcome: Optional[str] = None
        self.incorrect_poke_stopped_sound = False
        self._in_post_poke_sound = False

        # IZ-dwell measurement for the Trial Log "Dwell" column.
        #
        # ``current_trial_dwell`` (shown in the Trial Log and saved as
        # ``dwell_duration``) is the TOTAL continuous time the mouse
        # spent inside the IZ for the bout that triggered the trial —
        # measured from when it entered the zone, through the trigger,
        # until it first leaves the zone. It therefore includes both
        # the pre-trial dwell that satisfied the trigger requirement
        # AND any extra time the mouse lingered in the IZ after the
        # trial started, so it is always >= the dwell requirement.
        #
        # The IZ tracker disables itself the instant a trial triggers,
        # so the post-trigger portion is measured here directly with
        # point_in_zone(). To match the tracker's behavior, a brief
        # dropout grace is applied: a momentary tracking glitch (a lost
        # or NaN centroid for a frame or two) does not prematurely end
        # the measurement — the mouse must be genuinely out of the zone
        # for longer than the grace window before the dwell is frozen.
        # State:
        #   _iz_dwell_anchor    — wall-clock time the mouse entered the
        #                         IZ (the tracker's dwell_start_time
        #                         captured at trigger); the dwell clock
        #                         counts up from here
        #   _iz_dwell_last_in   — wall-clock time the centroid was last
        #                         confirmed inside the IZ; used with the
        #                         grace window to ride out brief dropouts
        #   _iz_dwell_left      — True once the mouse has been out of the
        #                         IZ beyond the grace window, which
        #                         freezes the measurement for the trial
        # The pre-trial dwell that triggered the trial is still kept
        # separately as ``_last_trigger_dwell`` for the console message.
        self._iz_dwell_anchor: Optional[float] = None
        self._iz_dwell_last_in: Optional[float] = None
        self._iz_dwell_left: bool = False

        # Active ports. Fixed at all 6 for every session in this
        # paradigm — there is no per-session speaker-set choice.
        self._active_ports: Tuple[str, ...] = ACTIVE_PORTS
        # Port the mouse poked on the previous trial. None for the first
        # trial of a session and after any trial that timed out (no poke).
        #
        # NOTE: in the 3-port paradigm this drove the no-repeat selection
        # rule. Here it does NOT influence trial selection at all — the
        # target is drawn i.i.d. uniformly from all 6 ports. It is still
        # tracked and saved (`prev_poked_port`) because it remains a
        # useful regressor: win-stay/lose-shift, perseveration, and
        # previous-port effects on the approach trajectory.
        self._last_poked_port: Optional[str] = None
        # Bookkeeping: which port (if any) caused the current trial to
        # end. Set in the poke handler; cleared at trial start. None at
        # finalize means the trial timed out.
        self._trial_ended_by_port: Optional[str] = None

        # Poke training state
        self._blocked_rule = DEFAULT_BLOCKED_PORTS_RULE
        self._blocked_ports: Tuple[str, ...] = ()   # blocked for next reward
        self._n_blocked_pokes = 0     # blocked-port pokes since last trial
        self._last_reward_time: Optional[float] = None
        self._current_trial_blocked: Tuple[str, ...] = ()
        self._current_trial_n_blocked = 0
        self._current_trial_since_prev: Optional[float] = None

        # IZ tracker: kept because the inherited per-frame bookkeeping uses
        # it, but never enabled (and radius 0) in poke training.
        self.iz_tracker = InitiationZoneTracker()
        self.iz_tracker.set_zone(DEFAULT_MASK[0], DEFAULT_MASK[1], 0)
        self.iz_tracker.set_required_sec(DEFAULT_DWELL_SEC)
        self._last_iz_ui_update = 0.0

        # Poke tracker
        self.poke_tracker = PokeTracker()

        # Event log + frame-level state tracker
        self.event_log = EventLog()
        self.frame_tracker = FrameTracker()

        # Crash-safe session journal (created per-session in _start_session).
        self._session_journal: Optional[SessionJournal] = None

        # Per-trial data storage (lists, converted to arrays on save)
        self.trial_data: List[dict] = []

        # Manual-reward log: list of (abs_time, port_key)
        self._manual_reward_log: List[tuple] = []

        # --- Messenger ---
        self.messagebar = gui.Messenger()
        self.messagebar.timed_message.connect(
            lambda msg: self.statusBar().showMessage(msg)
        )
        self.messagebar.collect('Initializing paradigm...')

        # --- Build everything ---
        self._create_widgets()
        self._setup_parameters()
        self._setup_results_storage()
        self._setup_layout()
        self._setup_sound()
        self._setup_video()
        self._setup_hardware()
        self._connect_signals()

        # Push the fixed 6-port active set into every per-port widget
        self._apply_active_ports()

        # Initialize calibration (so the dashboard's water tally has the
        # current µL values from the moment the GUI opens)
        self._on_calibration_changed(self.volume_cal.get_values())

        # Start disabled until Subject and Trainer are set.
        self._update_start_enabled()

        self.messagebar.collect('Paradigm ready')

    # ====================================================================
    # SETUP METHODS
    # ====================================================================

    def _create_widgets(self):
        """Create all UI widgets."""
        # Video — controls=True keeps the threshold / min area / mask
        # radius sliders under the video (useful for live tracking tuning).
        self.video_widget = widgets.VideoWidget(
            controls=True,
            threshold=BLACK_THRESHOLD,
            minarea=MIN_AREA,
            mask_radius=DEFAULT_MASK[2]
        )
        self.video_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        # The VideoWidget's control panel ships with a binary/masked-view
        # toggle that is checked by default. Start it OFF so the paradigm
        # opens showing the plain camera view; the experimenter can still
        # turn it on manually for tracking tuning.
        self._uncheck_binary_mask_mode()

        # IZ config widget
        self.iz_config = InitiationZoneConfigWidget()

        # Active-ports banner (read-only: all 6, every session)
        self.active_ports_display = ActivePortsDisplay()

        # Poke indicators (all 6)
        self.poke_indicators = PokeIndicatorPanel()

        # Manual reward panel (priming / flushing; all 6)
        self.manual_reward_panel = ManualRewardPanel()

        # Session info — custom panel showing the fixed active-ports
        # banner alongside Subject/Trainer in a highlighted box.
        self.session_info = SessionSetupWidget(self.active_ports_display)
        self.session_info.set_values({
            'subject': '',
            'trainer': '',
            'maxSessionDuration': 1800,
            'maxTrials': float('inf'),
        })

        # Status indicator
        self.status_indicator = StatusIndicator()

        # Start/Stop button
        self.start_btn = QPushButton("Start Session")
        self.start_btn.setStyleSheet(STYLE_BTN_START)
        self.start_btn.clicked.connect(self._toggle_session)
        # Starts disabled — enabled only once Subject and Trainer are
        # filled in (see _update_start_enabled).
        self.start_btn.setEnabled(False)
        self.start_btn.setToolTip(
            "Fill in Subject and Trainer to enable."
        )

        # Save-data helper widget (kept for its to_file() API but NOT
        # shown in the UI; saving is automatic on session end).
        self.savedata_widget = savedata.SaveData(datadir=config.DATA_PATH)
        self.savedata_widget.log_message.connect(self.messagebar.collect)

        # Adjustable data/video save paths
        self.data_paths = DataPathsWidget(
            data_path=config.DATA_PATH,
            video_path=config.VIDEO_PATH,
        )
        self.data_paths.paths_changed.connect(self._on_paths_changed)

        # Hardware status banner
        self.hw_status_label = QLabel("Arduino: Connecting...")
        self.hw_status_label.setStyleSheet(
            "font-weight: bold; padding: 5px; background-color: #FFA726; "
            "border-radius: 4px; color: white;"
        )
        self.hw_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Performance dashboard
        self.dashboard = PerformanceDashboard()

        # Volume calibration (per-port)
        self.volume_cal = VolumeCalibrationWidget()

        # Trial event log
        self.trial_log = TrialEventLog()

        # Session notes
        self.notes_group = QGroupBox("Session Notes")
        notes_layout = QVBoxLayout()
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText(
            "Type observations here (saved with session data)..."
        )
        self.notes_edit.setMaximumHeight(80)
        notes_layout.addWidget(self.notes_edit)
        self.notes_group.setLayout(notes_layout)

        # Timers
        self.dashboard_timer = QTimer()
        self.dashboard_timer.timeout.connect(self._update_timer_display)

        self.iti_timer = QTimer()
        self.iti_timer.setSingleShot(True)
        self.iti_timer.timeout.connect(self._on_iti_end)

        # Trial timeout timer
        self.trial_timeout_timer = QTimer()
        self.trial_timeout_timer.setSingleShot(True)
        self.trial_timeout_timer.timeout.connect(self._on_trial_timeout)

        # Post-poke sound extension timer
        self.post_poke_sound_timer = QTimer()
        self.post_poke_sound_timer.setSingleShot(True)
        self.post_poke_sound_timer.timeout.connect(
            self._on_post_poke_sound_expired
        )

        # Debounce timer for sound-parameter changes
        self._sound_rebuild_timer = QTimer()
        self._sound_rebuild_timer.setSingleShot(True)
        self._sound_rebuild_timer.timeout.connect(self._prebuild_sounds)

    def _uncheck_binary_mask_mode(self):
        """Turn off the VideoWidget's binary/masked-view toggle.

        The phonotaxis VideoWidget control panel includes a checkbox
        that switches the live view between the plain camera image and
        a binary/masked (thresholded) view, and it defaults to ON. The
        paradigm should open showing the normal camera view instead.

        The checkbox is internal to VideoWidget and its attribute name
        is not part of a stable public API, so this locates it
        defensively: first by a few likely attribute names, then by
        scanning child QCheckBoxes for a binary/mask-related label. If
        nothing matches (e.g. a future VideoWidget without the toggle)
        this is a harmless no-op.
        """
        vw = self.video_widget
        # 1) Try common attribute names directly.
        for attr in ('binary_checkbox', 'binary_check', 'mask_checkbox',
                     'masked_checkbox', 'binary_mode_checkbox',
                     'show_binary_checkbox', 'binary_cb', 'mask_cb'):
            cb = getattr(vw, attr, None)
            if isinstance(cb, QCheckBox):
                cb.setChecked(False)
                return
        # 2) Fall back to scanning child checkboxes by their label text.
        try:
            for cb in vw.findChildren(QCheckBox):
                txt = (cb.text() or '').lower()
                if ('binary' in txt or 'mask' in txt
                        or 'threshold' in txt):
                    cb.setChecked(False)
                    return
        except Exception as e:
            print(f"[Paradigm] Could not reset binary/mask toggle: {e}")

    def _setup_parameters(self):
        """Create adjustable parameter widgets (click train only).

        NOTE: the parent paradigm's master ``sound_amplitude_spin`` is
        gone. With no warble there is only one sound to set a level
        for, and that is ``click_amp_spin`` in the click-train group.
        """
        self.params = gui.Container()

        # Trial timeout
        self.trial_timeout_spin = QDoubleSpinBox()
        self.trial_timeout_spin.setRange(0.5, 300.0)
        self.trial_timeout_spin.setDecimals(1)
        self.trial_timeout_spin.setSingleStep(0.5)
        self.trial_timeout_spin.setValue(10.0)
        self.trial_timeout_spin.setSuffix(" s")
        self.trial_timeout_spin.setToolTip(
            "If no valid poke stops the sound within this time, the\n"
            "trial ends automatically with no reward."
        )

        # Reward sound duration. Poke training reuses the inherited
        # post-poke sound machinery: the sound starts at the rewarded poke
        # and the trial ends when this duration has elapsed. The checkbox
        # is kept (always checked, not shown) because the saving code
        # reads it.
        self.post_poke_sound_checkbox = QCheckBox(
            "Continue sound after correct poke:"
        )
        self.post_poke_sound_checkbox.setChecked(True)
        self.post_poke_sound_spin = QDoubleSpinBox()
        self.post_poke_sound_spin.setRange(0.1, 30.0)
        self.post_poke_sound_spin.setDecimals(1)
        self.post_poke_sound_spin.setSingleStep(0.5)
        self.post_poke_sound_spin.setValue(DEFAULT_REWARD_SOUND_SEC)
        self.post_poke_sound_spin.setSuffix(" s")
        self.post_poke_sound_spin.setToolTip(
            "After a rewarded poke, the click train plays from that port\n"
            "for this duration. Other pokes during the sound are ignored."
        )

        # Which ports are blocked on the trial after a reward
        self.blocked_rule_combo = QComboBox()
        for rule_key, rule_label in BLOCKED_PORTS_RULES.items():
            self.blocked_rule_combo.addItem(rule_label, rule_key)
        self.blocked_rule_combo.setCurrentIndex(
            list(BLOCKED_PORTS_RULES).index(DEFAULT_BLOCKED_PORTS_RULE)
        )
        self.blocked_rule_combo.setToolTip(
            "Ports that cannot be rewarded on the next trial.\n"
            "Ports are labelled clockwise A-F, so the neighbors of A are\n"
            "F and B. All ports are allowed on the first trial.\n\n"
            "Cannot be changed once the session has started."
        )

        # ITI
        self.iti_spin = QDoubleSpinBox()
        self.iti_spin.setRange(0.0, 300.0)
        self.iti_spin.setDecimals(1)
        self.iti_spin.setSingleStep(0.5)
        self.iti_spin.setValue(0.0)
        self.iti_spin.setSuffix(" s")
        self.iti_spin.setToolTip(
            "Extra pause after the reward sound ends, during which pokes\n"
            "are ignored. Default 0 (the next reward is possible as soon\n"
            "as the sound ends)."
        )

        # Error ITI
        self.error_iti_checkbox = QCheckBox(
            "Error ITI (incorrect trials only):"
        )
        self.error_iti_checkbox.setChecked(False)
        self.error_iti_checkbox.setToolTip(
            "When enabled, an additional penalty ITI is imposed after\n"
            "every incorrect poke. The IZ tracker stays disabled for\n"
            "this duration, preventing the mouse from initiating a new\n"
            "trial.\n\nDefault is OFF — only the standard ITI is used."
        )
        self.error_iti_spin = QDoubleSpinBox()
        self.error_iti_spin.setRange(0.0, 300.0)
        self.error_iti_spin.setDecimals(1)
        self.error_iti_spin.setSingleStep(0.5)
        self.error_iti_spin.setValue(5.0)
        self.error_iti_spin.setSuffix(" s")
        self.error_iti_spin.setToolTip(
            "Duration of the penalty ITI applied after an incorrect\n"
            "poke. Default is 5 s. Has no effect when the checkbox is\n"
            "unchecked."
        )
        self.error_iti_spin.setEnabled(
            self.error_iti_checkbox.isChecked()
        )
        self.error_iti_checkbox.toggled.connect(
            self.error_iti_spin.setEnabled
        )

        # NOTE: the 3-port paradigm had a "Count pokes at inactive ports
        # as incorrect" toggle here. With all 6 ports active there are no
        # inactive ports, so the toggle is meaningless and has been
        # removed. (The corresponding HDF5/CSV fields are retained with
        # constant values so v4-era readers keep working — see _save_data.)

        # Shaping: whether a poke at a non-target port ends the trial.
        # Locked at session start (see _start_session).
        self.incorrect_ends_trial_checkbox = QCheckBox(
            "Incorrect poke ends trial"
        )
        self.incorrect_ends_trial_checkbox.setChecked(
            DEFAULT_INCORRECT_POKE_ENDS_TRIAL
        )
        self.incorrect_ends_trial_checkbox.setToolTip(
            "When checked, the first poke at a non-target port stops the\n"
            "sound and ends the trial as incorrect, with no reward\n"
            "(original task).\n\n"
            "When unchecked (shaping, default), pokes at non-target ports\n"
            "are logged but ignored: the sound continues and the mouse can\n"
            "still poke the target port for reward until the trial timeout.\n"
            "The Error ITI only applies when this is checked.\n\n"
            "Cannot be changed once the session has started."
        )

        # --- Combined task-parameters group ---
        self.combined_task_group = QGroupBox("Task parameters")
        combined_layout = QVBoxLayout()
        combined_layout.setSpacing(8)

        sub_style = (
            "QGroupBox { border: 1px solid #ccc; border-radius: 4px; "
            "margin-top: 8px; padding-top: 8px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 8px; "
            "padding: 0 4px; }"
        )

        # NOTE: the 3-port paradigm's speaker-set selector used to live
        # here, then moved into the "Set every session" box. There is no
        # selector at all now — all 6 ports are always active.

        # Poke training shows only the blocking rule, reward sound duration
        # and ITI. The trial timeout, error ITI and incorrect-poke controls
        # still exist (the saving code reads them) but are not shown.
        rule_wrap = QGroupBox("Blocked after reward")
        rule_wrap.setFlat(True)
        rule_wrap.setStyleSheet(sub_style)
        rule_vbox = QVBoxLayout()
        rule_vbox.setSpacing(4)
        rule_vbox.addWidget(self.blocked_rule_combo)
        rule_lbl = QLabel(
            "Any poke at an allowed port is rewarded. All ports are\n"
            "allowed on the first trial."
        )
        rule_lbl.setStyleSheet("color: #555;")
        rule_vbox.addWidget(rule_lbl)
        rule_wrap.setLayout(rule_vbox)
        combined_layout.addWidget(rule_wrap)

        sound_row_wrap = QGroupBox("Reward sound")
        sound_row_wrap.setFlat(True)
        sound_row_wrap.setStyleSheet(sub_style)
        sound_row = QHBoxLayout()
        sound_row.setSpacing(6)
        sound_row.addWidget(QLabel("Duration after poke:"))
        sound_row.addWidget(self.post_poke_sound_spin)
        sound_row.addStretch()
        sound_row_wrap.setLayout(sound_row)
        combined_layout.addWidget(sound_row_wrap)

        iti_row_wrap = QGroupBox("Inter-trial interval")
        iti_row_wrap.setFlat(True)
        iti_row_wrap.setStyleSheet(sub_style)
        iti_row = QHBoxLayout()
        iti_row.setSpacing(6)
        iti_row.addWidget(QLabel("Extra pause after sound:"))
        iti_row.addWidget(self.iti_spin)
        iti_row.addStretch()
        iti_row_wrap.setLayout(iti_row)
        combined_layout.addWidget(iti_row_wrap)

        self.combined_task_group.setLayout(combined_layout)

        # --- Broadband click-train sound parameter group ---
        # THE target sound in this paradigm. A train of brief broadband
        # (white-noise burst) clicks is played on the target port's
        # channel. Broadband clicks carry sharp wideband onset transients
        # with strong binaural and spectral localization cues (ITD / ILD /
        # HRTF notches) that a narrowband warble lacks.
        #
        # Unlike the parent paradigm there is no enable/disable toggle:
        # the click train is the only sound here, so disabling it would
        # leave every trial silent.
        self.click_params_group = QGroupBox(
            "Broadband Click Train (target sound)"
        )
        click_layout = QGridLayout()
        click_layout.setSpacing(6)
        crow = 0

        click_hdr = QLabel(
            "Played from the rewarded port's speaker after each\n"
            "rewarded poke, for the reward sound duration."
        )
        click_hdr.setStyleSheet("color: #555;")
        click_layout.addWidget(click_hdr, crow, 0, 1, 2)
        crow += 1

        self.click_rate_label = QLabel("Click rate:")
        click_layout.addWidget(self.click_rate_label, crow, 0)
        self.click_rate_spin = QDoubleSpinBox()
        self.click_rate_spin.setRange(1.0, 500.0)
        self.click_rate_spin.setDecimals(1)
        self.click_rate_spin.setSingleStep(5.0)
        self.click_rate_spin.setValue(20.0)
        self.click_rate_spin.setSuffix(" Hz")
        self.click_rate_spin.setToolTip(
            "Number of clicks per second. Default 20 Hz."
        )
        click_layout.addWidget(self.click_rate_spin, crow, 1)
        crow += 1

        self.click_amp_label = QLabel("Click amplitude:")
        click_layout.addWidget(self.click_amp_label, crow, 0)
        self.click_amp_spin = QDoubleSpinBox()
        self.click_amp_spin.setRange(0.0, 1.0)
        self.click_amp_spin.setDecimals(3)
        self.click_amp_spin.setSingleStep(0.01)
        self.click_amp_spin.setValue(0.180)
        self.click_amp_spin.setToolTip(
            "Peak amplitude (0-1) of each click, and the only level\n"
            "control in this paradigm. Default 0.180.\n\n"
            "This is much higher than the warble paradigm's 0.03 because\n"
            "a brief click at a low rate has a tiny duty cycle, so its\n"
            "RMS level is far below its peak. The two paradigms are NOT\n"
            "level-matched by these numbers — check with a calibrated\n"
            "microphone before comparing performance across them."
        )
        click_layout.addWidget(self.click_amp_spin, crow, 1)
        crow += 1

        self.click_dur_label = QLabel("Click duration:")
        click_layout.addWidget(self.click_dur_label, crow, 0)
        self.click_dur_spin = QDoubleSpinBox()
        self.click_dur_spin.setRange(0.05, 10.0)
        self.click_dur_spin.setDecimals(2)
        self.click_dur_spin.setSingleStep(0.1)
        self.click_dur_spin.setValue(0.50)
        self.click_dur_spin.setSuffix(" ms")
        self.click_dur_spin.setToolTip(
            "Duration of each individual click. Shorter clicks are more\n"
            "broadband and give sharper onset transients."
        )
        click_layout.addWidget(self.click_dur_spin, crow, 1)
        crow += 1

        # Optional gating. In the parent paradigm the click train could
        # be gated to the warble's segment/gap rhythm. There is no warble
        # to follow here, so the segment and gap durations get their own
        # controls. OFF by default = one continuous train.
        self.click_gate_checkbox = QCheckBox(
            "Pulse the train into on/off segments"
        )
        self.click_gate_checkbox.setChecked(False)
        self.click_gate_checkbox.setToolTip(
            "When unchecked (default) the click train runs continuously\n"
            "for the whole trial.\n\n"
            "When checked, the train is gated into on/off epochs using\n"
            "the segment and gap durations below — reproducing the\n"
            "rhythm the FM warble imposed in the parent paradigm, in\n"
            "case the envelope matters for the comparison."
        )
        click_layout.addWidget(self.click_gate_checkbox, crow, 0, 1, 2)
        crow += 1

        self.click_seg_dur_label = QLabel("Segment duration:")
        click_layout.addWidget(self.click_seg_dur_label, crow, 0)
        self.click_seg_dur_spin = QDoubleSpinBox()
        self.click_seg_dur_spin.setRange(0.01, 30.0)
        self.click_seg_dur_spin.setDecimals(2)
        self.click_seg_dur_spin.setSingleStep(0.05)
        self.click_seg_dur_spin.setValue(0.40)
        self.click_seg_dur_spin.setSuffix(" s")
        self.click_seg_dur_spin.setToolTip(
            "Length of each click-train burst before the gap.\n"
            "Only used when segment pulsing is enabled."
        )
        click_layout.addWidget(self.click_seg_dur_spin, crow, 1)
        crow += 1

        self.click_gap_label = QLabel("Gap between segments:")
        click_layout.addWidget(self.click_gap_label, crow, 0)
        self.click_gap_spin = QDoubleSpinBox()
        self.click_gap_spin.setRange(0.0, 10.0)
        self.click_gap_spin.setDecimals(2)
        self.click_gap_spin.setSingleStep(0.05)
        self.click_gap_spin.setValue(0.20)
        self.click_gap_spin.setSuffix(" s")
        self.click_gap_spin.setToolTip(
            "Silent gap between click-train bursts.\n"
            "Only used when segment pulsing is enabled."
        )
        click_layout.addWidget(self.click_gap_spin, crow, 1)
        crow += 1

        self.click_params_group.setLayout(click_layout)

        # Sync the greyed state of the segment controls to the gating
        # checkbox. Derived from the checkbox itself so the two can never
        # drift out of sync if the default changes.
        self._on_click_gate_toggled(
            self.click_gate_checkbox.isChecked()
        )

    def _on_click_gate_toggled(self, checked):
        """Enable/disable the segment/gap spins with the gating toggle."""
        for w in (self.click_seg_dur_label, self.click_seg_dur_spin,
                  self.click_gap_label, self.click_gap_spin):
            w.setEnabled(checked)

    def _setup_results_storage(self):
        """Initialize results container for HDF5 saving."""
        self.results = utils.EnumContainer()
        # Port triggered: 0=A, 1=B, 2=C, 3=D, 4=E, 5=F
        self.results.labels['port_triggered'] = bidict(PORT_ENUM_MAP)
        # Outcome: 0 = correct, 1 = incorrect, 2 = timeout
        self.results.labels['outcome'] = bidict(
            {'correct': 0, 'incorrect': 1, 'timeout': 2}
        )

        self.results['port_triggered'] = np.full(MAX_TRIALS, -1, dtype=int)
        self.results['outcome'] = np.full(MAX_TRIALS, -1, dtype=int)
        self.results['trial_onset_time'] = np.full(MAX_TRIALS, np.nan)
        self.results['sound_offset_time'] = np.full(MAX_TRIALS, np.nan)
        self.results['valve_close_time'] = np.full(MAX_TRIALS, np.nan)
        self.results['poke_detected'] = np.full(MAX_TRIALS, 0, dtype=int)
        self.results['poke_time'] = np.full(MAX_TRIALS, np.nan)
        self.results['latency_to_poke'] = np.full(MAX_TRIALS, np.nan)
        self.results['other_port_poke_detected'] = np.full(
            MAX_TRIALS, 0, dtype=int
        )
        self.results['other_port_poke_time'] = np.full(MAX_TRIALS, np.nan)
        self.results['trial_end_time'] = np.full(MAX_TRIALS, np.nan)
        self.results['reward_delivered'] = np.full(MAX_TRIALS, 0, dtype=int)
        self.results['dwell_duration'] = np.full(MAX_TRIALS, np.nan)
        # Previous trial's target port (-1 for trial 0).
        self.results['prev_port'] = np.full(MAX_TRIALS, -1, dtype=int)
        # Port the mouse poked on the previous trial (-1 for trial 0 or
        # after a timeout). Recorded, but does NOT gate trial selection
        # in the 6-port paradigm (it did in the 3-port one).
        self.results['prev_poked_port'] = np.full(MAX_TRIALS, -1, dtype=int)

    def _setup_layout(self):
        """Arrange all widgets in a three-column layout.

        Column 1 (left):   video + IZ config + pokes + manual reward
        Column 2 (middle): all adjustable session parameters
        Column 3 (right):  session performance, trial log, session notes
        """
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.addWidget(self.hw_status_label)

        columns = QHBoxLayout()

        # --- Column 1: Video + IZ + Pokes + Manual Reward ---
        col1_widget = QWidget()
        col1 = QVBoxLayout(col1_widget)
        col1.setContentsMargins(0, 0, 0, 0)
        col1.addWidget(self.video_widget, stretch=1)
        # IZ config not shown: poke training does not use the IZ.
        col1.addWidget(self.poke_indicators)
        col1.addWidget(self.manual_reward_panel)
        col1_widget.setMinimumWidth(640)
        col1_widget.setMaximumWidth(680)
        columns.addWidget(col1_widget, stretch=3)

        # --- Column 2 (middle): session parameters ---
        for w in [self.session_info, self.volume_cal,
                  self.combined_task_group,
                  self.click_params_group, self.data_paths]:
            pol = w.sizePolicy()
            pol.setHorizontalPolicy(QSizePolicy.Policy.Maximum)
            w.setSizePolicy(pol)

        self.start_btn.setMinimumWidth(170)
        sp = self.start_btn.sizePolicy()
        sp.setHorizontalPolicy(QSizePolicy.Policy.Maximum)
        sp.setVerticalPolicy(QSizePolicy.Policy.MinimumExpanding)
        self.start_btn.setSizePolicy(sp)

        # Top row: session info on left, Start button on right
        top_row_widget = QWidget()
        top_row = QHBoxLayout(top_row_widget)
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(6)
        top_row.addWidget(self.session_info)
        top_row.addWidget(self.start_btn)
        top_row.addStretch(1)

        col2_widget = QWidget()
        col2_layout = QVBoxLayout(col2_widget)
        col2_layout.setSpacing(6)
        col2_layout.addWidget(top_row_widget)
        col2_layout.addWidget(
            self.data_paths, alignment=Qt.AlignmentFlag.AlignLeft
        )
        col2_layout.addWidget(
            self.volume_cal, alignment=Qt.AlignmentFlag.AlignLeft
        )
        col2_layout.addWidget(
            self.combined_task_group, alignment=Qt.AlignmentFlag.AlignLeft
        )
        col2_layout.addWidget(
            self.click_params_group, alignment=Qt.AlignmentFlag.AlignLeft
        )
        col2_layout.addStretch()

        col2_scroll = QScrollArea()
        col2_scroll.setWidgetResizable(True)
        col2_scroll.setWidget(col2_widget)
        col2_scroll.setMinimumWidth(430)
        columns.addWidget(col2_scroll, stretch=4)

        # --- Column 3 (right): status + dashboard + trial log + notes ---
        col3_widget = QWidget()
        col3_layout = QVBoxLayout(col3_widget)
        col3_layout.setSpacing(6)
        col3_layout.addWidget(self.status_indicator)
        col3_layout.addWidget(self.dashboard)
        col3_layout.addWidget(self.trial_log, stretch=1)
        col3_layout.addWidget(self.notes_group)

        col3_scroll = QScrollArea()
        col3_scroll.setWidgetResizable(True)
        col3_scroll.setWidget(col3_widget)
        col3_scroll.setMinimumWidth(460)
        col3_scroll.setMaximumWidth(560)
        columns.addWidget(col3_scroll, stretch=1)

        main_layout.addLayout(columns)

    def _setup_sound(self):
        """Initialize sound player (not connected to state machine)."""
        self.sound_player = soundmodule.SoundPlayer()
        # Force sounddevice to use the configured output device
        try:
            import sounddevice as sd
            sd.default.device = config.SOUND_DEVICE
            self.sound_player.device = config.SOUND_DEVICE
        except Exception as e:
            print(f"[Sound] Could not pin output device: {e}")

    def _setup_video(self):
        """Initialize video thread for live display and recording."""
        # Live-view repaint throttle. COSMETIC ONLY: _display_frame still
        # runs IZ dwell detection, per-frame logging and journalling on
        # every acquired frame; this caps only how often the Qt widget
        # redraws, which keeps the GUI cheap while acquiring at 120 fps.
        # config.GUI_DISPLAY_MAX_FPS = 0 repaints on every frame.
        _gui_fps = float(getattr(config, 'GUI_DISPLAY_MAX_FPS', 0) or 0)
        self._display_min_interval = (1.0 / _gui_fps) if _gui_fps > 0 else 0.0
        self._last_paint_mono = 0.0
        if self._display_min_interval > 0:
            print(f"[Paradigm] Live view repaint capped at {_gui_fps:.0f} "
                  f"fps (tracking still runs on every frame)")

        if getattr(config, 'CAMERA_TYPE', 'webcam') == 'spinnaker':
            self.video_thread = videomodule.VideoThread(
                camera_index=getattr(config, 'SPINNAKER_CAMERA_INDEX', 0),
                mode='binary',
                tracking=True,
                acquisition_fps=getattr(
                    config, 'SPINNAKER_ACQUISITION_FPS', 60
                ),
                display_width=getattr(
                    config, 'SPINNAKER_DISPLAY_WIDTH', 640
                ),
                # Video-encoding settings (FFmpeg writer). Fallbacks keep
                # this working even if config.py predates these options.
                ffmpeg_path=getattr(config, 'FFMPEG_PATH', 'ffmpeg'),
                video_encoder=getattr(config, 'VIDEO_ENCODER', 'auto'),
                video_crf=getattr(config, 'VIDEO_CRF', 17),
                video_preset=getattr(config, 'VIDEO_PRESET', 'veryfast'),
                video_lossless=getattr(config, 'VIDEO_LOSSLESS', False),
                video_monochrome=getattr(
                    config, 'VIDEO_MONOCHROME', False
                ),
                video_fragment_sec=getattr(
                    config, 'VIDEO_FRAGMENT_SEC', 1.0
                ),
                write_queue_size=getattr(
                    config, 'VIDEO_WRITE_QUEUE_SIZE', 600
                ),
                # Exposure / gain / bandwidth. These gate whether the
                # requested frame rate is physically reachable (a camera
                # cannot expose longer than one frame period), so the video
                # module applies them BEFORE setting AcquisitionFrameRate.
                # The fallbacks keep an older config.py working.
                exposure_auto=getattr(
                    config, 'SPINNAKER_EXPOSURE_AUTO', 'off'
                ),
                exposure_time_us=getattr(
                    config, 'SPINNAKER_EXPOSURE_TIME_US', None
                ),
                exposure_headroom=getattr(
                    config, 'SPINNAKER_EXPOSURE_HEADROOM', 0.8
                ),
                gain_auto=getattr(
                    config, 'SPINNAKER_GAIN_AUTO', 'continuous'
                ),
                gain_db=getattr(config, 'SPINNAKER_GAIN_DB', None),
                gamma_enable=getattr(
                    config, 'SPINNAKER_GAMMA_ENABLE', None
                ),
                gamma=getattr(config, 'SPINNAKER_GAMMA', None),
                device_link_throughput=getattr(
                    config, 'SPINNAKER_DEVICE_LINK_THROUGHPUT_BPS', None
                ),
            )
        else:
            self.video_thread = videomodule.VideoThread(
                camera_index=config.CAMERA_INDEX,
                mode='binary',
                tracking=True,
            )
        self.video_thread.set_threshold(BLACK_THRESHOLD)
        self.video_thread.set_minarea(MIN_AREA)
        self.video_thread.set_circular_mask(DEFAULT_MASK)
        self.video_thread.frame_processed.connect(self._display_frame)
        self.video_thread.start()

        self.video_widget.connect_video_thread(self.video_thread)

    def _setup_hardware(self):
        """Initialize Arduino connection or emulator."""
        if config.HARDWARE_INTERFACE == 'arduino':
            self.arduino_thread = arduinomodule.ArduinoThread(debug=False)
            self.arduino_thread.arduino_ready.connect(
                self._on_arduino_ready
            )
            self.arduino_thread.arduino_error.connect(
                self._on_arduino_error
            )
            self.arduino_thread.threshold_crossed.connect(
                self._on_threshold_crossed
            )
            self.arduino_thread.start()
        else:
            self.arduino_thread = None
            self.arduino_connected = True
            self.hw_status_label.setText("Hardware: Emulator Mode")
            self.hw_status_label.setStyleSheet(
                "font-weight: bold; padding: 5px; "
                "background-color: #FF9800; "
                "border-radius: 4px; color: white;"
            )
            self.messagebar.collect(
                "Running in emulator mode (no hardware)"
            )

    def _connect_signals(self):
        """Connect widget signals to handlers."""
        self.volume_cal.calibration_changed.connect(
            self._on_calibration_changed
        )
        self.manual_reward_panel.reward_requested.connect(
            self._manual_reward
        )
        self.iz_config.radius_changed.connect(self._on_iz_radius_changed)
        self.iz_config.dwell_changed.connect(self._on_dwell_changed)

        # Re-evaluate whether the Start button may be enabled whenever
        # either required per-session entry (subject, trainer) changes.
        self.session_info.values_changed.connect(self._update_start_enabled)

        # Invalidate the sound cache whenever a stimulus parameter
        # changes. The trial timeout is in here too because it sets
        # the built waveform's length.
        for widget in (
            self.click_rate_spin, self.click_amp_spin,
            self.click_dur_spin, self.click_seg_dur_spin,
            self.click_gap_spin, self.trial_timeout_spin,
        ):
            widget.valueChanged.connect(self._schedule_sound_rebuild)
        self.click_gate_checkbox.toggled.connect(
            self._on_click_gate_toggled
        )
        self.click_gate_checkbox.toggled.connect(
            self._schedule_sound_rebuild
        )

    # ====================================================================
    # ARDUINO HANDLERS
    # ====================================================================

    def _on_arduino_ready(self):
        self.arduino_connected = True
        self.hw_status_label.setText("Arduino: Connected")
        self.hw_status_label.setStyleSheet(
            "font-weight: bold; padding: 5px; background-color: #4CAF50; "
            "color: white; border-radius: 4px;"
        )
        # Set thresholds on ALL 6 input pins — every port is active, and
        # out-of-trial pokes at any port are logged to the event log too.
        for input_name in ARDUINO_INPUTS:
            pin = config.INPUT_PINS[input_name]
            try:
                self.arduino_thread.set_threshold(pin, 0.60)
            except Exception as e:
                print(f"Warning: Could not set threshold for pin {pin}: {e}")
        self.messagebar.collect("Arduino connected and ready")

    def _on_arduino_error(self, msg):
        self.arduino_connected = False
        self.hw_status_label.setText(f"Arduino: Error — {msg}")
        self.hw_status_label.setStyleSheet(
            "font-weight: bold; padding: 5px; background-color: #f44336; "
            "color: white; border-radius: 4px;"
        )
        self.messagebar.collect(f"Arduino error: {msg}")

    def _on_threshold_crossed(self, pin_num, value, is_rising):
        """Handle IR beam-break events from Arduino.

        Every poke at any of the 6 ports is logged to the session-wide
        event log and (during a trial) to PokeTracker.

        With all 6 ports active there are only two outcome branches:
          - Target port: reward + sound stop/extend + trial end.
          - Any other port (5 of them): sound stops, trial ends as
            incorrect, no reward.
        The 3-port paradigm's third branch (inactive-port pokes, which
        were optionally logged-only) no longer exists.
        """
        if not self.session_running:
            return

        # Determine which port this pin belongs to
        port_key = None
        for key, info in PORT_MAP.items():
            if config.INPUT_PINS.get(info['input']) == pin_num:
                port_key = key
                break
        if port_key is None:
            return

        # Determine if this is a poke-in event. The original 2-port
        # paradigm noted both branches of the ARDUINO_INPUTS_INVERTED
        # logic resolved to "falling edge = beam broken = poke" for
        # typical pull-up wiring; we keep the same behavior here.
        if hasattr(config, 'ARDUINO_INPUTS_INVERTED') and \
                config.ARDUINO_INPUTS_INVERTED:
            poke_in = not is_rising
        else:
            poke_in = not is_rising

        if not poke_in:
            return

        now = time.time()

        # Flash indicator (all 6 are visible).
        self.poke_indicators.flash(port_key)

        # ---- ALWAYS log the poke to the session-wide event log ----
        # This captures in-trial pokes, between-trial pokes,
        # post-poke-extension pokes, and repeats.
        if self.session_start_time is not None:
            event_name = f'poke_{port_key}'
            self.event_log.log(
                event_name,
                now - self.session_start_time,
                port=port_key,
                trial_num=(self.current_trial if self.trial_active
                           else -1),
            )

        # Poke training. A trial is active only while the reward sound
        # plays: pokes then are recorded but ignored.
        if self.trial_active:
            self.poke_tracker.on_poke(port_key, now)
            return

        # Pokes during the optional extra pause (ITI) are ignored.
        if self.in_iti:
            return

        if port_key in self._blocked_ports:
            self._n_blocked_pokes += 1
            self.messagebar.collect(
                f"Poke at blocked Port {port_key} — no reward"
            )
            return

        self._start_reward_trial(port_key, now)

    # ====================================================================
    # VIDEO / IZ DWELL LOGIC
    # ====================================================================

    def _display_frame(self, timestamp, frame, points, contour=None):
        """Called on every processed frame. Handles IZ dwell detection
        and draws the IZ overlay before passing the frame to the widget."""
        centroid = None
        if points is not None and len(points) > 0:
            try:
                cx = float(points[0][0])
                cy = float(points[0][1])
                if cx >= 0 and cy >= 0:
                    centroid = (cx, cy)
            except (TypeError, IndexError):
                centroid = None

        trigger_now = False
        dwell_info = self.iz_tracker.update(centroid)
        if dwell_info['trigger']:
            trigger_now = True

        # Draw the IZ overlay and repaint the live view. This is the only
        # cosmetic part of this method -- everything below runs on every
        # frame regardless -- so the repaint is throttled to
        # config.GUI_DISPLAY_MAX_FPS. Skipping a repaint costs nothing but
        # a slightly staler picture (and a slightly sparser centroid
        # trail, which is drawn by the widget).
        _min_interval = getattr(self, '_display_min_interval', 0.0)
        _now_paint = time.monotonic()
        if (_min_interval <= 0.0
                or (_now_paint - getattr(self, '_last_paint_mono', 0.0))
                >= _min_interval):
            self._last_paint_mono = _now_paint
            frame_out = self._draw_iz_overlay(frame, dwell_info)
            self.video_widget.display_frame(frame_out, points,
                                            contour=contour)

        # --- Per-frame state recording (session-only) ---------------------
        if self.session_running and self.session_start_time is not None:
            if self.trial_active:
                phase = ('post_poke_sound' if self._in_post_poke_sound
                         else 'trial_active')
            elif self.in_iti:
                phase = 'iti'
            else:
                phase = 'waiting_for_poke'

            self.frame_tracker.record(
                timestamp=timestamp,
                phase_name=phase,
                trial_num=(self.current_trial
                           if (self.trial_active or self.in_iti) else -1),
                in_iz=dwell_info['in_zone'],
                dwell_sec=dwell_info['dwell_sec'],
                centroid=centroid,
            )

            # Mirror this per-frame record to the crash-safe journal.
            if self._session_journal is not None:
                self._session_journal.log_frame({
                    'ts': float(timestamp),
                    'phase': phase,
                    'trial_num': (self.current_trial
                                  if (self.trial_active or self.in_iti)
                                  else -1),
                    'in_iz': bool(dwell_info['in_zone']),
                    'dwell_sec': float(dwell_info['dwell_sec']),
                    'cx': (float(centroid[0])
                           if centroid is not None else None),
                    'cy': (float(centroid[1])
                           if centroid is not None else None),
                })

            # Log dwell enter/exit edge events
            if self.iz_tracker.last_transition in ('enter', 'exit'):
                ev = ('dwell_enter'
                      if self.iz_tracker.last_transition == 'enter'
                      else 'dwell_exit')
                self.event_log.log(
                    ev, timestamp - self.session_start_time,
                    trial_num=self.current_trial,
                )

        # --- IZ dwell measurement ------------------------------------
        # While a trial is active, keep measuring the continuous IZ
        # bout that triggered it: total time in the zone from entry
        # (the anchor, set in _trigger_trial_from_iz) until the mouse
        # leaves. A brief dropout grace is applied so a momentary
        # tracking glitch does not prematurely freeze the measurement,
        # mirroring the IZ tracker's own grace behavior. The IZ tracker
        # is disabled during a trial, so the zone test is done directly
        # via point_in_zone(). ``current_trial_dwell`` is updated live
        # so a value is available even if the trial ends (poke/timeout)
        # before the mouse leaves the zone.
        if (self.trial_active
                and self._iz_dwell_anchor is not None
                and not self._iz_dwell_left):
            now_t = time.time()
            in_zone_now = self.iz_tracker.point_in_zone(centroid)
            grace = getattr(self.iz_tracker, 'dropout_grace_sec', 0.12)
            if in_zone_now:
                # Confirmed in the IZ — advance the dwell and remember
                # this as the most recent in-zone moment.
                self._iz_dwell_last_in = now_t
                self.current_trial_dwell = now_t - self._iz_dwell_anchor
            else:
                # Out of the zone this frame. Could be a real exit or a
                # brief tracking dropout — only freeze the measurement
                # once the mouse has been out longer than the grace
                # window. The frozen value counts up to the last
                # confirmed in-zone moment, not the exit gap.
                if (self._iz_dwell_last_in is not None
                        and (now_t - self._iz_dwell_last_in) > grace):
                    self.current_trial_dwell = (
                        self._iz_dwell_last_in - self._iz_dwell_anchor
                    )
                    self._iz_dwell_left = True
                # else: within grace — leave current_trial_dwell as-is
                # (last in-zone value) and wait to see if the mouse
                # comes back.

        # Update IZ live dwell readout + status indicator (throttled)
        now_mono = time.monotonic()
        if now_mono - self._last_iz_ui_update > 0.1:
            self._last_iz_ui_update = now_mono
            req = (self.iz_tracker.required_sec
                   if hasattr(self.iz_tracker, 'required_sec') else 0)
            self.iz_config.set_live_dwell(
                dwell_info['in_zone'], dwell_info['dwell_sec'], req
            )
            if (self.session_running and not self.trial_active
                    and not self.in_iti):
                self.status_indicator.set_waiting_for_poke(
                    self._blocked_ports, self.current_trial
                )
        # Poke training: the IZ never starts trials (the tracker is never
        # enabled, so trigger_now is always False).

    def _draw_iz_overlay(self, frame, dwell_info):
        """Draw the IZ circle on the (grayscale) display frame."""
        # Poke training: no IZ, nothing to draw.
        if cv2 is None or frame is None or self.iz_tracker.radius <= 0:
            return frame
        try:
            out = frame
            cx = int(self.iz_tracker.cx)
            cy = int(self.iz_tracker.cy)
            r = int(self.iz_tracker.radius)
            if self.trial_active:
                intensity = 100
                thickness = 1
            elif self.in_iti:
                intensity = 140
                thickness = 1
            elif dwell_info.get('in_zone'):
                intensity = 255
                thickness = 3
            else:
                intensity = 220
                thickness = 2
            cv2.circle(out, (cx, cy), r, intensity, thickness)
            cv2.drawMarker(out, (cx, cy), intensity,
                           markerType=cv2.MARKER_CROSS,
                           markerSize=8, thickness=1)
            return out
        except Exception:
            return frame

    def _on_iz_radius_changed(self, radius):
        self.iz_tracker.set_zone(DEFAULT_MASK[0], DEFAULT_MASK[1],
                                 float(radius))

    def _on_dwell_changed(self, dwell_sec):
        self.iz_tracker.set_required_sec(float(dwell_sec))

    # ====================================================================
    # CALIBRATION / PATHS / SPEAKER SET
    # ====================================================================

    def _on_calibration_changed(self, vols: dict):
        """``vols`` is {port_key: µL_per_open} for all 6 ports."""
        self.dashboard.set_volume_calibration(vols)

    def _on_paths_changed(self, data_path, video_path):
        """Update data/video paths (takes effect at next session start)."""
        if data_path:
            try:
                config.DATA_PATH = data_path
            except Exception:
                pass
            for attr in ('datadir', 'data_dir', 'dataDir'):
                if hasattr(self.savedata_widget, attr):
                    try:
                        setattr(self.savedata_widget, attr, data_path)
                    except Exception:
                        pass
        if video_path:
            try:
                config.VIDEO_PATH = video_path
            except Exception:
                pass
        self.messagebar.collect(
            f"Save locations updated — data: {data_path}, "
            f"video: {video_path}"
        )

    def _apply_active_ports(self):
        """Push the fixed 6-port active set into every per-port widget.

        The 3-port paradigm re-ran this whenever the ACE/BDF radio
        buttons changed. Here the active set never changes, so this runs
        exactly once, at startup.
        """
        self._active_ports = ACTIVE_PORTS
        self.poke_indicators.set_active_ports(ACTIVE_PORTS)
        self.manual_reward_panel.set_active_ports(ACTIVE_PORTS)
        self.volume_cal.set_active_ports(ACTIVE_PORTS)
        self.dashboard.set_active_ports(ACTIVE_PORTS)
        self.messagebar.collect(
            f"Active ports: {' / '.join(ACTIVE_PORTS)} (all 6) — "
            f"chance = {CHANCE_LEVEL_PCT:.1f}%"
        )

    # ====================================================================
    # DUPLICATE-SESSION HANDLING
    # ====================================================================

    def _find_existing_session_files(self, subject, date_str):
        """Return paths of existing data/video files for this subject+date."""
        matches = []
        data_path = self.data_paths.get_data_path()
        video_path = self.data_paths.get_video_path()
        data_subdir = os.path.join(data_path, subject)
        video_subdir = os.path.join(video_path, subject)
        prefix = f"{subject}_{PARADIGM_NAME}_{date_str}"

        for root_dir, exts in [
            (data_subdir, ('.h5',)),
            (video_subdir, ('.mp4', '.avi', '.mov')),
        ]:
            if not os.path.isdir(root_dir):
                continue
            try:
                for fn in os.listdir(root_dir):
                    if fn.startswith(prefix) and fn.endswith(exts):
                        matches.append(os.path.join(root_dir, fn))
            except Exception:
                pass
        return matches

    def _prompt_duplicate_session(self, subject, date_str, existing_files):
        """Ask whether to overwrite or save as new. Returns 'overwrite' |
        'new' | 'cancel'."""
        file_list_text = "\n".join(
            f"  • {os.path.basename(f)}" for f in existing_files
        )
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Existing session detected")
        box.setText(
            f"A session for subject '{subject}' has already been run "
            f"today ({date_str})."
        )
        box.setInformativeText(
            "Existing files:\n"
            f"{file_list_text}\n\n"
            "How would you like to proceed?\n\n"
            "• Overwrite previous session — delete the existing data "
            "and video files for this subject/date and start fresh.\n"
            "• Save as new session — keep the existing files and save "
            "this run with an additional suffix.\n"
            "• Cancel — abort starting the session."
        )
        overwrite_btn = box.addButton(
            "Overwrite previous session",
            QMessageBox.ButtonRole.DestructiveRole
        )
        new_btn = box.addButton(
            "Save as new session", QMessageBox.ButtonRole.AcceptRole
        )
        cancel_btn = box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(new_btn)
        box.exec()
        clicked = box.clickedButton()
        if clicked is overwrite_btn:
            return 'overwrite'
        if clicked is new_btn:
            return 'new'
        return 'cancel'

    def _delete_files(self, paths):
        for p in paths:
            try:
                os.remove(p)
                self.messagebar.collect(f"Deleted {os.path.basename(p)}")
            except Exception as e:
                print(f"Warning: could not delete {p}: {e}")

    # ====================================================================
    # SESSION CONTROL
    # ====================================================================

    def _toggle_session(self):
        if not self.session_running:
            self._start_session()
        else:
            self._stop_session()

    def _update_start_enabled(self):
        """Enable Start only when Subject and Trainer are filled in.

        Leaves the button alone once a session is running or has ended,
        so it never gets re-enabled out from under the "Stop Session" /
        "Session Ended" states.
        """
        if self.session_running or self._session_finished:
            return
        self.start_btn.setEnabled(self.session_info.is_ready())

    def _validate_session(self):
        subject = self.session_info.get_value('subject').strip()
        trainer = self.session_info.get_value('trainer').strip()
        missing = []
        if not subject:
            missing.append("Subject ID")
        if not trainer:
            missing.append("Trainer initials")
        if missing:
            QMessageBox.warning(
                self, "Missing Information",
                "Please fill in:\n\n• " + "\n• ".join(missing)
            )
            return False
        return True

    def _start_session(self):
        if not self._validate_session():
            return

        # Apply current paths into config
        data_path = self.data_paths.get_data_path()
        video_path = self.data_paths.get_video_path()
        try:
            config.DATA_PATH = data_path
            config.VIDEO_PATH = video_path
        except Exception:
            pass
        for attr in ('datadir', 'data_dir', 'dataDir'):
            if hasattr(self.savedata_widget, attr):
                try:
                    setattr(self.savedata_widget, attr, data_path)
                except Exception:
                    pass

        # Duplicate-session check
        subject = self.session_info.get_value('subject')
        date_str = time.strftime('%Y%m%d')
        existing = self._find_existing_session_files(subject, date_str)
        self._overwrite_existing = False
        if existing:
            choice = self._prompt_duplicate_session(
                subject, date_str, existing
            )
            if choice == 'cancel':
                self.messagebar.collect("Session start cancelled")
                return
            if choice == 'overwrite':
                self._delete_files(existing)
                self._overwrite_existing = True
                self.messagebar.collect(
                    f"Previous session for {subject} on {date_str} "
                    "deleted — overwriting"
                )
            else:
                self.messagebar.collect(
                    f"Saving as new session for {subject} on {date_str} "
                    "(existing files kept)"
                )

        # Active set is fixed at all 6 ports; nothing to lock in.
        self._active_ports = ACTIVE_PORTS
        self._last_poked_port = None
        self._trial_ended_by_port = None

        self.session_running = True
        self.session_start_time = time.time()
        self.session_start_epoch = self.session_start_time
        self.session_end_epoch = None
        self.current_trial = 0
        self.data_saved = False
        self.trial_data = []
        self.current_data_filepath = None
        self.current_video_filepath = None

        # Reset results arrays
        self._setup_results_storage()

        # Reset event log + frame tracker for this session only
        self.event_log.clear()
        self.frame_tracker.clear()
        self._manual_reward_log = []

        # Clear video thread's accumulated tracking data
        if hasattr(self.video_thread, 'clear_tracking'):
            try:
                self.video_thread.clear_tracking()
            except Exception as e:
                print(f"Warning: could not clear video tracking buffers: {e}")

        # Poke training: IZ not used. All ports allowed on the first trial.
        self._blocked_ports = ()
        self._n_blocked_pokes = 0
        self._last_reward_time = None
        self._blocked_rule = self.blocked_rule_combo.currentData()

        # Configure dashboard
        session_dur = self.session_info.get_value('maxSessionDuration')
        self.dashboard.reset()
        self.dashboard.set_active_ports(self._active_ports)
        self.dashboard.set_session_duration(session_dur)
        self._on_calibration_changed(self.volume_cal.get_values())

        # Update UI
        self.start_btn.setText("Stop Session")
        self.start_btn.setStyleSheet(STYLE_BTN_STOP)
        self.status_indicator.set_waiting_for_poke(self._blocked_ports, 0)
        self.session_info.setEnabled(False)
        self.data_paths.setEnabled(False)
        self.incorrect_ends_trial_checkbox.setEnabled(False)
        self.blocked_rule_combo.setEnabled(False)

        # Start timer
        self.dashboard_timer.start(1000)  # 1 s (dashboard, clock, session end)

        # Start video recording
        video_dir = os.path.join(video_path, subject)
        os.makedirs(video_dir, exist_ok=True)
        video_ext = '.mp4'

        suffix_ord = ord('a')
        while True:
            suffix = (chr(suffix_ord) if suffix_ord <= ord('z')
                      else str(suffix_ord - ord('z')))
            video_fn = (f"{subject}_{PARADIGM_NAME}_"
                        f"{date_str}{suffix}{video_ext}")
            video_fp = os.path.join(video_dir, video_fn)
            if not os.path.exists(video_fp):
                break
            suffix_ord += 1

        self.current_video_filepath = video_fp
        self.video_thread.start_recording(video_fp)

        # (Poke training: IZ dwell detection is NOT enabled.)

        # Pre-generate sounds for the active ports
        self._prebuild_sounds()

        # ---- Open the crash-safe session journal -----------------------
        # An append-only JSONL journal is written alongside the data file as
        # the session runs. If the machine crashes before the HDF5 is saved,
        # recover_session.py rebuilds the session from this journal.
        try:
            journal_dir = os.path.join(data_path, subject)
            os.makedirs(journal_dir, exist_ok=True)
            journal_path = make_journal_path(
                journal_dir, subject, PARADIGM_NAME)
            self._session_journal = SessionJournal(journal_path)
            self._session_journal.start()
            self.event_log._journal = self._session_journal
            self._session_journal.log_meta({
                'paradigm_name': PARADIGM_NAME,
                'paradigm_version': PARADIGM_VERSION,
                'schema_version': SCHEMA_VERSION,
                'subject': subject,
                'trainer': self.session_info.get_value('trainer'),
                'date_str': date_str,
                'session_start_epoch': float(self.session_start_epoch),
                'session_start_iso': datetime.fromtimestamp(
                    self.session_start_epoch).isoformat(timespec='seconds'),
                # `speaker_set` key name kept for recover_session.py
                # compatibility; its value is now always 'ABCDEF'.
                'speaker_set': ACTIVE_SET_NAME,
                'active_ports': list(self._active_ports),
                'n_active_ports': int(N_ACTIVE_PORTS),
                'trial_selection_rule': 'poke_training',
                'task_type': 'poke_training',
                'blocked_ports_rule': self._blocked_rule,
                'video_filepath': self.current_video_filepath or '',
                'phase_enum_map': PHASES,
            })
            self.messagebar.collect(
                f"Crash-safe journal: {os.path.basename(journal_path)}")
        except Exception as e:
            print(f"Warning: could not start session journal: {e}")
            self._session_journal = None

        # Log session_start (t=0 by definition)
        self.event_log.log('session_start', 0.0, trial_num=-1)

        self.messagebar.collect(
            f"Session started — poke training, blocked after reward: "
            f"{BLOCKED_PORTS_RULES[self._blocked_rule]}"
        )

    def _stop_session(self):
        if not self.session_running:
            return

        # Close any active trial
        if self.trial_active:
            if self.current_trial_outcome is None:
                self.current_trial_outcome = 'timeout'
            self._finalize_current_trial()

        # Log session_end before flipping the flag
        if self.session_start_time is not None:
            end_rel = time.time() - self.session_start_time
            self.event_log.log('session_end', end_rel, trial_num=-1)
        self.session_end_epoch = time.time()

        self.session_running = False
        self._session_finished = True
        self.trial_active = False
        self.in_iti = False
        self._current_iti_is_error = False
        self.iz_tracker.disable()
        self.dashboard_timer.stop()
        self.iti_timer.stop()
        self.trial_timeout_timer.stop()
        self.post_poke_sound_timer.stop()
        self._sound_rebuild_timer.stop()
        self._sounds_prebuilt = False

        # Stop sound
        self._stop_sound()

        # Stop video recording
        try:
            self.video_thread.stop_recording()
        except Exception as e:
            print(f"Warning: Error stopping video recording: {e}")

        # Update UI
        self.start_btn.setText("Session Ended")
        self.start_btn.setEnabled(False)
        self.status_indicator.set_ended()

        # Save data
        if not self.data_saved:
            try:
                self._save_data()
            except Exception as e:
                print(f"ERROR saving data: {e}")
                self.messagebar.collect(f"Error saving data: {e}")
                QMessageBox.warning(
                    self, "Save Error",
                    f"Could not save session data:\n\n{e}\n\n"
                    "You can try saving manually with the Save button."
                )

        # Finalise (or preserve) the crash-safe journal
        if self._session_journal is not None:
            try:
                if self.data_saved:
                    # HDF5 written OK -> rename the journal to *.done so the
                    # recovery tool knows this session is already saved.
                    self._session_journal.finalize_ok()
                else:
                    # Save failed -> keep the journal (no .done marker) so the
                    # session can be rebuilt later with recover_session.py.
                    self._session_journal.log_note(
                        'HDF5 save failed -- journal kept for recovery')
                    self._session_journal.close()
            except Exception as e:
                print(f"Warning: journal finalisation issue: {e}")
            self.event_log._journal = None
            self._session_journal = None

        # Remux the recorded video to a normal, indexed MP4.
        # During recording the file is a *fragmented* MP4 so it survives a
        # crash, but fragmented files show no duration and can't be scrubbed
        # in players / Explorer. Now that the session has saved successfully,
        # convert it in-place to a standard indexed MP4. This is a stream
        # copy (no re-encode) -> fast and lossless.
        if self.data_saved and self.current_video_filepath:
            try:
                video_mp4 = os.path.splitext(
                    self.current_video_filepath)[0] + '.mp4'
                remux = getattr(videomodule, 'remux_to_indexed', None)
                if remux is not None and os.path.isfile(video_mp4):
                    self.messagebar.collect("Finalising video file...")
                    ok = remux(
                        video_mp4,
                        ffmpeg_path=getattr(config, 'FFMPEG_PATH', 'ffmpeg'),
                        replace=True,
                    )
                    if ok:
                        self.messagebar.collect(
                            "Video finalised (indexed MP4).")
                    else:
                        self.messagebar.collect(
                            "Video left as crash-safe fragmented MP4 "
                            "(remux skipped -- see console).")
            except Exception as e:
                print(f"Warning: video remux step failed: {e}")

        # Append CSV summary
        try:
            self._append_csv_summary()
        except Exception as e:
            print(f"ERROR appending CSV summary: {e}")
            self.messagebar.collect(f"CSV summary error: {e}")

        # Show summary dialog
        try:
            self._show_summary_dialog()
        except Exception as e:
            print(f"ERROR showing summary dialog: {e}")
            self.messagebar.collect(f"Summary dialog error: {e}")

        self.messagebar.collect(
            "Session complete — close GUI to start new session"
        )

    def _update_timer_display(self):
        if not self.session_running or not self.session_start_time:
            return
        elapsed = time.time() - self.session_start_time
        self.dashboard.update_timer(elapsed)

        if self.in_iti:
            remaining = max(0.0, self._iti_end_time - time.time())
            if self._current_iti_is_error:
                self.status_indicator.set_error_iti(
                    remaining, self.current_trial
                )
            else:
                self.status_indicator.set_iti(
                    remaining, self.current_trial
                )

        # Auto-end session
        session_dur = self.session_info.get_value('maxSessionDuration')
        if elapsed >= session_dur:
            self.messagebar.collect(
                "Session time limit reached — ending session"
            )
            self._stop_session()

    # ====================================================================
    # TRIAL LOGIC
    # ====================================================================

    def _choose_next_port(self) -> str:
        """Pick the target port for the next trial.

        Independent, uniformly-random draw over ALL 6 ports on every
        trial. Nothing is excluded:
          - the previous trial's TARGET port is eligible again
          - the port the mouse just POKED is eligible again
        so an immediate repeat occurs with p = 1/6 (~17% of trials), and
        runs of 2+ on the same port will occur. This is intentional — it
        removes the 3-port paradigm's no-repeat-based-on-poke rule, which
        made the target partially predictable from the mouse's own last
        action.

        ``self._last_poked_port`` is still maintained and saved (see
        ``prev_poked_port``) but deliberately plays no part here.

        Consequences worth remembering when analysing these sessions:
          - Chance performance is 1/6 = 16.7%, not 1/3 = 33.3%.
          - Because targets are i.i.d., per-port trial counts will be
            unbalanced within a session by sampling noise alone (for
            n trials, each port's count is ~Binomial(n, 1/6)). Do not
            read a per-port count imbalance as a bug. The dashboard's
            Trial Balance readout judges deviation relative to the
            expected 16.7% share and stays grey until enough trials
            have accrued.
          - A repeat trial arrives with the mouse already next to the
            (previously rewarded) target. If that turns out to inflate
            accuracy on repeat trials, it can be handled at analysis
            time by conditioning on ``prev_poked_port``, or by adding a
            max-run-length cap / block-balanced draw here later.
        """
        return str(np.random.choice(self._active_ports))

    def _start_reward_trial(self, port_key, poke_time):
        """Poke training: a poke at an allowed port starts a trial that is
        rewarded immediately (valve + sound from that port). The trial
        ends when the reward sound ends (post_poke_sound_timer)."""
        if (not self.session_running or self.trial_active
                or self.in_iti):
            return

        trial_num = self.current_trial

        if trial_num >= MAX_TRIALS:
            self.messagebar.collect("Reached MAX_TRIALS — stopping")
            self._stop_session()
            return

        onset_time = poke_time
        onset_relative = onset_time - self.session_start_time

        # Blocking bookkeeping for this trial, then block for the next one
        self._current_trial_blocked = tuple(self._blocked_ports)
        self._current_trial_n_blocked = self._n_blocked_pokes
        self._current_trial_since_prev = (
            onset_time - self._last_reward_time
            if self._last_reward_time is not None else None
        )
        self._n_blocked_pokes = 0
        self._last_reward_time = onset_time
        self._blocked_ports = blocked_ports_after_reward(
            port_key, self._blocked_rule
        )

        self.trial_active = True
        self._in_post_poke_sound = False
        self.reward_delivered_this_trial = False
        self.incorrect_poke_stopped_sound = False
        self.current_trial_port = port_key
        self.current_trial_outcome = None
        self._trial_ended_by_port = None
        # Anchor the IZ-dwell measurement at the moment the mouse
        # ENTERED the zone for the bout that triggered this trial — not
        # at the trigger itself — so the reported dwell covers the full
        # continuous in-zone bout (pre-trigger hold + post-trigger
        # linger) and is always >= the dwell requirement. The tracker's
        # dwell_start_time still holds that entry time at this point
        # (disable() does not clear it); fall back to onset_time only if
        # it is somehow unavailable. The measurement is frozen the first
        # frame the centroid leaves the IZ (see _display_frame); the
        # final value is written to current_trial_dwell at finalize.
        # Poke training: no IZ, so no dwell measurement (anchor None).
        self._iz_dwell_anchor = None
        # Mouse is in the IZ at trigger, so seed last-in time to now.
        self._iz_dwell_last_in = onset_time
        self._iz_dwell_left = False
        self.current_trial_dwell = np.nan

        # Start poke tracking
        self.poke_tracker.start_trial(
            port_key, onset_time, self._active_ports
        )
        # The poke that started the trial is the (rewarded) target poke
        self.poke_tracker.on_poke(port_key, onset_time)

        # Record trial onset in legacy per-trial arrays
        self.results['port_triggered'][trial_num] = \
            self.results.labels['port_triggered'][port_key]
        self.results['trial_onset_time'][trial_num] = onset_relative
        # dwell_duration is finalised in _finalize_current_trial once
        # the post-trigger IZ dwell is known; leave it at the default
        # (NaN) for now.
        # `prev_port`: the previous trial's TARGET port, derived from the
        # prior row of port_triggered (-1 on trial 0).
        if trial_num > 0:
            prev_target_int = int(
                self.results['port_triggered'][trial_num - 1]
            )
        else:
            prev_target_int = -1
        self.results['prev_port'][trial_num] = prev_target_int
        # `prev_poked_port`: the port the mouse poked on the previous
        # trial (-1 for the first trial of the session AND for trials
        # that follow a timeout).
        #
        # In the 3-port paradigm this GATED trial selection (the
        # no-repeat rule). Here it gates nothing — the target above was
        # drawn uniformly at random from all 6 — but it is still recorded
        # because it stays a useful regressor (win-stay/lose-shift,
        # perseveration, previous-port effects on the approach path).
        prev_poked_int = (PORT_ENUM_MAP.get(self._last_poked_port, -1)
                          if self._last_poked_port is not None else -1)
        self.results['prev_poked_port'][trial_num] = prev_poked_int

        # Log trial_start
        self.event_log.log('trial_start', onset_relative,
                           port=port_key, trial_num=trial_num)

        # Play sound
        self._play_sound(port_key)

        # Update status
        # Reward immediately
        self.reward_delivered_this_trial = True
        self._open_valve(port_key)
        self.current_trial_outcome = 'correct'
        self._trial_ended_by_port = port_key

        # The trial ends when the reward sound ends (no timeout)
        sound_ms = int(self.post_poke_sound_spin.value() * 1000)
        self._in_post_poke_sound = True
        self.event_log.log('post_poke_sound_start', onset_relative,
                           port=port_key, trial_num=trial_num)
        self.post_poke_sound_timer.start(sound_ms)

        self.status_indicator.set_active(port_key, trial_num + 1)
        self.messagebar.collect(
            f"Reward {trial_num + 1} at Port {port_key} — next blocked: "
            f"{', '.join(self._blocked_ports)}"
        )

    # ====================================================================
    # SOUND
    # ====================================================================

    def _prebuild_sounds(self):
        """Pre-generate the click train for each of the 6 ports and load
        it into the sound player so ``_play_sound`` is a near-instant
        call.

        Each Sound object is built with ``N_AUDIO_CHANNELS`` so that
        every port's channel (0-5, one per port) is addressable.

        COST NOTE (changed from the 3-port paradigm): this now builds 6
        waveforms rather than 3, each spanning max(60 s, timeout + 10 s)
        across 6 audio channels. That is a substantial numpy workload on
        the GUI thread. The 3-port paradigm unconditionally invalidated
        and rebuilt the cache after EVERY trial; at 6 ports that doubles
        the per-trial cost for no benefit, so the post-trial rebuild is
        now conditional on the cache actually being stale (see
        ``_finalize_trial_and_advance``). A stale cache only ever arises
        from a sound-parameter change or a failed build, both of which
        already schedule their own rebuild.

        Called:
          - once synchronously at session start
          - via QTimer 100 ms after a trial closes, ONLY if the cache is
            stale (parameter change or previous build failure)
          - via debounce timer 200 ms after any sound-parameter change
        """
        self._sounds_prebuilt = False
        t_build0 = time.perf_counter()
        try:
            duration = max(
                60.0, float(self.trial_timeout_spin.value()) + 10.0
            )
            # Build one Sound per port (6 total — every port is a
            # possible target on every trial). The click train is the
            # only component: no FM warble is added.
            for port_key in self._active_ports:
                channel = PORT_MAP[port_key]['channel']
                sound_id = PORT_TO_SOUND_ID[port_key]
                sound = soundmodule.Sound(
                    duration=duration, srate=SAMPLING_RATE,
                    nchannels=N_AUDIO_CHANNELS,
                )
                self._add_click_train(sound, channel)
                self.sound_player.set_sound(sound_id, sound)

            self._sounds_prebuilt = True
            dt = time.perf_counter() - t_build0
            print(f"[Sound prebuild] Built {len(self._active_ports)} "
                  f"sounds ({duration:.0f}s x {N_AUDIO_CHANNELS}ch) in "
                  f"{dt:.2f}s")
            if dt > 1.0:
                # Worth surfacing: this runs on the GUI thread, so a slow
                # build stalls the live video/IZ tracking while it runs.
                self.messagebar.collect(
                    f"Note: sound prebuild took {dt:.1f}s "
                    "(consider a shorter trial timeout)"
                )
        except Exception as e:
            print(f"[Sound prebuild] Warning — could not prebuild "
                  f"sounds: {e}")
            self._sounds_prebuilt = False

    def _add_click_train(self, sound, channel):
        """Write the broadband click train onto ``sound`` for ``channel``.

        This is the entire stimulus — unlike the parent paradigm there is
        no enable check and no warble underneath it, so this is never a
        no-op. Calling it is mandatory for every built Sound; skipping it
        would produce a silent trial.

        When segment pulsing is enabled the train is gated into on/off
        epochs (segment starts at t=0); otherwise it runs continuously
        for the length of the buffer.
        """
        gate = self.click_gate_checkbox.isChecked()
        seg_dur = (float(self.click_seg_dur_spin.value())
                   if gate else None)
        gap_dur = (float(self.click_gap_spin.value())
                   if gate else 0.0)
        sound.add_click_train(
            click_rate=float(self.click_rate_spin.value()),
            click_duration=float(self.click_dur_spin.value()) / 1000.0,
            amp=float(self.click_amp_spin.value()),
            channel=channel,
            segment_duration=seg_dur,
            gap_duration=gap_dur,
        )

    def _schedule_sound_rebuild(self):
        """Mark cache stale and schedule a rebuild after 200 ms debounce."""
        self._sounds_prebuilt = False
        self._sound_rebuild_timer.start(200)

    def _play_sound(self, port_key):
        """Play the pre-built click train for the given port."""
        sound_id = PORT_TO_SOUND_ID[port_key]

        if not self._sounds_prebuilt:
            # Synchronous fallback build (should rarely happen)
            print(f"[Sound] Cache miss for port {port_key} — building "
                  "synchronously")
            channel = PORT_MAP[port_key]['channel']
            duration = max(
                60.0, float(self.trial_timeout_spin.value()) + 10.0
            )
            sound = soundmodule.Sound(
                duration=duration, srate=SAMPLING_RATE,
                nchannels=N_AUDIO_CHANNELS,
            )
            self._add_click_train(sound, channel)
            self.sound_player.set_sound(sound_id, sound)

        # Play the sound, retrying on transient PortAudio stream-start
        # failures so a flaky audio device can't crash the session.
        played_ok = self._play_sound_id_resilient(sound_id)

        self.sound_playing = True
        if self.session_start_time is not None:
            self.event_log.log(
                'sound_on',
                time.time() - self.session_start_time,
                port=port_key,
                trial_num=(self.current_trial if self.trial_active
                           else -1),
            )
        if not played_ok:
            # Sound hardware failed even after retries. The trial still
            # proceeds (the mouse can poke regardless); flag it loudly
            # so the experimenter knows audio is unreliable right now.
            self.messagebar.collect(
                f"WARNING: sound for port {port_key} failed to play "
                "(audio device error) — trial continuing without sound"
            )

    def _play_sound_id_resilient(self, sound_id) -> bool:
        """Play a sound id, retrying transient PortAudio failures.

        On Windows the WDM-KS audio path intermittently raises
        PortAudioError "Unanticipated host error [-9999]" (ERROR_BUSY)
        when a new output stream is started before the previous one has
        fully closed. This wrapper retries the playback a few times,
        force-stopping the device between attempts to let it release,
        and only gives up after SOUND_PLAY_MAX_ATTEMPTS.

        Returns True if the sound started, False if every attempt
        failed. A False return is non-fatal: the caller logs a warning
        and the trial proceeds without sound rather than crashing.
        """
        last_err = None
        for attempt in range(1, SOUND_PLAY_MAX_ATTEMPTS + 1):
            try:
                self.sound_player.play(sound_id)
                if attempt > 1:
                    # Recovered after an earlier failure — note it.
                    print(f"[Sound] Playback succeeded on attempt "
                          f"{attempt}/{SOUND_PLAY_MAX_ATTEMPTS}")
                return True
            except sd.PortAudioError as e:
                last_err = e
                print(f"[Sound] PortAudioError on attempt "
                      f"{attempt}/{SOUND_PLAY_MAX_ATTEMPTS}: {e}")
                # Force-stop the device to clear any half-open stream,
                # then pause briefly before the next attempt so the OS
                # can finish releasing the audio endpoint.
                try:
                    sd.stop()
                except Exception:
                    pass
                if attempt < SOUND_PLAY_MAX_ATTEMPTS:
                    time.sleep(SOUND_PLAY_RETRY_DELAY_S)
            except Exception as e:
                # Any other error is unexpected — don't silently retry
                # forever; report and bail out of the retry loop.
                print(f"[Sound] Unexpected error during playback: {e}")
                last_err = e
                break
        print(f"[Sound] Giving up after {SOUND_PLAY_MAX_ATTEMPTS} "
              f"attempt(s); last error: {last_err}")
        return False

    def _stop_sound(self):
        """Stop any currently playing sound."""
        if self.sound_playing:
            # Stopping is normally safe, but guard it anyway so an audio
            # device hiccup can't crash the session on a stop call.
            try:
                self.sound_player.play(STOP_ALL_SOUNDS)
            except Exception as e:
                print(f"[Sound] Error while stopping sound: {e}")
                try:
                    sd.stop()
                except Exception:
                    pass
            self.sound_playing = False

            if self.session_start_time is not None:
                offset_rel = time.time() - self.session_start_time
                self.event_log.log(
                    'sound_off', offset_rel,
                    port=(self.current_trial_port if self.trial_active
                          else None),
                    trial_num=(self.current_trial if self.trial_active
                               else -1),
                )
                if (self.trial_active
                        and self.current_trial < MAX_TRIALS):
                    self.results['sound_offset_time'][self.current_trial] = \
                        offset_rel

    # ====================================================================
    # VALVES / REWARDS
    # ====================================================================

    def _manual_reward(self, port_key):
        """Deliver water at the given port without a trial."""
        now = time.time()
        self._open_valve(port_key, manual=True)
        self._manual_reward_log.append((now, port_key))
        if self.session_running and self.session_start_time is not None:
            self.event_log.log(
                f'manual_reward_{port_key}',
                now - self.session_start_time,
                port=port_key, trial_num=-1,
            )
        self.messagebar.collect(
            f"Manual reward delivered at Port {port_key}"
        )

    def _open_valve(self, port_key, manual=False):
        """Open the valve for the configured duration."""
        valve_name = PORT_MAP[port_key]['valve']
        duration = self._get_valve_duration(port_key)

        if self.session_running and self.session_start_time is not None:
            self.event_log.log(
                f'valve_open_{port_key}',
                time.time() - self.session_start_time,
                port=port_key,
                trial_num=(self.current_trial if self.trial_active
                           else -1),
            )

        if self.arduino_thread and self.arduino_connected:
            try:
                self.arduino_thread.set_digital_output(valve_name, True)
                QTimer.singleShot(
                    int(duration * 1000),
                    lambda: self._close_valve(port_key)
                )
            except Exception as e:
                self.messagebar.collect(f"Valve error: {e}")
        else:
            QTimer.singleShot(
                int(duration * 1000),
                lambda: self._close_valve(port_key)
            )

    def _close_valve(self, port_key):
        """Close the valve and record timing."""
        valve_name = PORT_MAP[port_key]['valve']
        if self.arduino_thread and self.arduino_connected:
            try:
                self.arduino_thread.set_digital_output(valve_name, False)
            except Exception as e:
                print(f"Warning: Could not close valve {valve_name}: {e}")

        if self.session_running and self.session_start_time is not None:
            close_rel = time.time() - self.session_start_time
            self.event_log.log(
                f'valve_close_{port_key}',
                close_rel,
                port=port_key,
                trial_num=(self.current_trial if self.trial_active
                           else -1),
            )
            if self.trial_active and self.current_trial < MAX_TRIALS:
                self.results['valve_close_time'][self.current_trial] = \
                    close_rel

    def _get_valve_duration(self, port_key):
        return float(self.volume_cal.get_valve_durations().get(
            port_key, 0.05
        ))

    # ====================================================================
    # TRIAL FINALIZATION
    # ====================================================================

    def _on_trial_timeout(self):
        if not self.trial_active or not self.session_running:
            return
        self.post_poke_sound_timer.stop()
        self._stop_sound()
        self.current_trial_outcome = 'timeout'
        self.messagebar.collect(
            f"Trial {self.current_trial + 1}: timeout — sound stopped"
        )
        self._finalize_trial_and_advance()

    def _on_post_poke_sound_expired(self):
        if not self.session_running:
            return
        self._stop_sound()
        self._in_post_poke_sound = False
        if self.session_start_time is not None:
            self.event_log.log(
                'post_poke_sound_end',
                time.time() - self.session_start_time,
                port=self.current_trial_port,
                trial_num=self.current_trial,
            )
        self.messagebar.collect("Post-poke sound extension complete")
        if self.trial_active:
            self._finalize_trial_and_advance()

    def _finalize_trial_and_advance(self):
        if not self.trial_active:
            return

        outcome = self.current_trial_outcome
        self._finalize_current_trial()

        if not self.session_running:
            return

        use_error_iti = (
            outcome == 'incorrect'
            and self.error_iti_checkbox.isChecked()
            and self.error_iti_spin.value() > 0
        )

        if use_error_iti:
            iti = float(self.error_iti_spin.value())
        else:
            iti = float(self.iti_spin.value())

        self._current_iti_is_error = use_error_iti

        if iti > 0:
            self.in_iti = True
            self._iti_end_time = time.time() + iti
            self.iz_tracker.disable()
            if use_error_iti:
                self.status_indicator.set_error_iti(
                    iti, self.current_trial
                )
            else:
                self.status_indicator.set_iti(iti, self.current_trial)
            if self.session_start_time is not None:
                event_name = ('error_iti_start' if use_error_iti
                              else 'iti_start')
                self.event_log.log(
                    event_name,
                    time.time() - self.session_start_time,
                    trial_num=self.current_trial - 1,
                )
            self.iti_timer.start(int(iti * 1000))
        else:
            self.in_iti = False
            self._current_iti_is_error = False
            # Poke training: IZ not enabled; wait for the next poke
            self.status_indicator.set_waiting_for_poke(
                self._blocked_ports, self.current_trial
            )

        # Rebuild the sound cache during the ITI / IZ-wait — but ONLY if
        # it is actually stale (a sound parameter changed, or the last
        # build failed). The 3-port paradigm invalidated and rebuilt
        # unconditionally after every trial; with 6 prebuilt waveforms
        # that regenerates ~6 x (timeout + 10 s) x 6-channel buffers on
        # the GUI thread between every single trial, which stalls the
        # live video/IZ tracking for no benefit. Parameter changes
        # already schedule their own rebuild via _schedule_sound_rebuild.
        if not self._sounds_prebuilt:
            QTimer.singleShot(100, self._prebuild_sounds)

    def _on_iti_end(self):
        if not self.session_running:
            return
        if self.session_start_time is not None:
            event_name = ('error_iti_end' if self._current_iti_is_error
                          else 'iti_end')
            self.event_log.log(
                event_name,
                time.time() - self.session_start_time,
                trial_num=self.current_trial,
            )
        self.in_iti = False
        self._current_iti_is_error = False
        # Poke training: IZ not enabled; wait for the next poke
        self.status_indicator.set_waiting_for_poke(
            self._blocked_ports, self.current_trial
        )

    def _finalize_current_trial(self):
        """Close the current trial's observation window and record data."""
        if self.current_trial >= MAX_TRIALS:
            return

        end_time = time.time()
        trial_num = self.current_trial

        self.trial_timeout_timer.stop()
        self.post_poke_sound_timer.stop()
        self._stop_sound()

        mouse_in_iz_at_end = bool(self.iz_tracker.in_zone)
        poke_result = self.poke_tracker.end_trial(end_time)

        # Finalise the IZ dwell. If the measurement was never frozen
        # (the mouse was still in the IZ, or within the dropout grace,
        # when the trial ended via poke or timeout), freeze it now at
        # the last confirmed in-zone moment. Otherwise it was already
        # frozen when the mouse left. Either way, persist it to the
        # per-trial array. The value spans the full continuous IZ bout
        # (entry → last confirmed in-zone).
        if (self._iz_dwell_anchor is not None
                and not self._iz_dwell_left):
            last_in = (self._iz_dwell_last_in
                       if self._iz_dwell_last_in is not None
                       else end_time)
            self.current_trial_dwell = last_in - self._iz_dwell_anchor
        self._iz_dwell_left = True
        if (self.current_trial_dwell is not None
                and np.isfinite(self.current_trial_dwell)):
            self.results['dwell_duration'][trial_num] = \
                self.current_trial_dwell

        # Fill in outcome if still unset
        outcome = self.current_trial_outcome
        if outcome is None:
            outcome = ('timeout' if not poke_result['poke_detected']
                       else ('correct'
                             if poke_result['active_port'] is not None
                             else 'incorrect'))

        end_relative = end_time - self.session_start_time
        self.results['trial_end_time'][trial_num] = end_relative
        self.results['poke_detected'][trial_num] = int(
            poke_result['poke_detected']
        )
        self.results['reward_delivered'][trial_num] = int(
            self.reward_delivered_this_trial
        )
        self.results['outcome'][trial_num] = \
            self.results.labels['outcome'][outcome]

        if poke_result['poke_time'] is not None:
            self.results['poke_time'][trial_num] = \
                poke_result['poke_time'] - self.session_start_time
        if poke_result['latency'] is not None:
            self.results['latency_to_poke'][trial_num] = \
                poke_result['latency']

        self.results['other_port_poke_detected'][trial_num] = int(
            poke_result['other_poke_detected']
        )
        if poke_result['other_poke_time'] is not None:
            self.results['other_port_poke_time'][trial_num] = \
                poke_result['other_poke_time'] - self.session_start_time

        # Log trial_end event
        self.event_log.log(
            'trial_end', end_relative,
            port=self.current_trial_port, trial_num=trial_num,
        )

        # Store per-trial record
        port_key = poke_result['active_port']
        onset_relative = self.results['trial_onset_time'][trial_num]
        # `prev_port` here = previous trial's TARGET port (legacy field
        # name kept for downstream compatibility); `prev_poked_port` is
        # the new rule-governing field — see _trigger_trial_from_iz.
        prev_target_port = (
            self.results.labels['port_triggered'].inverse.get(
                int(self.results['port_triggered'][trial_num - 1]), None
            )
            if trial_num > 0 else None
        )
        self.trial_data.append({
            'trial_num': trial_num,
            'port': port_key,
            'prev_port': prev_target_port,
            'prev_poked_port': self._last_poked_port,
            'onset_time': onset_relative,
            'outcome': outcome,
            'poke_detected': poke_result['poke_detected'],
            'latency': poke_result['latency'],
            'reward_delivered': self.reward_delivered_this_trial,
            'dwell_duration': self.current_trial_dwell,
            'n_pokes_correct_port': poke_result['n_pokes_active_port'],
            'n_pokes_incorrect_port': poke_result['n_pokes_other_port'],
            'n_pokes_inactive_ports':
                poke_result['n_pokes_inactive_ports'],
            'first_poked_port': poke_result['first_poked_port'],
            'n_incorrect_pokes_before_correct':
                poke_result['n_incorrect_before_correct'],
            # Poke training
            'n_blocked_pokes_before_reward': self._current_trial_n_blocked,
            'blocked_ports': list(self._current_trial_blocked),
            'trial_ended_by_port': self._trial_ended_by_port,
            'ended_by_inactive_port': bool(
                self._trial_ended_by_port is not None
                and self._trial_ended_by_port not in self._active_ports
            ),
            'mouse_in_iz_at_end': mouse_in_iz_at_end,
        })

        # Mirror the just-completed trial to the crash-safe journal.
        if self._session_journal is not None:
            try:
                self._session_journal.log_trial(self.trial_data[-1])
            except Exception as e:
                print(f"Warning: could not journal trial: {e}")

        # Update dashboard
        self.dashboard.record_trial(
            port_key, outcome,
            reward_delivered=self.reward_delivered_this_trial
        )

        # Update trial log table. For incorrect trials, pass the port
        # the mouse actually poked (``_trial_ended_by_port``) so the log
        # can show which port was poked in error — any of the 5
        # non-target ports.
        onset_min = int(onset_relative // 60)
        onset_sec = int(onset_relative % 60)
        time_str = f"{onset_min:02d}:{onset_sec:02d}"
        # Poke training: last two columns are time since previous reward
        # and pokes at blocked ports before this reward.
        self.trial_log.add_trial(
            trial_num, time_str, port_key, outcome,
            self._current_trial_since_prev,
            int(self._current_trial_n_blocked),
            poked_port=self._trial_ended_by_port,
        )

        # Console diagnostics
        lat_str = (f"{poke_result['latency']:.2f}s"
                   if poke_result['latency'] is not None else "none")
        reward_str = "YES" if self.reward_delivered_this_trial else "NO"
        print(f"Trial {trial_num+1}: Port {port_key}, "
              f"Outcome={outcome}, Latency={lat_str}, "
              f"Reward={reward_str}, "
              f"Dwell={self.current_trial_dwell}, "
              f"Pokes (target/non-target)="
              f"{poke_result['n_pokes_active_port']}/"
              f"{poke_result['n_pokes_other_port']}, "
              f"FirstPoked={poke_result['first_poked_port']}, "
              f"ErrorsBeforeCorrect="
              f"{poke_result['n_incorrect_before_correct']}")

        # Record parameter values for this trial
        self.params.update_history(trial_num)

        # Record the port the mouse poked on this trial (None if it timed
        # out without poking). This does NOT influence the next trial's
        # target — that is drawn uniformly at random from all 6 ports
        # regardless (see _choose_next_port). It is kept solely as a
        # saved regressor (`prev_poked_port` on the NEXT trial's row).
        self._last_poked_port = self._trial_ended_by_port

        # Advance
        self.current_trial += 1
        self.trial_active = False
        self._in_post_poke_sound = False
        # Clear the IZ-dwell measurement; the next trial re-arms it in
        # _trigger_trial_from_iz.
        self._iz_dwell_anchor = None
        self._iz_dwell_last_in = None
        self._iz_dwell_left = False

    # ====================================================================
    # DATA SAVING
    # ====================================================================

    def _save_data(self):
        """Save session data to HDF5 file using paradigm schema v5.

        The group/dataset LAYOUT is byte-for-byte the same shape as v4 —
        no datasets added or removed — so existing readers open these
        files without a rename layer. Only field VALUES differ (all-6
        active set, uniform-random selection rule, structurally-zero
        inactive-port counts). See SCHEMA NOTES in the module docstring.
        """
        if self.data_saved:
            return

        subject = self.session_info.get_value('subject')
        date_str = time.strftime('%Y%m%d')

        data_path = self.data_paths.get_data_path()
        data_dir = os.path.join(data_path, subject)
        os.makedirs(data_dir, exist_ok=True)

        # Find next available suffix (a, b, c, ...)
        suffix_ord = ord('a')
        while True:
            suffix = (chr(suffix_ord) if suffix_ord <= ord('z')
                      else str(suffix_ord - ord('z')))
            filename = (f"{subject}_{PARADIGM_NAME}_"
                        f"{date_str}{suffix}.h5")
            filepath = os.path.join(data_dir, filename)
            if not os.path.exists(filepath):
                break
            suffix_ord += 1

        n_trials = self.current_trial

        try:
            with h5py.File(filepath, 'w') as h5:
                # --------- /meta ---------
                meta = h5.create_group('meta')
                meta.attrs['paradigm_name'] = PARADIGM_NAME
                meta.attrs['paradigm_version'] = PARADIGM_VERSION
                meta.attrs['schema_version'] = SCHEMA_VERSION
                meta.attrs['save_timestamp'] = \
                    datetime.now().isoformat(timespec='seconds')
                meta.attrs['session_start_epoch'] = float(
                    self.session_start_epoch or 0.0
                )
                meta.attrs['session_end_epoch'] = float(
                    self.session_end_epoch or 0.0
                )
                meta.attrs['session_start_iso'] = datetime.fromtimestamp(
                    self.session_start_epoch
                ).isoformat(timespec='seconds') if self.session_start_epoch \
                    else ''
                meta.attrs['session_end_iso'] = datetime.fromtimestamp(
                    self.session_end_epoch
                ).isoformat(timespec='seconds') if self.session_end_epoch \
                    else ''
                # Convenience fields for analysis tools: explicit duration
                # and trial count without having to crawl /trials.
                meta.attrs['session_duration_sec'] = float(max(
                    0.0,
                    (self.session_end_epoch or 0.0) -
                    (self.session_start_epoch or 0.0),
                ))
                meta.attrs['n_trials'] = int(n_trials)
                # Date string in the same YYYYMMDD format as the filename.
                meta.attrs['date_str'] = date_str
                meta.attrs['git_hash'] = self._get_git_hash()
                meta.attrs['python_version'] = sys.version
                meta.attrs['hostname'] = os.uname().nodename \
                    if hasattr(os, 'uname') else 'unknown'
                meta.attrs['subject'] = subject
                meta.attrs['trainer'] = self.session_info.get_value(
                    'trainer'
                )
                meta.attrs['notes'] = self.notes_edit.toPlainText().strip()
                meta.attrs['video_filename'] = (
                    os.path.basename(self.current_video_filepath)
                    if self.current_video_filepath else ''
                )

                # Self-describing: which event types & ports are encoded?
                meta.attrs['events_type_enum_map_json'] = json.dumps(
                    EVENT_TYPES
                )
                meta.attrs['port_enum_map_json'] = json.dumps(
                    {**{p: PORT_TO_INT[p] for p in ALL_PORTS},
                     'none': -1}
                )

                # --------- /task_params ---------
                tp = h5.create_group('task_params')
                # Active set: all 6 ports, every session.
                tp.attrs['active_ports'] = np.array(self._active_ports,
                                                    dtype='S1')
                tp.attrs['active_set_name'] = ACTIVE_SET_NAME   # 'ABCDEF'
                tp.attrs['n_active_ports'] = int(N_ACTIVE_PORTS)
                tp.attrs['n_inactive_ports'] = int(
                    len(ALL_PORTS) - N_ACTIVE_PORTS
                )
                tp.attrs['chance_level_pct'] = float(CHANCE_LEVEL_PCT)

                # Trial-selection rule (no parameters needed).
                #   v3: 'no_repeat_previous'       (excluded prev TARGET)
                #   v4: 'no_repeat_previous_poke'  (excluded prev POKED port)
                #   v5: 'uniform_random_all_ports' (excludes nothing)
                #
                # !! DOWNSTREAM COMPATIBILITY !!
                # The v3/v4 analyzer detects the task mode by matching a
                # rule string that STARTS WITH 'no_repeat'. This string
                # does not, so that branch will not fire on v5 files.
                # Detect the 6-port mode from `n_active_ports` (== 6) or
                # `active_set_name` (== 'ABCDEF') instead.
                tp.attrs['trial_selection_rule'] = 'poke_training'
                tp.attrs['task_type'] = 'poke_training'
                tp.attrs['blocked_ports_rule'] = self._blocked_rule
                tp.attrs['reward_sound_duration_sec'] = float(
                    self.post_poke_sound_spin.value()
                )

                # IZ params
                tp.attrs['iz_radius_px'] = float(self.iz_config.get_radius())
                tp.attrs['iz_dwell_sec'] = float(
                    self.iz_config.get_dwell_sec()
                )
                tp.attrs['iz_center_x_px'] = float(DEFAULT_MASK[0])
                tp.attrs['iz_center_y_px'] = float(DEFAULT_MASK[1])
                tp.attrs['iz_dropout_grace_sec'] = float(
                    self.iz_tracker.dropout_grace_sec
                )

                # Sound params.
                #
                # The stimulus is a broadband click train ONLY. The fm_*
                # attributes written by the parent 6-port paradigm are
                # deliberately NOT written here rather than being zero-
                # or NaN-filled: a placeholder would silently propagate
                # into analyses as though it described a real stimulus,
                # whereas an absent key fails loudly. Readers should use
                # tp.attrs.get(...) and branch on 'sound_type'.
                tp.attrs['sound_type'] = 'broadband_click_train'
                tp.attrs['fm_enabled'] = 0
                # Mirrors click_amplitude — there is no separate warble
                # level in this paradigm. Kept under the parent's name so
                # generic "what level was this session run at" readers
                # keep working.
                tp.attrs['sound_amplitude'] = float(
                    self.click_amp_spin.value()
                )
                tp.attrs['sampling_rate_hz'] = SAMPLING_RATE
                tp.attrs['n_audio_channels'] = N_AUDIO_CHANNELS

                # Broadband click-train params. Clicks are brief
                # white-noise bursts on the target port's channel. When
                # pulsing is enabled the train is gated into on/off
                # epochs using the segment/gap durations below; when
                # disabled the train is continuous and those two values
                # are recorded but unused.
                # click_train_enabled is structurally 1 here (the train
                # is the only sound); it is written for schema
                # compatibility with the parent paradigm's files.
                tp.attrs['click_train_enabled'] = 1
                tp.attrs['click_rate_hz'] = float(
                    self.click_rate_spin.value()
                )
                tp.attrs['click_amplitude'] = float(
                    self.click_amp_spin.value()
                )
                tp.attrs['click_duration_ms'] = float(
                    self.click_dur_spin.value()
                )
                tp.attrs['click_gated_to_segments'] = int(
                    self.click_gate_checkbox.isChecked()
                )
                tp.attrs['click_segment_duration_sec'] = float(
                    self.click_seg_dur_spin.value()
                )
                tp.attrs['click_gap_duration_sec'] = float(
                    self.click_gap_spin.value()
                )

                # Trial timing
                tp.attrs['trial_timeout_sec'] = float(
                    self.trial_timeout_spin.value()
                )
                tp.attrs['post_poke_sound_enabled'] = int(
                    self.post_poke_sound_checkbox.isChecked()
                )
                tp.attrs['post_poke_sound_duration_sec'] = float(
                    self.post_poke_sound_spin.value()
                )
                tp.attrs['iti_sec'] = float(self.iti_spin.value())
                tp.attrs['error_iti_enabled'] = int(
                    self.error_iti_checkbox.isChecked()
                )
                tp.attrs['error_iti_sec'] = float(
                    self.error_iti_spin.value()
                )
                # No inactive ports exist in the 6-port task, so this is
                # vacuous: every non-target poke ends the trial as
                # incorrect. Written as 1 (rather than dropped) so v4-era
                # readers that expect the attr keep working; use
                # `n_inactive_ports` (== 0) as the unambiguous field.
                tp.attrs['inactive_pokes_count_as_incorrect'] = 1
                tp.attrs['incorrect_poke_ends_trial'] = int(
                    self.incorrect_ends_trial_checkbox.isChecked()
                )
                tp.attrs['max_session_duration_sec'] = float(
                    self.session_info.get_value('maxSessionDuration')
                )

                # Tracking params
                tp.attrs['video_black_threshold'] = BLACK_THRESHOLD
                tp.attrs['video_min_area'] = MIN_AREA
                tp.attrs['display_mask_cx_px'] = DEFAULT_MASK[0]
                tp.attrs['display_mask_cy_px'] = DEFAULT_MASK[1]
                tp.attrs['display_mask_radius_px'] = DEFAULT_MASK[2]

                # --------- /hardware ---------
                hw = h5.create_group('hardware')
                hw.attrs['hardware_interface'] = config.HARDWARE_INTERFACE
                hw.attrs['camera_type'] = getattr(
                    config, 'CAMERA_TYPE', 'webcam'
                )
                hw.attrs['arduino_port'] = getattr(
                    config, 'ARDUINO_PORT', ''
                )
                hw.attrs['sound_device'] = config.SOUND_DEVICE
                # Per-port valve durations and µL/open for ALL 6 ports
                valve_durs = self.volume_cal.get_valve_durations()
                vol_per = self.volume_cal.get_values()
                for p in ALL_PORTS:
                    hw.attrs[f'valve_duration_{p}_sec'] = float(
                        valve_durs[p]
                    )
                    hw.attrs[f'volume_per_open_{p}_ul'] = float(vol_per[p])

                # Per-port → audio channel mapping
                hw.attrs['port_to_channel_json'] = json.dumps(
                    {p: PORT_MAP[p]['channel'] for p in ALL_PORTS}
                )

                # --------- /trials ---------
                trials = h5.create_group('trials')
                trials.attrs['n_trials'] = n_trials
                trials.attrs['port_enum_map_json'] = json.dumps(
                    {**{p: PORT_TO_INT[p] for p in ALL_PORTS},
                     'none': -1}
                )
                trials.attrs['outcome_enum_map_json'] = json.dumps(
                    dict(self.results.labels['outcome'])
                )

                if n_trials > 0:
                    # Dataset names are unchanged from v4 (which followed
                    # the v2 IZ-training schema), so the session analyzer
                    # reads v5 files without a rename layer. Two of them
                    # are now structurally constant — see the comments at
                    # n_pokes_inactive_ports / ended_by_inactive_port
                    # below.
                    trials.create_dataset(
                        'port_triggered',
                        data=self.results['port_triggered'][:n_trials]
                    )
                    trials.create_dataset(
                        'prev_port',
                        data=self.results['prev_port'][:n_trials]
                    )
                    # Port the mouse poked on the previous trial (-1 if
                    # that trial timed out, or on trial 0). In v5 this no
                    # longer gates trial selection — targets are drawn
                    # uniformly at random from all 6 ports — but it is
                    # still saved as a regressor (win-stay/lose-shift,
                    # perseveration, previous-port effects on approach).
                    # `prev_port` above is the previous trial's TARGET.
                    trials.create_dataset(
                        'prev_poked_port',
                        data=self.results['prev_poked_port'][:n_trials]
                    )
                    trials.create_dataset(
                        'outcome',
                        data=self.results['outcome'][:n_trials]
                    )
                    trials.create_dataset(
                        'trial_onset_sec',
                        data=self.results['trial_onset_time'][:n_trials]
                    )
                    trials.create_dataset(
                        'trial_end_sec',
                        data=self.results['trial_end_time'][:n_trials]
                    )
                    trials.create_dataset(
                        'sound_offset_sec',
                        data=self.results['sound_offset_time'][:n_trials]
                    )
                    trials.create_dataset(
                        'valve_close_sec',
                        data=self.results['valve_close_time'][:n_trials]
                    )
                    trials.create_dataset(
                        'poke_detected',
                        data=self.results['poke_detected'][:n_trials]
                            .astype(np.int8)
                    )
                    trials.create_dataset(
                        'first_correct_poke_sec',
                        data=self.results['poke_time'][:n_trials]
                    )
                    trials.create_dataset(
                        'latency_sec',
                        data=self.results['latency_to_poke'][:n_trials]
                    )
                    trials.create_dataset(
                        'other_port_poke_detected',
                        data=self.results[
                            'other_port_poke_detected'
                        ][:n_trials].astype(np.int8)
                    )
                    trials.create_dataset(
                        'first_incorrect_poke_sec',
                        data=self.results[
                            'other_port_poke_time'
                        ][:n_trials]
                    )
                    trials.create_dataset(
                        'reward_delivered',
                        data=self.results['reward_delivered'][:n_trials]
                            .astype(np.int8)
                    )
                    trials.create_dataset(
                        'dwell_duration_sec',
                        data=self.results['dwell_duration'][:n_trials]
                    )

                    # Per-trial poke counts (target / non-target /
                    # inactive). These come from self.trial_data rather
                    # than self.results to keep the schema clean.
                    # n_pokes_inactive_ports is ALWAYS 0 in v5: all 6
                    # ports are active, so no poke can land on an
                    # inactive one. The dataset is written anyway so the
                    # file shape matches v4.
                    npokes_correct = np.array(
                        [t['n_pokes_correct_port'] for t in self.trial_data],
                        dtype=np.int32
                    )
                    npokes_incorrect = np.array(
                        [t['n_pokes_incorrect_port']
                         for t in self.trial_data], dtype=np.int32
                    )
                    npokes_inactive = np.array(
                        [t['n_pokes_inactive_ports']
                         for t in self.trial_data], dtype=np.int32
                    )
                    trials.create_dataset(
                        'n_pokes_correct_port', data=npokes_correct
                    )
                    trials.create_dataset(
                        'n_pokes_incorrect_port', data=npokes_incorrect
                    )
                    trials.create_dataset(
                        'n_pokes_inactive_ports', data=npokes_inactive
                    )
                    # Shaping fields. first_poked_port: port enum of the
                    # first poke in the trial (-1 if no poke). Correct on
                    # first try <=> outcome == correct and
                    # n_incorrect_pokes_before_correct == 0. Pokes after
                    # the reward (post-poke sound) are not counted.
                    first_poked = np.array(
                        [PORT_TO_INT.get(t.get('first_poked_port'), -1)
                         for t in self.trial_data], dtype=np.int8
                    )
                    trials.create_dataset(
                        'first_poked_port', data=first_poked
                    )
                    n_errors_before_correct = np.array(
                        [t['n_incorrect_pokes_before_correct']
                         for t in self.trial_data], dtype=np.int32
                    )
                    trials.create_dataset(
                        'n_incorrect_pokes_before_correct',
                        data=n_errors_before_correct
                    )
                    # Poke training fields
                    n_blocked_pokes = np.array(
                        [trial['n_blocked_pokes_before_reward']
                         for trial in self.trial_data], dtype=np.int32
                    )
                    trials.create_dataset(
                        'n_blocked_pokes_before_reward',
                        data=n_blocked_pokes
                    )
                    blocked_mask = np.array(
                        [[int(port in trial['blocked_ports'])
                          for port in ALL_PORTS]
                         for trial in self.trial_data], dtype=np.int8
                    )
                    blocked_dataset = trials.create_dataset(
                        'blocked_ports_mask', data=blocked_mask
                    )
                    blocked_dataset.attrs['port_order'] = ''.join(ALL_PORTS)
                    # Which port (enum int) caused the trial to end.
                    # -1 if the trial timed out (no poke). For an
                    # incorrect trial this is the non-target port the
                    # mouse actually poked — the key field for building
                    # the 6x6 target-vs-choice confusion matrix, which
                    # is the main new analysis this paradigm affords.
                    ended_by = np.array(
                        [PORT_TO_INT.get(t.get('trial_ended_by_port'), -1)
                         for t in self.trial_data], dtype=np.int8
                    )
                    trials.create_dataset(
                        'trial_ended_by_port', data=ended_by
                    )
                    # ALWAYS 0 in v5 (no inactive ports exist). Retained
                    # so the file shape matches v4.
                    ended_by_inactive = np.array(
                        [int(bool(t.get('ended_by_inactive_port', False)))
                         for t in self.trial_data], dtype=np.int8
                    )
                    trials.create_dataset(
                        'ended_by_inactive_port',
                        data=ended_by_inactive
                    )
                    in_iz_at_end = np.array(
                        [int(t['mouse_in_iz_at_end'])
                         for t in self.trial_data], dtype=np.int8
                    )
                    # Field name matches v2 ('mouse_in_iz_at_end')
                    trials.create_dataset(
                        'mouse_in_iz_at_end', data=in_iz_at_end
                    )

                # --------- /events ---------
                ev_times, ev_types, ev_ports, ev_trials = \
                    self.event_log.as_arrays()
                events = h5.create_group('events')
                events.attrs['n_events'] = len(self.event_log)
                events.attrs['event_type_enum_map_json'] = json.dumps(
                    EVENT_TYPES
                )
                events.attrs['port_enum_map_json'] = json.dumps(
                    {**{p: PORT_TO_INT[p] for p in ALL_PORTS},
                     'none': -1}
                )
                events.create_dataset('time_sec', data=ev_times)
                events.create_dataset('event_type', data=ev_types)
                events.create_dataset('port', data=ev_ports)
                events.create_dataset('trial_num', data=ev_trials)

                # --------- /tracking ---------
                # Per-frame state co-indexed with the video frames. All
                # arrays here have the same length (= self.frame_tracker
                # length), and ``time_sec`` is the time-base.
                # Field names follow the v2 IZ-training convention so the
                # session analyzer's existing v2 reader can pick these up
                # without paradigm-specific handling.
                tracking = h5.create_group('tracking')
                tracking.attrs['phase_enum_map_json'] = json.dumps(PHASES)
                tracking.attrs['n_frames'] = len(self.frame_tracker)
                if len(self.frame_tracker) > 0:
                    abs_ts = np.array(self.frame_tracker.timestamps,
                                      dtype=np.float64)
                    rel_ts = abs_ts - float(self.session_start_epoch or 0.0)
                    tracking.create_dataset('time_sec', data=rel_ts)
                    tracking.create_dataset('time_epoch', data=abs_ts)
                    # Centroid x/y in display-frame pixels, plus a validity
                    # mask. NaN where tracking lost the mouse; valid=False
                    # marks those frames so downstream tools can skip them.
                    tracking.create_dataset(
                        'centroid_x_display_px',
                        data=np.array(self.frame_tracker.centroid_x,
                                      dtype=np.float32),
                    )
                    tracking.create_dataset(
                        'centroid_y_display_px',
                        data=np.array(self.frame_tracker.centroid_y,
                                      dtype=np.float32),
                    )
                    tracking.create_dataset(
                        'centroid_valid',
                        data=np.array(self.frame_tracker.centroid_valid,
                                      dtype=np.int8),
                    )
                    tracking.create_dataset(
                        'phase',
                        data=np.array(self.frame_tracker.phases,
                                      dtype=np.int8)
                    )
                    tracking.create_dataset(
                        'trial_num',
                        data=np.array(self.frame_tracker.trial_nums,
                                      dtype=np.int32)
                    )
                    tracking.create_dataset(
                        'in_iz',
                        data=np.array(self.frame_tracker.in_iz,
                                      dtype=np.int8)
                    )
                    tracking.create_dataset(
                        'dwell_sec',
                        data=np.array(self.frame_tracker.dwell_secs,
                                      dtype=np.float32)
                    )

                # --------- /video ---------
                video = h5.create_group('video')
                video.attrs['filename'] = (
                    os.path.basename(self.current_video_filepath)
                    if self.current_video_filepath else ''
                )
                video.attrs['filepath'] = (
                    self.current_video_filepath or ''
                )
                # Frame rate for this recording. 'fps_requested' is what
                # config asked for; 'fps_actual' is what the camera
                # accepted and what is written into the MP4 header -- they
                # differ if exposure or bandwidth forced a clamp, so
                # analysis should use fps_actual. For exact per-frame
                # timing prefer frame_time_epoch / frame_time_sec below;
                # those are measured, not assumed. 0.0 means unknown.
                try:
                    _fps_req = (
                        float(getattr(config, 'SPINNAKER_ACQUISITION_FPS', 0))
                        if getattr(config, 'CAMERA_TYPE', 'webcam')
                        == 'spinnaker' else 0.0
                    )
                except (TypeError, ValueError):
                    _fps_req = 0.0
                _fps_act = None
                if hasattr(self.video_thread, 'get_fps'):
                    try:
                        _fps_act = self.video_thread.get_fps()
                    except Exception:
                        _fps_act = None
                video.attrs['fps_requested'] = _fps_req
                video.attrs['fps_actual'] = float(_fps_act or 0.0)
                # Centroid time-series from the video thread
                if hasattr(self.video_thread, 'points'):
                    try:
                        points_data = self.video_thread.points
                        if points_data is not None and len(points_data) > 0:
                            pts = np.array(points_data)
                            if pts.ndim == 3 and pts.shape[1] == 1:
                                pts = pts.squeeze(axis=1)
                            video.create_dataset('centroid_xy', data=pts)
                    except Exception as e:
                        print(f"Warning: could not save centroid: {e}")
                if hasattr(self.video_thread, 'frame_timestamps'):
                    try:
                        ts = self.video_thread.frame_timestamps
                        if ts is not None and len(ts) > 0:
                            ts_arr = np.array(ts, dtype=np.float64)
                            video.create_dataset(
                                'frame_time_epoch', data=ts_arr
                            )
                            rel = ts_arr - float(
                                self.session_start_epoch or 0.0
                            )
                            video.create_dataset(
                                'frame_time_sec', data=rel
                            )
                    except Exception as e:
                        print(f"Warning: could not save frame "
                              f"timestamps: {e}")

                # --------- /manual_rewards ---------
                if len(self._manual_reward_log) > 0:
                    mr = h5.create_group('manual_rewards')
                    mr_times = np.array(
                        [t for (t, _p) in self._manual_reward_log],
                        dtype=np.float64
                    )
                    mr_rel = mr_times - float(self.session_start_epoch or 0.0)
                    mr_ports = np.array(
                        [PORT_TO_INT.get(p, -1)
                         for (_t, p) in self._manual_reward_log],
                        dtype=np.int8
                    )
                    mr.create_dataset('time_sec', data=mr_rel)
                    mr.create_dataset('time_epoch', data=mr_times)
                    mr.create_dataset('port', data=mr_ports)
                    mr.attrs['port_enum_map_json'] = json.dumps(
                        {**{p: PORT_TO_INT[p] for p in ALL_PORTS},
                         'none': -1}
                    )

            self.current_data_filepath = filepath
            self.data_saved = True
            self.messagebar.collect(
                f"Data saved → {os.path.basename(filepath)}"
            )
        except Exception as e:
            self.messagebar.collect(f"Error saving data: {e}")
            raise

    @staticmethod
    def _get_git_hash():
        try:
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                cwd=os.path.dirname(os.path.abspath(__file__)),
                capture_output=True, text=True, timeout=2,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return 'unknown'

    def _manual_save(self):
        """Manually trigger data save (button in UI)."""
        try:
            self._save_data()
            QMessageBox.information(
                self, "Save Successful",
                f"Data saved to:\n{self.current_data_filepath}"
            )
        except Exception as e:
            QMessageBox.warning(
                self, "Save Error", f"Could not save:\n{e}"
            )

    def _append_csv_summary(self):
        """Append a one-line per-session summary to a master CSV.

        File lives at:
            <DATA_PATH>/session_summary_log.csv

        The column set is deliberately IDENTICAL to the 3-port
        paradigm's, so both paradigms can share one master training log
        and rows stay aligned under a single header — the `paradigm`
        column (and `speaker_set_name`: 'ACE'/'BDF' vs 'ABCDEF') tells
        them apart. That matters for cross-stage training-progression
        plots.

        Two columns are therefore retained with constant values rather
        than dropped:
            inactive_pokes_count_as_incorrect  -> always 1 (vacuous)
            n_pokes_inactive_port_total        -> always 0 (no inactive ports)

        If the existing file's header does NOT match this row's fields
        (e.g. it was written by a different paradigm version), we fall
        back to a paradigm-specific file rather than writing values
        under the wrong headers — csv.DictWriter would otherwise happily
        append a misaligned row.
        """
        if not self.session_running and self.current_trial == 0:
            return

        data_path = self.data_paths.get_data_path()
        os.makedirs(data_path, exist_ok=True)
        csv_path = os.path.join(data_path, CSV_SUMMARY_FILENAME)

        stats = self.dashboard.get_summary_stats()
        n_trials = self.current_trial
        subject = self.session_info.get_value('subject')
        trainer = self.session_info.get_value('trainer')

        latencies = [t['latency'] for t in self.trial_data
                     if t['latency'] is not None]
        mean_lat = (float(np.mean(latencies))
                    if len(latencies) > 0 else float('nan'))
        median_lat = (float(np.median(latencies))
                      if len(latencies) > 0 else float('nan'))

        if self.session_start_epoch and self.session_end_epoch:
            duration_min = (self.session_end_epoch
                            - self.session_start_epoch) / 60.0
        else:
            duration_min = float('nan')

        # Per-port latencies (active only — others will be NaN)
        per_port_latencies: Dict[str, list] = {p: [] for p in ALL_PORTS}
        for t in self.trial_data:
            if t['latency'] is not None and t['port'] in per_port_latencies:
                per_port_latencies[t['port']].append(t['latency'])

        # Pokes-at-inactive-port totals across all trials. Structurally
        # 0 here (no inactive ports); computed anyway so the column keeps
        # its meaning if ALL_PORTS is ever reduced.
        n_pokes_inactive_total = sum(
            t.get('n_pokes_inactive_ports', 0) for t in self.trial_data
        )

        # Active set identifier — always 'ABCDEF' in this paradigm.
        speaker_set_name = ACTIVE_SET_NAME
        active_ports_str = '/'.join(self._active_ports)

        row = {
            'date': time.strftime('%Y-%m-%d'),
            'time': time.strftime('%H:%M:%S'),
            'subject': subject,
            'trainer': trainer,
            'paradigm': PARADIGM_NAME,
            'duration_min': f"{duration_min:.2f}",
            'n_trials': n_trials,
            'speaker_set_name': speaker_set_name,
            'active_ports': active_ports_str,
            'iz_radius_px': f"{self.iz_config.get_radius():.0f}",
            'iz_dwell_sec': f"{self.iz_config.get_dwell_sec():.2f}",
            'trial_timeout_sec': f"{self.trial_timeout_spin.value():.1f}",
            'iti_sec': f"{self.iti_spin.value():.1f}",
            'error_iti_enabled': int(self.error_iti_checkbox.isChecked()),
            'error_iti_sec': f"{self.error_iti_spin.value():.1f}",
            # Vacuous in the 6-port task (no inactive ports exist), but
            # kept so the column set matches the 3-port log. See docstring.
            'inactive_pokes_count_as_incorrect': 1,
            'incorrect_poke_ends_trial': int(
                self.incorrect_ends_trial_checkbox.isChecked()
            ),
            'blocked_ports_rule': self._blocked_rule,
            'n_blocked_pokes_total': sum(
                trial['n_blocked_pokes_before_reward']
                for trial in self.trial_data
            ),
            'post_poke_sound_enabled': int(
                self.post_poke_sound_checkbox.isChecked()
            ),
            'post_poke_sound_sec': f"{self.post_poke_sound_spin.value():.1f}",
            # Stimulus: broadband click train only. No fm_* columns —
            # this log is written to a paradigm-specific filename, so
            # the changed column set cannot corrupt the parent
            # paradigm's summary CSV.
            'sound_type': 'broadband_click_train',
            'sound_amplitude': f"{self.click_amp_spin.value():.3f}",
            'click_train_enabled': 1,
            'click_rate_hz': f"{self.click_rate_spin.value():.1f}",
            'click_amplitude': f"{self.click_amp_spin.value():.3f}",
            'click_duration_ms': f"{self.click_dur_spin.value():.2f}",
            'click_gated_to_segments': int(
                self.click_gate_checkbox.isChecked()
            ),
            'click_segment_duration_sec': (
                f"{self.click_seg_dur_spin.value():.2f}"
            ),
            'click_gap_duration_sec': f"{self.click_gap_spin.value():.2f}",
            'total_correct': stats['total_correct'],
            'total_incorrect': stats['total_incorrect'],
            'total_timeouts': stats['total_timeouts'],
            'total_rewards': stats['total_rewards'],
            'n_correct_first_try': sum(
                1 for trial in self.trial_data
                if trial['outcome'] == 'correct'
                and trial['n_incorrect_pokes_before_correct'] == 0
            ),
            'correct_rate_pct': f"{stats['correct_rate']:.1f}",
            'reward_rate_pct': f"{stats['reward_rate']:.1f}",
            'mean_latency_sec': (f"{mean_lat:.3f}"
                                 if not np.isnan(mean_lat) else 'NaN'),
            'median_latency_sec': (f"{median_lat:.3f}"
                                   if not np.isnan(median_lat) else 'NaN'),
            'n_pokes_inactive_port_total': n_pokes_inactive_total,
            'total_water_ul': f"{stats['total_water_ul']:.2f}",
        }

        # Per-port columns (all 6 ports)
        for p in ALL_PORTS:
            row[f'n_trials_{p}'] = stats['n_trials'][p]
            row[f'n_correct_{p}'] = stats['n_correct'][p]
            row[f'n_incorrect_{p}'] = stats['n_incorrect'][p]
            row[f'n_timeouts_{p}'] = stats['n_timeouts'][p]
            row[f'n_rewards_{p}'] = stats['n_rewards'][p]
            row[f'volume_per_open_{p}_ul'] = (
                f"{stats['vol_per'][p]:.2f}"
            )
            row[f'correct_rate_{p}_pct'] = (
                f"{stats['correct_rate_per_port'][p]:.1f}"
            )
            if per_port_latencies[p]:
                row[f'mean_latency_{p}_sec'] = (
                    f"{float(np.mean(per_port_latencies[p])):.3f}"
                )
            else:
                row[f'mean_latency_{p}_sec'] = 'NaN'

        # Final two columns: filenames + notes
        row['data_filename'] = (
            os.path.basename(self.current_data_filepath)
            if self.current_data_filepath else ''
        )
        row['video_filename'] = (
            os.path.basename(self.current_video_filepath)
            if self.current_video_filepath else ''
        )
        row['notes'] = self.notes_edit.toPlainText().strip().replace(
            '\n', ' | '
        )

        file_exists = os.path.exists(csv_path)

        # Guard against silent column misalignment. DictWriter writes the
        # row's VALUES in the row's key order; it does not check them
        # against a header that is already on disk. If an existing log was
        # written with a different column set, appending would put values
        # under the wrong headers with no error. Detect that and divert to
        # a paradigm-specific file instead.
        if file_exists:
            try:
                with open(csv_path, 'r', newline='', encoding='utf-8') as f:
                    existing_header = next(csv.reader(f), [])
            except Exception:
                existing_header = []
            if existing_header and existing_header != list(row.keys()):
                csv_path = os.path.join(
                    data_path, f'session_summary_log_{PARADIGM_NAME}.csv'
                )
                file_exists = os.path.exists(csv_path)
                self.messagebar.collect(
                    f"Master CSV header mismatch — appending to "
                    f"{os.path.basename(csv_path)} instead"
                )
                print(f"[CSV] Header of {CSV_SUMMARY_FILENAME} does not "
                      f"match this paradigm's columns; wrote to "
                      f"{os.path.basename(csv_path)} to avoid misaligned "
                      f"rows.")

        try:
            with open(csv_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=list(row.keys()))
                if not file_exists:
                    writer.writeheader()
                writer.writerow(row)
            self.messagebar.collect(
                f"Session appended to {os.path.basename(csv_path)}"
            )
        except Exception as e:
            self.messagebar.collect(f"CSV append failed: {e}")
            raise

    def _show_summary_dialog(self):
        """Pop modal summary at session end."""
        stats = self.dashboard.get_summary_stats()
        latencies = [t['latency'] for t in self.trial_data
                     if t['latency'] is not None]
        mean_lat = (float(np.mean(latencies))
                    if len(latencies) > 0 else None)
        median_lat = (float(np.median(latencies))
                      if len(latencies) > 0 else None)

        # Per-port mean latencies
        per_port = {p: [] for p in ALL_PORTS}
        for t in self.trial_data:
            if t['latency'] is not None and t['port'] in per_port:
                per_port[t['port']].append(t['latency'])
        mean_lat_per_port = {
            p: (float(np.mean(per_port[p])) if per_port[p] else None)
            for p in ALL_PORTS
        }

        if self.session_start_epoch and self.session_end_epoch:
            duration_min = (
                self.session_end_epoch - self.session_start_epoch
            ) / 60.0
        else:
            duration_min = 0.0

        dialog = SessionSummaryDialog(
            stats=stats,
            subject=self.session_info.get_value('subject'),
            trainer=self.session_info.get_value('trainer'),
            session_minutes=duration_min,
            mean_lat=mean_lat,
            median_lat=median_lat,
            mean_lat_per_port=mean_lat_per_port,
            speaker_set_name=ACTIVE_SET_NAME,
            active_ports=list(self._active_ports),
            data_fp=self.current_data_filepath,
            video_fp=self.current_video_filepath,
            notes=self.notes_edit.toPlainText().strip(),
            parent=self,
        )
        dialog.exec()

    # ====================================================================
    # CLEANUP
    # ====================================================================

    def closeEvent(self, event):
        """Clean shutdown of threads and hardware."""
        if self.session_running:
            reply = QMessageBox.question(
                self, "Confirm Exit",
                "A session is still running. Stop the session and "
                "save data before exiting?",
                QMessageBox.StandardButton.Yes |
                QMessageBox.StandardButton.No |
                QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Yes
            )
            if reply == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
            elif reply == QMessageBox.StandardButton.Yes:
                self._stop_session()

        try:
            self._stop_sound()
        except Exception:
            pass

        # Close all valves on exit (all 6, defensive)
        if self.arduino_thread and self.arduino_connected:
            for port_key, info in PORT_MAP.items():
                try:
                    self.arduino_thread.set_digital_output(
                        info['valve'], False
                    )
                except Exception:
                    pass

        # Stop video thread
        try:
            if hasattr(self.video_thread, 'stop_recording'):
                self.video_thread.stop_recording()
            self.video_thread.stop()
            self.video_thread.wait()
        except Exception as e:
            print(f"Warning: Error stopping video thread: {e}")

        # Stop Arduino
        if self.arduino_thread:
            try:
                self.arduino_thread.stop()
                self.arduino_thread.wait()
            except Exception as e:
                print(f"Warning: Error stopping Arduino: {e}")

        # Stop sound player
        try:
            if hasattr(self.sound_player, 'shutdown'):
                self.sound_player.shutdown()
        except Exception:
            pass

        # Close the crash-safe journal if one is still open.
        if getattr(self, '_session_journal', None) is not None:
            try:
                self._session_journal.close()
            except Exception:
                pass

        event.accept()


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    (app, paradigm) = gui.create_app(Paradigm)
    paradigm.showMaximized()
    sys.exit(app.exec())
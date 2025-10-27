"""
Tool to calibrate water delivery system.

This task alternates opening the left and right valves for specified durations
to help calibrate water delivery volumes.
"""

import numpy as np
from PyQt6.QtWidgets import QWidget, QMainWindow, QHBoxLayout, QVBoxLayout
from phonotaxis import gui
from phonotaxis import widgets
from phonotaxis import controller
from phonotaxis import arduinomodule
from phonotaxis import statematrix
from phonotaxis import emulator
from phonotaxis import config


# --- State machine inputs and outputs ---
INPUTS = list(config.INPUT_PINS.keys()) 
OUTPUTS = list(config.OUTPUT_PINS.keys())


class Task(QMainWindow):
    def __init__(self):
        super().__init__()
        self.name = 'water_calibration'  # Paradigm name
        self.setWindowTitle("Water Calibration Tool")
        self.setWindowIcon(gui.create_icon())

        # -- Connect messenger --
        self.messagebar = gui.Messenger()
        self.messagebar.timed_message.connect(self._show_message)
        self.messagebar.collect('Created window')

        # -- Main widgets --
        self.session_running = False
        self.controller = controller.SessionController()

        # -- Connect signals from GUI --
        self.controller.session_started.connect(self.start_session)
        self.controller.prepare_next_trial.connect(self.prepare_next_trial)
        self.controller.session_stopped.connect(self.session_stopped)

        # -- Connect signals to messenger
        self.controller.log_message.connect(self.messagebar.collect)

        # -- Parameters --
        self.session_info = widgets.SessionInfo()
        self.session_info.set_value('maxTrials', 100)

        self.params = gui.Container()
        self.params['leftValveDuration'] = gui.NumericParam('Left valve duration', 
                                                             value=0.1, units='s',
                                                             group='Calibration params')
        self.params['rightValveDuration'] = gui.NumericParam('Right valve duration', 
                                                              value=0.1, units='s', 
                                                              group='Calibration params')
        self.params['interValveDelay'] = gui.NumericParam('Delay between valves', 
                                                           value=0.5, units='s',
                                                           group='Calibration params')
        self.calibrationParams = self.params.layout_group('Calibration params')

        # --- GUI layout ---
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QHBoxLayout(self.central_widget)
        self.layout.addWidget(self.controller.gui)
        self.layout.addWidget(self.session_info)
        self.layout.addWidget(self.calibrationParams)

        # -- State machine --
        self.sm = statematrix.StateMatrix(inputs=INPUTS, outputs=OUTPUTS)

        # -- Hardware interface --
        if config.HARDWARE_INTERFACE == 'arduino':
            self.interface = arduinomodule.ArduinoInterface(inputs=INPUTS, outputs=OUTPUTS, 
                                                            debug=True)
            self.messagebar.collect("Connecting to Arduino...")
            self.interface.arduino_ready.connect(lambda: self.messagebar.collect("Arduino ready."))
            self.interface.arduino_error.connect(
                lambda err: self.messagebar.collect(f"Arduino error: {err}"))
        elif config.HARDWARE_INTERFACE == 'emulator':
            self.interface = emulator.EmulatorWidget(inputs=INPUTS, outputs=OUTPUTS)
            self.interface.show()  # Show emulator window
        self.interface.connect_state_machine(self.controller.state_machine)

        # -- Track number of completed trials --
        self.trials_completed = 0

    def _show_message(self, msg):
        self.statusBar().showMessage(str(msg))
        print(msg)

    def start_session(self):
        """
        Called automatically when SessionController.start() is called.
        """
        if not self.session_running:
            # Set a very long session duration (we'll stop based on trial count)
            self.controller.set_session_duration(3600)  # 1 hour max
            self.session_running = True
            self.trials_completed = 0
            n_trials = int(self.session_info.get_value('maxTrials'))
            self.messagebar.collect(f"Starting calibration for {n_trials} trials")

    def session_stopped(self):
        """Called when session stops."""
        self.session_running = False
        self.messagebar.collect(f"Calibration completed: {self.trials_completed} trials")

    def prepare_next_trial(self, next_trial):
        """Prepare the next calibration trial."""
        # Check if we've completed the requested number of trials
        # n_trials = int(self.params['nTrials'].get_value())
        n_trials = int(self.session_info.get_value('maxTrials'))
        
        if next_trial > 0:
            self.params.update_history(next_trial-1)
            self.trials_completed = next_trial
            
        if next_trial >= n_trials:
            # Stop the session after completing all trials
            self.messagebar.collect(f"Completed {n_trials} trials. Stopping calibration.")
            self.controller.stop()
            return

        # Get parameters for this trial
        left_duration = self.params['leftValveDuration'].get_value()
        right_duration = self.params['rightValveDuration'].get_value()
        inter_valve_delay = self.params['interValveDelay'].get_value()

        # Build state matrix
        self.sm.reset_transitions()
        
        # State 1: Open left valve
        self.sm.add_state(name='left_valve_on', 
                          statetimer=left_duration,
                          transitions={'Tup':'left_valve_off'},
                          outputsOn=['ValveL'],
                          outputsOff=['ValveR'])
        
        # State 2: Close left valve, wait before right valve
        self.sm.add_state(name='left_valve_off', 
                          statetimer=inter_valve_delay,
                          transitions={'Tup':'right_valve_on'},
                          outputsOff=['ValveL', 'ValveR'])
        
        # State 3: Open right valve
        self.sm.add_state(name='right_valve_on', 
                          statetimer=right_duration,
                          transitions={'Tup':'right_valve_off'},
                          outputsOn=['ValveR'],
                          outputsOff=['ValveL'])
        
        # State 4: Close right valve and end trial
        self.sm.add_state(name='right_valve_off', 
                          statetimer=inter_valve_delay,
                          transitions={'Tup':'END'},
                          outputsOff=['ValveL', 'ValveR'])
        
        if next_trial == 0:
            print(self.sm)
            
        self.controller.set_state_matrix(self.sm)
        self.controller.ready_to_start_trial()

    def closeEvent(self, event):
        """Clean up when closing the window."""
        self.interface.close()  # Close the emulator window if open
        super().closeEvent(event)


if __name__ == "__main__":
    (app, paradigm) = gui.create_app(Task)

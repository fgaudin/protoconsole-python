import krpc
import serial

PORT = 'COM7'
BAUD_RATE = 115200


class InputController:
    def __init__(self, shared_state):
        self.shared_state = shared_state
        self.kerbal = krpc.connect(name=__name__, address='127.0.0.1')
        self.vessel = self.kerbal.space_center.active_vessel
        self.control = self.vessel.control
        self.arduino = None
        self.state = None
        self.staging_enabled = False
        self.handlers = {
            # switch, (parent, attribute, toggle) or callable
            16: self._ascent_mode,
            17: self._stage,
            18: (self.control, 'sas', True),
            19: (self.control, 'rcs', True),
            20: (self.control, 'lights', True),
            21: self._undock,
            22: self._orbit_mode,
            23: self._descent_mode,
            24: (self.vessel.control, 'gear', False),
            25: (self.vessel.control, 'solar_panels', False),
            26: self._engines,
            27: self._staging,
            28: self._docking_mode,
            30: (self.vessel.control, 'brakes', False),
        }

    def _ascent_mode(self, enabled):
        self.shared_state.display_mode = 'ascent'

    def _orbit_mode(self, enabled):
        self.shared_state.display_mode = 'orbit'

    def _descent_mode(self, enabled):
        self.shared_state.display_mode = 'descent'

    def _docking_mode(self, enabled):
        self.shared_state.display_mode = 'docking'

    def _engines(self, enabled):
        active_stage = self.vessel.control.current_stage
        in_stage_parts = self.vessel.parts.in_stage(active_stage)
        for p in in_stage_parts:
            if p.engine:
                e = p.engine
                if e.active != enabled:
                    e.active = enabled

    def _staging(self, enabled):
        self.shared_state.staging = enabled

    def _stage(self, enabled):
        if self.shared_state.staging and enabled:
            self.vessel.control.activate_next_stage()

    def _undock(self, enabled):
        for d in self.vessel.parts.docking_ports:
            if d.state.name == 'docked':
                d.undock()
                self.vessel = self.kerbal.space_center.active_vessel
                break

    def set_switch(self, switch, value):
        if switch not in self.handlers:
            print(f'switch {switch} not handled')
            return

        if callable(self.handlers[switch]):
            self.handlers[switch](value)
        else:
            parent = self.handlers[switch][0]
            attr = self.handlers[switch][1]
            toggle = self.handlers[switch][2]
            if toggle:
                if value is True:
                    current = getattr(parent, attr)
                    setattr(parent, attr, not current)
            else:
                setattr(parent, attr, value)

    def handle_state(self, state):
        value = bytes.fromhex(state)
        if self.state is None:
            self.state = bytes(len(value))

        for i, _byte in enumerate(value):
            changed = _byte ^ self.state[i]
            if changed:
                for j in range(8):
                    mask = 1 << j
                    bit_changed = changed & mask
                    if bit_changed:
                        switch = 8 * i + j
                        enabled = bool(_byte & mask)
                        print(f'switch {switch} now = {enabled}')
                        self.set_switch(switch, enabled)

        self.state = value

    def listen(self):
        self.arduino = serial.Serial(PORT, baudrate=BAUD_RATE, timeout=None)  # open serial port
        print(self.arduino.name)  # check which port was really used

        state = ''
        store = False
        while True:
            value = self.arduino.read(1)
            if value == b'[':
                state = ''
                store = True
            elif value == b']':
                store = False
                self.handle_state(state)
            elif store:
                state += value.decode('ascii')

        self.arduino.close()

def run(state):
    controller = InputController(state)
    controller.listen()

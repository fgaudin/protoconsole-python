import krpc
import serial

PORT = 'COM7'
BAUD_RATE = 115200


class Controller:
    def __init__(self):
        self.kerbal = krpc.connect(name='__name__', address='127.0.0.1')
        self.vessel = self.kerbal.space_center.active_vessel
        self.control = self.vessel.control
        self.arduino = None
        self.state = None
        self.staging_enabled = False
        self.handlers = {
            # switch, (parent, attribute, toggle) or callable
            17: self._stage,
            18: (self.control, 'sas', True),
            19: (self.control, 'rcs', True),
            20: (self.control, 'lights', True),
            21: self._undock,
            24: (self.vessel.control, 'gear', False),
            25: (self.vessel.control, 'solar_panels', False),
            26: self._engines,
            27: self._staging,
            30: (self.vessel.control, 'brakes', False),
        }

    def _engines(self, enabled):
        active_stage = self.vessel.control.current_stage
        in_stage_parts = self.vessel.parts.in_stage(active_stage)
        for p in in_stage_parts:
            if p.engine:
                e = p.engine
                if e.active != enabled:
                    e.active = enabled

    def _staging(self, enabled):
        self.staging_enabled = enabled

    def _stage(self, enabled):
        if self.staging_enabled and enabled:
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

if __name__ == '__main__':
    controller = Controller()
    controller.listen()

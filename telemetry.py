import krpc
import serial

PORT = 'COM3'
BAUD_RATE = 57600


class Telemetry:
    def __init__(self, shared_state):
        self.shared_state = shared_state
        self.flags = 0
        self.flags_updated = False

        # arduino
        self.arduino = serial.Serial(PORT, baudrate=BAUD_RATE, timeout=None)  # open serial port
        
        # krpc
        self.kerbal = krpc.connect(name='telemetry', address='127.0.0.1')
        self.vessel = self.kerbal.space_center.active_vessel
        self.orbit = self.vessel.orbit
        self.flight = self.vessel.flight()

        self.streams = {}

        self.flags_conf = {
            # key: (position, parent, attribute, size, value function)
            'sas': (0, self.vessel.control, 'sas', 1),
            'rcs': (1, self.vessel.control, 'rcs', 1),
            'lights': (2, self.vessel.control, 'lights', 1),
            'brakes': (3, self.vessel.control, 'brakes', 1),
            'contact': (4, self.vessel, 'situation', 1, lambda x: x.name in ['landed', 'splashed', 'pre_launch']),
            '005g': (5, self.flight, 'g_force', 1, lambda x: x > 0.05),
        }

        #flags |= any([d.state.name == 'docked' for d in self.vessel.parts.docking_ports]) << 3
        #flags |= random.choice([True, False]) << 7  # master alarm

    def value_to_flag(self, values: set):
        # flags for solar panel, gear, antenna
        # 2 bits per part
        # 0 = off
        # 1 = problem
        # 2 = deploying/retracting
        # 3 = deployed

        if {'retracting', 'extending', 'deploying'} & values:
            return 2
        elif values < {'extended', 'deployed'}:
            return 3
        elif values == {'retracted'}:
            return 0
        else:
            return 1

    def init_streams(self):
        for flag, p in self.flags_conf.items():
            stream = self.kerbal.add_stream(getattr, p[1], p[2])
            vfunc = p[4] if len(p) > 4 else None
            # why flag=flag: see https://stackoverflow.com/questions/11087047/deferred-evaluation-with-lambda-in-python
            stream.add_callback(lambda val, flag=flag, size=p[3], vfunc=vfunc: self._update_flags(flag, val, size, vfunc))
            stream.start()
            self.streams[flag] = stream
        
    def _update_flags(self, flag, enabled: bool, size, value_function=None):
        pos = self.flags_conf[flag][0]
        mask = (2**size - 1) << pos
        value = enabled
        if callable(value_function):
            value = value_function(enabled)
        changed = (self.flags ^ (value << pos)) & mask
        if changed:
            if value:
                self.flags |= mask
            else:
                self.flags &= ~mask
            self.flags_updated = True

    def _send(self, cmd, value):
        packet = f'[{cmd}:{value}]'.encode()
        print(f'sending: {packet}')
        self.arduino.write(packet)

    def send_updates(self):
        if self.flags_updated:
            flags_to_hex = f'{self.flags:0>4X}'
            self._send('f', flags_to_hex)
            self.flags_updated = False
        

def run(state):
    telemetry = Telemetry(state)
    telemetry.init_streams()
    while True:
        telemetry.send_updates()


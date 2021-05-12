from threading import Lock
import time
import krpc
import serial
import math

PORT = 'COM3'
BAUD_RATE = 57600


class Telemetry:
    def __init__(self, shared_state):
        self.shared_state = shared_state
        self.flags = 0
        self.flags_updated = False
        self.flags2 = 0
        self.flags2_updated = False
        self.flags2_lock = Lock()
        self.last_antenna_check = 0

        # arduino
        self.arduino = serial.Serial(PORT, baudrate=BAUD_RATE, timeout=None)  # open serial port
        self._wait_for_arduino()
        
        # krpc
        self.kerbal = krpc.connect(name='telemetry', address='127.0.0.1')
        self.vessel = self.kerbal.space_center.active_vessel
        self.orbit = self.vessel.orbit
        self.flight = self.vessel.flight()

    def _wait_for_arduino(self):
        print("Connecting to Arduino...")
        while True:
            s = self.arduino.read(1)
            if s == b'!':
                print("Connected!")
                break

    def _update_flags(self, pos, value: int, value_func=None):
        mask = 1 << pos
        val = value
        if callable(value_func):
            val = value_func(value)
        changed = (self.flags ^ (val << pos)) & mask
        if changed:
            if val:
                self.flags |= mask
            else:
                self.flags &= ~mask
            self.flags_updated = True

    def _add_flags_stream(self, name, position, parent, attribute, value_func=None, callback=None):
        stream = self.kerbal.add_stream(getattr, parent, attribute)
        # why flag=flag: see https://stackoverflow.com/questions/11087047/deferred-evaluation-with-lambda-in-python
        if not callback:
            callback = lambda val, pos=position, vfunc=value_func: self._update_flags(pos, val, value_func=vfunc)
        stream.add_callback(callback)
        stream.start()

    def init_flags_streams(self):
        self._add_flags_stream('sas', 0, self.vessel.control, 'sas')
        self._add_flags_stream('rcs', 1, self.vessel.control, 'rcs')
        self._add_flags_stream('lights', 2, self.vessel.control, 'lights')
        self._add_flags_stream('brakes', 3, self.vessel.control, 'brakes')
        self._add_flags_stream('contact', 4, self.vessel, 'situation', lambda x: x.name in ['landed', 'splashed', 'pre_launch'])
        self._add_flags_stream('005g', 5, self.flight, 'g_force', lambda x: x > 0.05)
        
        self.init_docking_streams()

    def init_docking_streams(self):
        def callback(value):
            actual = any([d.state.name == 'docked' for d in self.vessel.parts.docking_ports])
            self._update_flags(6, 1, actual)
            
        for d in self.vessel.parts.docking_ports:
            stream = self.kerbal.add_stream(getattr, d, 'state')
            stream.add_callback(callback)
            stream.start()

    def set_flags2(self, states, offset):
        original_flags = self.flags2
        mask = 0b11 << offset
        self.flags2 &= ~mask  # clearing bits we want to set

        if {'retracting', 'extending', 'deploying'} & states:
            self.flags2 |= 0b10 << offset
        elif states < {'extended', 'deployed'}:
            self.flags2 |= 0b11 << offset
        elif states == {'retracted'}:
            self.flags2 |= 0b00 << offset
        else:
            self.flags2 |= 0b01 << offset

        if self.flags2 != original_flags:
            self.flags2_updated = True

    def init_flags2_streams(self):
        def callback_solar(value):
            with self.flags2_lock:
                sp_states = {sp.state.name for sp in self.vessel.parts.solar_panels}
                self.set_flags2(sp_states, offset=0)
        
        for sp in self.vessel.parts.solar_panels:
            stream = self.kerbal.add_stream(getattr, sp, 'state')
            stream.add_callback(callback_solar)
            stream.start()

        def callback_gear(value):
            with self.flags2_lock:
                gear_states = {g.state.name for g in self.vessel.parts.legs}
                self.set_flags2(gear_states, offset=2)

        for g in self.vessel.parts.legs:
            stream = self.kerbal.add_stream(getattr, g, 'state')
            stream.add_callback(callback_gear)
            stream.start()

    def init_streams(self):
        self.init_flags_streams()
        self.init_flags2_streams()

    def check_antenna(self):
        now = time.time()
        if now - self.last_antenna_check >= 1.0:  # checking every 1 sec
            with self.flags2_lock:
                original_flags = self.flags2
                offset = 4
                antenna = math.ceil(self.vessel.comms.signal_strength * 3)
                mask = 0b11 << offset
                self.flags2 &= ~mask
                self.flags2 |= antenna << 4

                if self.flags2 != original_flags:
                    self.flags2_updated = True

            self.last_antenna_check = now

    def check_staging(self):
        self._update_flags(7, 1, self.shared_state.staging)

    def check_non_streamable_data(self):
        self.check_antenna()
        self.check_staging()
        
    def _send(self, cmd, value):
        packet = f'[{cmd}:{value}]'.encode()
        print(f'sending: {packet}')
        self.arduino.write(packet)

    def send_updates(self):
        if self.flags_updated:
            flags_to_hex = f'{self.flags:0>2X}'
            self._send('f', flags_to_hex)
            self.flags_updated = False
        if self.flags2_updated:
            flags_to_hex = f'{self.flags2:0>2X}'
            self._send('g', flags_to_hex)
            with self.flags2_lock:
                self.flags2_updated = False
        

def run(state):
    telemetry = Telemetry(state)
    telemetry.init_streams()
    while True:
        telemetry.check_non_streamable_data()
        telemetry.send_updates()


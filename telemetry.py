from collections import defaultdict
from threading import Lock, RLock
import time
from utils import metricify
import krpc
import serial
import math

PORT = 'COM3'
BAUD_RATE = 57600


class Telemetry:
    def __init__(self, shared_state):
        self.shared_state = shared_state

        self.serial_lock = Lock()

        self.flags = 0
        self.flags_updated = False
        self.flags_lock = Lock()
        self.flags2 = 0
        self.flags2_updated = False
        self.flags2_lock = Lock()
        self.last_antenna_check = 0
        self.last_fuel_check = 0
        self.last_life_support_check = 0
        self.resources = [0, 0, 0, 0, 0]
        self.last_resource_mode = None
        self.display_streams = []
        self.display_data = defaultdict(int)
        self.display_update = defaultdict(int)

        # arduino
        self.arduino = serial.Serial(PORT, baudrate=BAUD_RATE, timeout=None)  # open serial port
        self._wait_for_arduino()
        
        # krpc
        self.kerbal = krpc.connect(name='telemetry', address='127.0.0.1')
        self.vessel = self.kerbal.space_center.active_vessel
        self.orbit = self.vessel.orbit
        self.orbital_flight = self.vessel.flight(self.vessel.orbit.body.reference_frame)
        self.surface_flight = self.vessel.flight(self.vessel.surface_reference_frame)
        self.flight = self.vessel.flight()

    def _wait_for_arduino(self):
        print("Connecting to Arduino...")
        while True:
            s = self.arduino.read(1)
            if s == b'!':
                print("Connected!")
                break

    def _update_flags(self, pos, value: int, value_func=None):
        with self.flags_lock:
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

    def _display_data_callback(self, field, value, format_func=None):
        formatted = value
        if format_func:
            formatted = format_func(value)

        now = time.time()
        if now - self.display_update[field] > 1 and formatted != self.display_data[field]:
            self._send(field, formatted)
            self.display_data[field] = formatted
            self.display_update[field] = now

    def _add_data_stream(self, obj, attr, prefix, format_func=None):
        stream = self.kerbal.add_stream(getattr, obj, attr)
        stream.add_callback(lambda value, f=format_func: self._display_data_callback(prefix, value, f))
        stream.start()
        self.display_streams.append(stream)

    def init_ascent_streams(self):
        self._add_data_stream(self.orbit, 'apoapsis_altitude', 'a', metricify)
        self._add_data_stream(self.orbit, 'periapsis_altitude', 'p', metricify)
        self._add_data_stream(self.orbital_flight, 'vertical_speed', 'v', metricify)
        self._add_data_stream(self.orbital_flight, 'horizontal_speed', 'h', metricify)
        self._add_data_stream(self.orbital_flight, 'mean_altitude', 'A', metricify)

        def round_value(value):
            return '{}'.format(round(value))

        self._add_data_stream(self.surface_flight, 'pitch', 'P', round_value)
        self._add_data_stream(self.orbital_flight, 'dynamic_pressure', 'Q', round_value)

        self.thrust = self.kerbal.add_stream(getattr, self.vessel, 'thrust')
        self.thrust.start()
        stream = self.kerbal.add_stream(getattr, self.orbit, 'body')

        def cb(body):
            self.surface_gravity = body.surface_gravity
        stream.add_callback(cb)
        stream.start()

        def twr_callback(value):
            divisor = value * self.surface_gravity
            twr = round(self.thrust()/divisor if divisor else 0, 1)
            self._display_data_callback('t', twr)

        stream = self.kerbal.add_stream(getattr, self.vessel, 'mass')
        stream.add_callback(twr_callback)
        stream.start()
        self.display_streams.append(stream)

    def init_display_streams(self):
        for s in self.display_streams:
            s.remove()
        
        self.init_ascent_streams()

    def init_streams(self):
        self.init_flags_streams()
        self.init_flags2_streams()
        self.init_display_streams()

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

    def check_fuels(self):
        now = time.time()
        mode_changed = self.last_resource_mode != self.shared_state.resource_mode
        self.last_resource_mode = self.shared_state.resource_mode
        if mode_changed or now - self.last_fuel_check >= 1.0:  # checking every 1 sec
            amount = defaultdict(float)
            max_fuel = defaultdict(float)
            changed = False

            stage = self.vessel.control.current_stage-1
            staged_resources = self.vessel.resources_in_decouple_stage(stage, True)
            total_resources = self.vessel.resources
            resources = (
                ('LiquidFuel', staged_resources),
                ('Oxidizer', staged_resources),
                ('MonoPropellant', total_resources), 
                ('ElectricCharge', total_resources),
                ('XenonGas', staged_resources),
            )
            i = 0
            for r in resources:
                f = r[0]
                amount[f] = r[1].amount(f)
                max_fuel[f] = r[1].max(f)
                
                value = round(amount[f] * 10 / max_fuel[f]) if max_fuel[f] else 0
                if value != self.resources[i]:
                    changed = True
                    self.resources[i] = value

                i += 1

            if changed:
                values_to_hex = "".join([f'{r:0>2X}' for r in self.resources])
                self._send('u', values_to_hex)
            
            self.last_fuel_check = now

    def check_life_support(self):
        now = time.time()
        mode_changed = self.last_resource_mode != self.shared_state.resource_mode
        self.last_resource_mode = self.shared_state.resource_mode
        if mode_changed or now - self.last_life_support_check >= 1.0:  # checking every 1 sec
            amount = defaultdict(float)
            max_ls = defaultdict(float)
            changed = False

            r = self.vessel.resources
            i = 0
            for f in ('Oxygen', 'Water', 'Food', 'CarbonDioxide', 'Waste'):
                amount[f] = r.amount(f)
                max_ls[f] = r.max(f)
                
                value = round(amount[f] * 10 / max_ls[f]) if max_ls[f] else 0
                if value != self.resources[i]:
                    changed = True
                    self.resources[i] = value
                
                i += 1

            if changed:
                values_to_hex = "".join([f'{r:0>2X}' for r in self.resources])
                self._send('l', values_to_hex)
            
            self.last_life_support_check = now

    def check_non_streamable_data(self):
        self.check_antenna()
        self.check_staging()
        if self.shared_state.resource_mode == 'fuel':
            self.check_fuels()
        else:
            self.check_life_support()
        
    def _send(self, cmd, value):
        with self.serial_lock:
            packet = f'[{cmd}:{value}]'.encode()
            print(f'sending: {packet}')
            self.arduino.write(packet)

    def send_flag_updates(self):
        if self.flags_updated:
            flags_to_hex = f'{self.flags:0>2X}'
            self._send('f', flags_to_hex)
            with self.flags_lock:
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
        telemetry.send_flag_updates()
        telemetry.check_non_streamable_data()

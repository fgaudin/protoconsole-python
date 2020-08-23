from enum import IntEnum

import krpc
import serial
import time


PORT = 'COM3'
BAUD_RATE = 115200
TIMEOUT = 1


class Command(IntEnum):
    # 0 -> reserved
    # 1 - 7 -> command without value
    HELLO = 1
    BYE = 2
    # 8 - 31 -> command with 8 bits value
    # flags for solar panel, gear
    # 2 bits per part, 0 = off, 1 = problem, 2 = deploying/retracting, 3 = deployed
    FLAGS1 = 8
    TWR = 9
    PITCH=10
    STAGE_FUEL=11
    STAGE_OX=12
    STAGE_MONOPROP=13
    STAGE_ELEC=14
    STAGE_XENON=15
    STAGE_O2 = 16
    STAGE_HO2 = 17
    STAGE_FOOD = 18
    STAGE_CO2 = 19
    STAGE_WASTE = 20
    # RCS, SAS, brake, docked, lights, antenna
    # 2 bits per part, 0 = off, 1 = problem, 2 = deploying/retracting, 3 = deployed
    FLAGS2 = 21
    # 32 - 63 -> command with 32 bits value
    PERIAPSIS = 32  # 4 bytes value
    APOAPSIS = 33  # 4 bytes value
    ALTITUDE = 34
    VERTICAL_SPEED = 35
    HORIZONTAL_SPEED = 36


class Controller:
    def __init__(self):
        self.kerbal = krpc.connect(name='protoconsole', address='127.0.0.1')
        self.arduino = serial.Serial(PORT, baudrate=BAUD_RATE, timeout=TIMEOUT)  # open serial port
        print(self.arduino.name)  # check which port was really used
        if self.wait_for_board():
            print('Board connected')
        else:
            print("Failed to connect to board")

        self.init_streams()

        self.send_packet(Command.HELLO.value)
        self.loop()
        self.arduino.close()  # close port

    def init_streams(self):
        self.vessel = self.kerbal.space_center.active_vessel
        self.orbit = self.vessel.orbit
        self.orbital_flight = self.vessel.flight(self.vessel.orbit.body.reference_frame)
        self.surface_flight = self.vessel.flight(self.vessel.surface_reference_frame)
        self.apoapsis = self.kerbal.add_stream(getattr, self.orbit, 'apoapsis_altitude')
        self.periapsis = self.kerbal.add_stream(getattr, self.orbit, 'periapsis_altitude')
        self.pitch = self.kerbal.add_stream(getattr, self.surface_flight, 'pitch')
        self.thrust = self.kerbal.add_stream(getattr, self.vessel, 'thrust')
        self.mass = self.kerbal.add_stream(getattr, self.vessel, 'mass')
        self.altitude = self.kerbal.add_stream(getattr, self.orbital_flight, 'mean_altitude')
        self.vertical_speed = self.kerbal.add_stream(getattr, self.orbital_flight, 'vertical_speed')
        self.horizontal_speed = self.kerbal.add_stream(getattr, self.orbital_flight, 'horizontal_speed')

    def twr(self):
        divisor = self.mass() * self.orbit.body.surface_gravity
        return self.thrust()/divisor if divisor else 0

    def stage_resource(self, resource):
        stage = self.vessel.control.current_stage-1
        for i in range(10):
            resources = self.vessel.resources_in_decouple_stage(stage)
            fuel = resources.amount(resource)
            max = resources.max(resource)
            stage -= 1
            if max > 0:
                break
        if max:
            return fuel * 10 / max
        
        return 0

    def stage_fuel(self):
        return self.stage_resource('LiquidFuel')

    def stage_ox(self):
        return self.stage_resource('Oxidizer')

    def stage_monoprop(self):
        return self.stage_resource('MonoPropellant')

    def stage_elec(self):
        return self.stage_resource('ElectricCharge')

    def stage_xenon(self):
        return self.stage_resource('XenonGas')

    def stage_o2(self):
        return self.stage_resource('Oxygen')

    def stage_h2o(self):
        return self.stage_resource('Water')

    def stage_food(self):
        return self.stage_resource('Food')

    def stage_co2(self):
        return self.stage_resource('CarbonDioxide')

    def stage_waste(self):
        return self.stage_resource('Waste')

    def flags1(self):
        # flags for solar panel, gear
        # 2 bits per part
        # 0 = off
        # 1 = problem
        # 2 = deploying/retracting
        # 3 = deployed
        flags = 0

        def set_flag(flags, states, offset):
            if {'retracting', 'deploying'} & states:
                flags |= 2 << offset
            elif states == {'extended'}:
                flags |= 3 << offset
            elif states == {'retracted'}:
                flags |= 0 << offset
            else:
                flags |= 1 << offset
            return flags

        sp_states = {sp.state.name for sp in self.vessel.parts.solar_panels}
        flags = set_flag(flags, sp_states, offset=0)
        gear_states = {g.state.name for g in self.vessel.parts.legs}
        flags = set_flag(flags, gear_states, offset=2)
        
        return flags

    def loop(self):
        while True:
            self.send_packet(Command.PERIAPSIS.value, int(self.periapsis()))
            self.send_packet(Command.APOAPSIS.value, int(self.apoapsis()))
            self.send_packet(Command.ALTITUDE.value, int(self.altitude()))
            self.send_packet(Command.VERTICAL_SPEED.value, int(self.vertical_speed()))
            self.send_packet(Command.HORIZONTAL_SPEED.value, int(self.horizontal_speed()))
            self.send_packet(Command.TWR.value, round(self.twr()*10))
            self.send_packet(Command.PITCH.value, int(self.pitch()))
            self.send_packet(Command.STAGE_FUEL.value, round(self.stage_fuel()))
            self.send_packet(Command.STAGE_OX.value, round(self.stage_ox()))
            self.send_packet(Command.STAGE_MONOPROP.value, round(self.stage_monoprop()))
            self.send_packet(Command.STAGE_ELEC.value, round(self.stage_elec()))
            self.send_packet(Command.STAGE_XENON.value, round(self.stage_xenon()))
            self.send_packet(Command.STAGE_O2.value, round(self.stage_o2()))
            self.send_packet(Command.STAGE_HO2.value, round(self.stage_h2o()))
            self.send_packet(Command.STAGE_FOOD.value, round(self.stage_food()))
            self.send_packet(Command.STAGE_CO2.value, round(self.stage_co2()))
            self.send_packet(Command.STAGE_WASTE.value, round(self.stage_waste()))
            self.send_packet(Command.FLAGS1.value, int(self.flags1()))

            time.sleep(0.5)

    def wait_for_board(self):
        while True:
            s = self.arduino.read(1)
            print(s)
            if s == self._command_to_byte(Command.HELLO.value):
                return True
        
        return False

    def _command_to_byte(self, command):
        return command.to_bytes(1, 'big')

    def send_packet(self, command, value=None):
        print(f"cmd: {command}")
        print(value)
        payload = None
        if command < 8:
            payload = self._command_to_byte(command)
        elif command < 32:
            payload = self._command_to_byte(command) + value.to_bytes(1, 'little', signed=True)
        else:
            payload = self._command_to_byte(command) + value.to_bytes(4, 'little', signed=True)

        self.arduino.write(payload)

def main():
    controller = Controller()


if __name__ == '__main__':
    main()

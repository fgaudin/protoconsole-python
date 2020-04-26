from enum import IntEnum

import krpc
import serial
import time


PORT = 'COM3'
BAUD_RATE = 115200
TIMEOUT = 1


class Command(IntEnum):
    # 0 -> reserved
    # 1 - 63 -> command without value
    HELLO = 1
    BYE = 2
    # 64 - 127 -> command with 8 bits value
    FLAGS1 = 64  # flags for solar panel, gear, docked, lights, RCS, SAS, brake, antenna
    TWR = 70
    PITCH=71
    STAGE_FUEL=72
    # 128 - 191 -> command with 16 bits value

    # 192 - 255 -> command with 32 bits value
    PERIAPSIS = 192  # 4 bytes value
    APOAPSIS = 193  # 4 bytes value
    ALTITUDE = 194
    VERTICAL_SPEED = 195
    HORIZONTAL_SPEED = 196


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
        return self.thrust()/(self.mass() * self.orbit.body.surface_gravity)

    def stage_fuel(self):
        stage = self.vessel.control.current_stage-1
        for i in range(10):
            resources = self.vessel.resources_in_decouple_stage(stage)
            fuel = resources.amount("LiquidFuel")
            max = resources.max("LiquidFuel")
            stage -= 1
            if max > 0:
                break
        if max:
            return fuel * 100 / max
        
        return 0

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
        print(command)
        print(value)
        payload = None
        if command < 64:
            payload = self._command_to_byte(command)
        elif command < 128:
            payload = self._command_to_byte(command) + value.to_bytes(1, 'little', signed=True)
        elif command < 192:
            payload = self._command_to_byte(command) + value.to_bytes(2, 'little', signed=True)
        else:
            payload = self._command_to_byte(command) + value.to_bytes(4, 'little', signed=True)

        self.arduino.write(payload)

def main():
    controller = Controller()


if __name__ == '__main__':
    main()


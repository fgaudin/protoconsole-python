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
    # 128 - 191 -> command with 16 bits value

    # 192 - 255 -> command with 32 bits value
    PERIAPSIS = 192  # 4 bytes value
    APOAPSIS = 193  # 4 bytes value
    ALTITUDE = 194
    VERTICAL_VELOCITY = 195
    HORIZONTAL_VELOCITY = 196


class Controller:
    def __init__(self):
        self.kerbal = krpc.connect(name='protoconsole', address='127.0.0.1')
        vessel = self.kerbal.space_center.active_vessel
        self.arduino = serial.Serial(PORT, baudrate=BAUD_RATE, timeout=TIMEOUT)  # open serial port
        print(self.arduino.name)  # check which port was really used
        if self.wait_for_board():
            print('Board connected')
        else:
            print("Failed to connect to board")

        self.apoapsis = self.kerbal.add_stream(getattr, vessel.orbit, 'apoapsis_altitude')
        self.periapsis = self.kerbal.add_stream(getattr, vessel.orbit, 'periapsis_altitude')

        self.send_packet(Command.HELLO.value)
        self.loop()
        self.arduino.close()  # close port

    def loop(self):
        self.send_packet(Command.PERIAPSIS.value, int(self.periapsis()))
        self.send_packet(Command.APOAPSIS.value, int(self.apoapsis()))
        time.sleep(1)

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
        payload = None
        if command < 64:
            payload = self._command_to_byte(command)
        elif command < 128:
            payload = self._command_to_byte(command) + value.to_bytes(1, 'little'
            )
        elif command < 192:
            payload = self._command_to_byte(command) + value.to_bytes(2, 'little')
        else:
            payload = self._command_to_byte(command) + value.to_bytes(4, 'little')

        self.arduino.write(payload)

def main():
    controller = Controller()


if __name__ == '__main__':
    main()


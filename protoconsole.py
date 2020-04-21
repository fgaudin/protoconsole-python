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
    # 64 - 127 -> command with 8 bits flags value
    FLAGS1 = 64  # solar panel, gear, docked, lights, RCS, SAS, brake, antenna
    # 128 - 191 -> command with 16 bits value

    # 192 - 255 -> command with 32 bits value
    PERIAPSIS = 192  # 4 bytes value
    APOAPSIS = 193  # 4 bytes value


class Controller:
    def __init__(self):
        #self.kerbal = krpc.connect(name='protoconsole', address='192.168.1.195')
        self.arduino = serial.Serial(PORT, baudrate=BAUD_RATE, timeout=TIMEOUT)  # open serial port
        print(self.arduino.name)  # check which port was really used
        #vessel = self.kerbal.space_center.active_vessel
        if self.wait_for_board():
            print('Board connected')
        else:
            print("Failed to connect to board")
        self.send_packet(Command.HELLO.value)
        self.send_packet(Command.BYE.value)
        self.send_packet(Command.FLAGS1.value, 0b01010101)
        self.send_packet(Command.PERIAPSIS.value, 123456789)
        self.arduino.close()  # close port

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


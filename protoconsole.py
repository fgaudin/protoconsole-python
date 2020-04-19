from enum import IntEnum

import krpc
import serial


class Command(IntEnum):
    # 0 - 63 -> command without value
    HELLO = 0
    BYE = 1
    # 64 - 127 -> command with 8 bits flags value
    FLAGS_1 = 64  # solar panel, gear, docked, lights, RCS, SAS, break, antenna
    # 128 - 191 -> command with 16 bits value

    # 192 - 255 -> command with 32 bits value
    PERIAPSIS = 192  # 4 bytes value
    APOAPSIS = 193  # 4 bytes value


class Controller:
    def __init__(self):
        #self.kerbal = krpc.connect(name='protoconsole', address='192.168.1.195')
        self.arduino = serial.Serial('/dev/ttyACM0', baudrate=115200)  # open serial port
        print(self.arduino.name)  # check which port was really used
        #vessel = self.kerbal.space_center.active_vessel
        self.send_packet(Command.FLAGS_1.value)
        self.arduino.close()  # close port

    def send_packet(self, command, value=None):
        self.arduino.write(command.to_bytes(1, 'big'))


def main():
    controller = Controller()


if __name__ == '__main__':
    main()


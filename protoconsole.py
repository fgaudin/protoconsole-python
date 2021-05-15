import threading
import inputs
import telemetry


class InternalState:
    def __init__(self):
        self.staging = False
        self.display_mode = 'ascent'
        self.resource_mode = 'fuel'


if __name__ == '__main__':
    state = InternalState()

    input_th = threading.Thread(target=inputs.run, args=(state,))
    input_th.start()

    telemetry = threading.Thread(target=telemetry.run, args=(state,))
    telemetry.start()

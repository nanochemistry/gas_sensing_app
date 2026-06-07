# src/gas_sensing_app/hardware/mock_drivers.py
import random
import time

class MockKeithley2400:
    def __init__(self, port):
        print(f"[MOCK] Keithley 2400 initialized on virtual port {port}")
        self.four_wire = False
        # Reference a shared state tracker if you want interactive physics simulation
        
    def setup_resistance(self, **kwargs):
        print(f"[MOCK] Keithley configured with settings: {kwargs}")
        self.four_wire = kwargs.get('four_wire', False)

    def get_reading(self) -> float:
        """Simulates fluctuating baseline resistance."""
        baseline = 100.0 if not self.four_wire else 102.5
        return baseline + random.uniform(-0.05, 0.05)

    def close(self):
        print("[MOCK] Keithley connection closed.")


class MockShutterController:
    def __init__(self, port, baud_rate, open_angle=90, closed_angle=0):
        self.open_angle = open_angle
        self.closed_angle = closed_angle
        self.is_open = False
        print(f"[MOCK] Shutter ready on {port} (Baud: {baud_rate})")

    def set_speed(self, speed):
        pass

    def set_open(self, should_open: bool):
        self.is_open = should_open
        state = "OPEN" if should_open else "CLOSED"
        angle = self.open_angle if should_open else self.closed_angle
        print(f"[MOCK] Shutter hardware moved to {state} ({angle}°)")

    def close(self):
        print("[MOCK] Shutter connection closed.")


class MockAeraMFCManager:
    def __init__(self, port, ranges):
        print(f"[MOCK] MFC Manager active on {port} with channel ceilings {ranges}")
        self.current_flows = {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0}

    def set_flow(self, ch: int, flow: float):
        self.current_flows[ch] = float(flow)
        print(f"[MOCK] MFC Ch {ch} physical valve adjusted to {flow} sccm")

    def get_actual_flow(self, ch: int) -> float:
        """Simulates natural gas flow turbulence around the target setpoint."""
        target = self.current_flows.get(ch, 0.0)
        if target == 0.0:
            return 0.0
        return target + random.uniform(-0.2, 0.2)

    def stop_all(self):
        print("[MOCK] Emergency Broadcast: All MFC gas lines zeroed out.")
        self.current_flows = {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0}

    def close(self):
        print("[MOCK] MFC controller connection closed.")
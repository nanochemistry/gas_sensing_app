# src/gas_sensing_app/hardware/shutter.py

import serial
import time

class ShutterController:
    def __init__(self, port='/dev/cu.usbmodem11301', baudrate=115200):
        self.ser = serial.Serial(port, baudrate, timeout=1)
        time.sleep(2)  # Critical: Wait for Arduino to reboot after serial opening
        print(f"Shutter Controller Connected at {port} with baudrate {baudrate}.")

    def _send_command(self, cmd_char, value_str):
        """Internal helper to format and send: <C###>"""
        payload = f"<{cmd_char}{value_str}>"
        self.ser.write(payload.encode('ascii'))
        
        # Read the acknowledgment: [OK###]
        response = self.ser.readline().decode('ascii').strip()
        return response

    def set_position(self, angle):
        """Sets the shutter angle (0-180). Example: <P090>"""
        angle = max(0, min(180, int(angle))) # Safety clamp
        # Format to 3 digits with leading zeros
        val_str = f"{angle:03d}" 
        return self._send_command('P', val_str)

    def set_speed(self, delay_ms):
        """Sets movement delay (0-250ms). 0 = instant."""
        delay = max(0, min(250, int(delay_ms)))
        val_str = f"{delay:03d}"
        return self._send_command('S', val_str)

    def get_position(self):
        """Queries current position: <GPOS>"""
        return self._send_command('G', 'POS')
    
    def shutter_open(self):
        self.set_position(150)  # Example: 150 degrees = fully open
    
    def shutter_close(self):
        self.set_position(40)  # Example: 40 degrees = fully closed

    def close(self):
        self.ser.close()

# --- Manual Test ---
if __name__ == "__main__":
    shutter = ShutterController()
    shutter.set_speed(0)
    shutter.shutter_open()
    print(f"Current Shutter Position: {shutter.get_position()}")
    time.sleep(2)
    shutter.shutter_close()
    print(f"Current Shutter Position: {shutter.get_position()}")
    #print(f"Closing Shutter: {shutter.set_position(40)}")
    shutter.close()
import time
from pymeasure.instruments.proterial import ROD4

class AeraMFCManager:
    def __init__(self, port='ASRL/dev/cu.usbserial-130::INSTR', ranges=None):
        """
        :param port: The PyVISA ressource name
        :param ranges: Dictionary mapping channel index to max sccm, 
                       e.g., {1: 1000, 2: 1000, 3: 200, 4: 200}
        """
        try:
            self.rod4 = ROD4(port)
        except Exception as e:
            print(f"Error connecting to ROD-4: {e}")
            raise

        # Default ranges if none provided
        self.ranges = ranges or {1: 1000, 2: 1000, 3: 200, 4: 200}
        self._initialize_channels()

    def _initialize_channels(self):
        """One-time setup for the ROD-4 unit."""
        print("Initializing Aera ROD-4 Channels...")
        for ch_idx, max_range in self.ranges.items():
            channel = getattr(self.rod4, f"ch_{ch_idx}")
            channel.mfc_range = max_range
            channel.flow_unit_display = 'sccm'
            channel.valve_mode = 'flow'
        print("MFCs Ready.")

    def set_flow(self, channel_idx, sccm):
        """Sets the flow rate in sccm for a specific channel."""
        if channel_idx not in self.ranges:
            print(f"Error: Channel {channel_idx} not configured.")
            return

        max_val = self.ranges[channel_idx]
        if sccm > max_val:
            print(f"Warning: {sccm} sccm exceeds max range ({max_val}) for Ch {channel_idx}. Clamping.")
            sccm = max_val

        channel = getattr(self.rod4, f"ch_{channel_idx}")
        channel.setpoint = sccm / max_val * 100  # Normalize to 0-100% scale 
        print(f"Channel {channel_idx} set to {sccm} sccm.")

    def get_actual_flow(self, channel_idx):
        """Reads the current real-time flow from the MFC."""
        channel = getattr(self.rod4, f"ch_{channel_idx}")
        return channel.actual_flow

    def stop_all(self):
        """Sets all flows to 0 sccm."""
        for i in self.ranges.keys():
            channel = getattr(self.rod4, f"ch_{i}")
            channel.setpoint = 0
        print("All MFC flows set to 0.")

    def close(self):
        """Ensures flows are zeroed before shutting down the connection."""
        print("Shutting down AeraMFCManager...")
        self.stop_all()
        # Brief pause to ensure commands are processed before port closes
        time.sleep(0.5) 
        self.rod4.shutdown()
        print("Connection closed.")


# --- Manual Test ---
if __name__ == "__main__":
    mfc_configs = {1: 1000, 2: 1000, 3: 200, 4: 200}
    mfc = AeraMFCManager(port='/dev/cu.usbserial-130', ranges=mfc_configs)
    
    try:
        # set flow on channel 2 to 432 sccm and read back the actual flow
        mfc.set_flow(2, 432.0) 
        # wait a bit for the flow to stabilize before reading
        time.sleep(10)
        # read the actual flow from channel 2
        print(f"Ch 2 Flow: {mfc.get_actual_flow(2)} sccm")
    finally:
        # Putting close in a finally block ensures 0 sccm even if the test fails
        mfc.close()

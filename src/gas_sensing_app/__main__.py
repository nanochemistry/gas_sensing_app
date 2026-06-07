# src/gas_sensing_app/__main__.py

import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon

# Absolute application package calls
from gas_sensing_app.gui.dashboard import GasSensingDashboard

def main():
    # --- WINDOWS TASKBAR FIX ---
    import os
    if os.name == 'nt':
        import ctypes
        app_id = "mylaboratory.gassensing.dashboard.2026"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    # ---------------------------

    app = QApplication(sys.argv)
    
    # === MAC & GLOBAL DOCK ICON FIX ===
    # This forces macOS to map the graphic directly to the running Dock process
    app.setWindowIcon(QIcon("../assets/sensor_icon.png")) 
    # ==================================

    window = GasSensingDashboard()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
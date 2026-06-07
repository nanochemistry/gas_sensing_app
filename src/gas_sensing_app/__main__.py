# src/gas_sensing_app/__main__.py

import sys
import os
from pathlib import Path
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
    
    SCRIPT_DIR = Path(__file__).resolve().parent # Get the absolute path of the directory containing THIS script file
    ICON_PATH = SCRIPT_DIR / "assets" / "sensor_icon.png"  # Build the exact path to the icon folder
    app.setWindowIcon(QIcon(str(ICON_PATH))) # Load the icon cleanly

    window = GasSensingDashboard()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
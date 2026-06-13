import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from gas_sensing_app.gui.dashboard import GasSensingDashboard

def main():
    # Windows Taskbar unique identification assignment
    if os.name == 'nt':
        import ctypes
        app_id = "nanochemistry.gassensing.dashboard.2026"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)

    app = QApplication(sys.argv)
    
    # Configure application metadata globally across window systems
    app.setApplicationName("Gas Sensing Dashboard")
    app.setApplicationDisplayName("Gas Sensing Dashboard")
    
    # Assign the master runtime icon to the global application process
    app.setWindowIcon(QIcon("assets/sensor_icon.png"))

    window = GasSensingDashboard()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
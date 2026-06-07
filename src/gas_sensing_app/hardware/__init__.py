# src/gas_sensing_app/hardware/__init__.py
import os
import yaml

# Find the absolute path to the directory containing this __init__.py file
current_dir = os.path.dirname(os.path.abspath(__file__))
# Navigate up two levels to reach the root folder where config.yaml lives
root_dir = os.path.abspath(os.path.join(current_dir, "..", "..", ".."))
config_path = os.path.join(root_dir, "config.yaml")

use_mock = True 

if os.path.exists(config_path):
    try:
        with open(config_path, 'r') as f:
            cfg = yaml.safe_load(f)
            use_mock = cfg.get('hardware', {}).get('use_mock', True)
    except Exception:
        pass

if use_mock:
    from .mock_drivers import (
        MockKeithley2400 as Keithley2400,
        MockShutterController as ShutterController,
        MockAeraMFCManager as AeraMFCManager
    )
else:
    # Ensure these match your lowercase filenames!
    from .keithley_2400 import Keithley2400
    from .shutter import ShutterController
    from .aera_mfc import AeraMFCManager

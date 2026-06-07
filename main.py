# main.py (At your repository root folder)
import sys
import os

# Insert the local src directory into python's runtime path mapping list
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# CHANGED: Import main from the __main__.py submodule layout instead of dashboard.py
from gas_sensing_app.__main__ import main

if __name__ == "__main__":
    main()
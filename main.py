# main.py (At your repository root folder)
import sys
import os

# Insert the local src directory into python's runtime path mapping list
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from gas_sensing_app.gui.dashboard import main

if __name__ == "__main__":
    main()
# src/gas_sensing_app/core/worker.py

import time
import yaml
import os
import csv
from PyQt6.QtCore import QThread, pyqtSignal, QMutex

#from src.gas_sensing_app.hardware.keithley_2400 import Keithley2400
#from src.gas_sensing_app.hardware.shutter import ShutterController
#from src.gas_sensing_app.hardware.aera_mfc import AeraMFCManager 
 
from gas_sensing_app.hardware import Keithley2400, ShutterController, AeraMFCManager

# ==============================================================================
# II. BACKGROUND WORKER (Processes State-Based Instructions)
# ==============================================================================
# src/gas_sensing_app/core/worker.py
import os


class ExperimentWorker(QThread):
    data_sig = pyqtSignal(dict)      
    status_sig = pyqtSignal(str)    
    error_sig = pyqtSignal(str)     
    finished_sig = pyqtSignal(str)  

    def __init__(self, config_path=None, recipe_path=None, mode='recipe'):
        
        self.mutex = QMutex()
        super().__init__()
        
        # 1. FIX: Save the incoming mode parameter so line 55 can read it!
        self.mode = mode
        
        # 2. FIX: Initialize this flag so your step loop doesn't crash on 'self.is_running'
        self.is_running = True
        
        # If no explicit absolute path is passed, calculate relative to this code file
        if config_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # Move up two levels: from core/ to gas_sensing_app/ to project_root/
            self.config_path = os.path.abspath(os.path.join(current_dir, "..", "..", "..", "config.yaml"))
        else:
            self.config_path = config_path
            
        # Do the same for the recipe file to prevent it from spawning randomly
        if recipe_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            self.recipe_path = os.path.abspath(os.path.join(current_dir, "..", "..", "..", "dummy_recipe.yaml"))
        else:
            self.recipe_path = recipe_path

    def update_manual_setpoints(self, shutter_open, flow_dict):
        self.mutex.lock()
        self.target_shutter_open = shutter_open
        self.target_flows = flow_dict.copy()  # Create a decoupled snapshot copy
        self.manual_update_pending = True
        self.mutex.unlock()

    def run(self):
        print(f"Starting Background Worker Thread [{self.mode.upper()} MODE]...")
        self.status_sig.emit("Initializing Hardware...")
        
        # Initialize references to None to avoid UnboundLocalErrors
        meter = None
        shutter = None
        mfc = None
        
        try:
            with open(self.config_path, 'r') as f: config = yaml.safe_load(f)
            hw = config['hardware']
            data_cfg = config.get('logging', {}).get('data_log', {})
            log_dir = data_cfg.get('folder', 'data')
            os.makedirs(log_dir, exist_ok=True)
            
            if self.mode == 'recipe':
                with open(self.recipe_path, 'r') as f: recipe = yaml.safe_load(f)
                prefix = data_cfg.get('filename_prefix', 'gas_experiment')
                self.log_path = os.path.join(log_dir, f"{prefix}_{time.strftime('%Y%m%d_%H%M%S')}.csv")
            else:
                self.log_path = os.path.join(log_dir, f"manual_session_{time.strftime('%Y%m%d_%H%M%S')}.csv")
                
        except Exception as e:
            self.error_sig.emit(f"Configuration/File Error: {str(e)}")
            return

        # Instantiate hardware using configuration bounds
        k2400_cfg = hw['keithley_2400']
        shutter_cfg = hw['shutter']
        
        meter = Keithley2400(k2400_cfg['port'])
        shutter = ShutterController(
            shutter_cfg['port'], 
            shutter_cfg.get('baud_rate', 115200),
            open_angle=shutter_cfg.get('open_angle', 90),
            closed_angle=shutter_cfg.get('closed_angle', 0)
        )
        shutter.set_speed(0)
        mfc = AeraMFCManager(hw['mfc_controller']['port'], ranges=hw['mfc_controller']['range_sccm'])

        try:
            meter.setup_resistance(
                auto_range=k2400_cfg.get('auto_range', True), 
                manual_range=k2400_cfg.get('manual_range', None), 
                four_wire=k2400_cfg.get('four_wire', False)
            )
            shutter.set_open(False) # Start safely closed
            
            experiment_start = time.time() # Capture the absolute start time of the experiment sequence
            with open(self.log_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                headers = ["Timestamp", "Elapsed_Seconds", "Mode_Step", "Tick", "Resistance", "MFC1", "MFC2", "MFC3", "MFC4", "Shutter_Open"]
                writer.writerow(headers)

                
                # ----------------- MODE A: AUTOMATED RECIPE -----------------
                if self.mode == 'recipe':
                    for step in recipe['steps']:
                        if not self.is_running:
                            break
        
                        is_open = bool(step.get('shutter_open', False))
                        print(f"Transitioning to Phase Step: {step['name']}")
                        shutter.set_open(is_open)
        
                        # 1. Extract raw flows dict
                        raw_flows = step.get('mfc_flows', {})
        
                        # 2. Defensively normalize all keys to integers to handle user string inputs
                        normalized_flows = {int(k): float(v) for k, v in raw_flows.items()}
        
                        # 3. Explicitly loop through all 4 hardware channels to prevent sticky flows
                        for ch in [1, 2, 3, 4]:
                            target_flow = normalized_flows.get(ch, 0.0)  # Safe fallback to 0.0 if omitted
                            mfc.set_flow(ch, target_flow)
                        
                        self.status_sig.emit(f"Step: {step['name']} ({step['duration']}s)")

                        for second in range(step['duration']):
                            if not self.is_running: break
                            loop_start = time.time()

                            res = meter.get_reading()
                            f1, f2 = mfc.get_actual_flow(1), mfc.get_actual_flow(2)
                            f3, f4 = mfc.get_actual_flow(3), mfc.get_actual_flow(4)
                            
                            curr_time = time.strftime("%Y-%m-%d %H:%M:%S") # Full calendar date + time format
                            elapsed_seconds = int(time.time() - experiment_start) # Calculate exact seconds elapsed from the start
                            
                            row = [curr_time, elapsed_seconds, step['name'], second + 1, res, f1, f2, f3, f4, int(is_open)]
                            writer.writerow(row)
                            csvfile.flush() 

                            self.data_sig.emit({
                                "timestamp": curr_time, "resistance": res, "flows": [f1, f2, f3, f4], "shutter": int(is_open)
                            })
                            time.sleep(max(0, 1.0 - (time.time() - loop_start)))

                # ----------------- MODE B: MANUAL CONTROL OVERRIDE -----------------
                elif self.mode == 'manual':
                    self.status_sig.emit("Live Manual Override Active")
                    tick = 0
                    while self.is_running:
                        loop_start = time.time()
                        tick += 1

                        if self.manual_update_pending:
                            shutter.set_open(self.target_shutter_open)
                            for ch_idx, flow in self.target_flows.items():
                                mfc.set_flow(ch_idx, flow)
                            self.manual_update_pending = False

                        res = meter.get_reading()
                        f1, f2 = mfc.get_actual_flow(1), mfc.get_actual_flow(2)
                        f3, f4 = mfc.get_actual_flow(3), mfc.get_actual_flow(4)

                        curr_time = time.strftime("%Y-%m-%d %H:%M:%S") # Full calendar date + time format
                        elapsed_seconds = int(time.time() - experiment_start) # Calculate exact seconds elapsed from the start

                        row = [curr_time, elapsed_seconds, "MANUAL", tick, res, f1, f2, f3, f4, int(self.target_shutter_open)]
                        writer.writerow(row)
                        csvfile.flush()

                        self.data_sig.emit({
                            "timestamp": curr_time, "resistance": res, "flows": [f1, f2, f3, f4], "shutter": int(self.target_shutter_open)
                        })
                        time.sleep(max(0, 1.0 - (time.time() - loop_start)))

        except Exception as e:
            self.error_sig.emit(f"Runtime Hardware Error: {str(e)}")

        finally:
            print("Cleaning up resources, moving hardware to safe state.")
            self.status_sig.emit("Finished / Safe State.")
            mfc.stop_all()
            shutter.set_open(False)
            meter.close()
            mfc.close()
            shutter.close()
            self.finished_sig.emit(self.log_path)
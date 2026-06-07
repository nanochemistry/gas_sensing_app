# src/gas_sensing_app/core/worker.py

import time
import yaml
import os
import csv
from PyQt6.QtCore import QThread, pyqtSignal
from src.gas_sensing_app.hardware.Keithley_2400 import Keithley2400
from src.gas_sensing_app.hardware.Shutter import ShutterController
from src.gas_sensing_app.hardware.AERA_MFC import AeraMFCManager 
 
# ==============================================================================
# II. BACKGROUND WORKER (Processes State-Based Instructions)
# ==============================================================================
class ExperimentWorker(QThread):
    data_sig = pyqtSignal(dict)      
    status_sig = pyqtSignal(str)    
    error_sig = pyqtSignal(str)     
    finished_sig = pyqtSignal(str)  

    def __init__(self, config_path, recipe_path=None, mode='recipe'):
        super().__init__()
        self.config_path = config_path
        self.recipe_path = recipe_path
        self.mode = mode  
        self.is_running = True
        self.log_path = ""
        
        # Thread-safe cross-talk properties
        self.target_shutter_open = False  # Boolean state variable
        self.target_flows = {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0}
        self.manual_update_pending = False

    def update_manual_setpoints(self, shutter_open, flow_dict):
        self.target_shutter_open = shutter_open
        self.target_flows = flow_dict
        self.manual_update_pending = True

    def run(self):
        print(f"Starting Background Worker Thread [{self.mode.upper()} MODE]...")
        self.status_sig.emit("Initializing Hardware...")
        
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

            with open(self.log_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                headers = ["Timestamp", "Mode_Step", "Tick", "Resistance", "MFC1", "MFC2", "MFC3", "MFC4", "Shutter_Open"]
                writer.writerow(headers)

                # ----------------- MODE A: AUTOMATED RECIPE -----------------
                if self.mode == 'recipe':
                    for step in recipe['steps']:
                        if not self.is_running: break
                        
                        # Extract the step boolean parameter (fallback to False if missing)
                        is_open = bool(step.get('shutter_open', False))
                        print(f"Transitioning to Phase Step: {step['name']}")
                        shutter.set_open(is_open)
                        
                        for ch_idx, flow in step.get('mfc_flows', {}).items():
                            mfc.set_flow(int(ch_idx), flow)
                        
                        self.status_sig.emit(f"Step: {step['name']} ({step['duration']}s)")

                        for second in range(step['duration']):
                            if not self.is_running: break
                            loop_start = time.time()

                            res = meter.get_reading()
                            f1, f2 = mfc.get_actual_flow(1), mfc.get_actual_flow(2)
                            f3, f4 = mfc.get_actual_flow(3), mfc.get_actual_flow(4)
                            
                            curr_time = time.strftime("%H:%M:%S")
                            row = [curr_time, step['name'], second + 1, res, f1, f2, f3, f4, int(is_open)]
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
                        
                        curr_time = time.strftime("%H:%M:%S")
                        row = [curr_time, "MANUAL", tick, res, f1, f2, f3, f4, int(self.target_shutter_open)]
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
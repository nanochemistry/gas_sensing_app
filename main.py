import sys
import time
import yaml
import os
import csv
import queue  
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QFileDialog, 
                             QFrame, QSplitter, QTextEdit, QCheckBox, QTabWidget,
                             QSpinBox, QGridLayout, QGroupBox)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer
import pyqtgraph as pg
from PyQt6.QtGui import QIcon
from PyQt6.QtGui import QFontDatabase

# ==============================================================================
# O. GLOBAL PRINT INTERCEPTOR (Thread-Safe Queue Approach)
# ==============================================================================
class WriteStream:
    def __init__(self, original_stream, log_file=None, text_queue=None):
        self.original_stream = original_stream
        self.log_file = log_file
        self.text_queue = text_queue
        self._prevent_loop = False  

    def write(self, text):
        if self._prevent_loop:
            self.original_stream.write(text)
            return
        self._prevent_loop = True
        try:
            self.original_stream.write(text)
            if self.log_file:
                self.log_file.write(text)
                self.log_file.flush()
            if self.text_queue and text:
                self.text_queue.put(text)
        finally:
            self._prevent_loop = False

    def flush(self):
        self.original_stream.flush()
        if self.log_file:
            self.log_file.flush()


# ==============================================================================
# I. REFACTORED SHUTTER DRIVER (State-Based Abstracted Interface)
# ==============================================================================
class Keithley2400:
    def __init__(self, p): print(f"[Driver] Keithley 2400 ready on {p}")
    def setup_resistance(self, **k): print(f"[Driver] Keithley configured: {k}")
    def get_reading(self): import random; return random.uniform(100, 105)
    def close(self): pass

class ShutterController:
    """Manages shutter movements using logical Open/Closed states."""
    def __init__(self, port, baud_rate, open_angle=90, closed_angle=0):
        self.open_angle = open_angle
        self.closed_angle = closed_angle
        print(f"[Driver] Shutter ready on {port} (Configured Open: {open_angle}°, Closed: {closed_angle}°)")
        
    def set_speed(self, s): 
        pass
        
    def set_open(self, should_open: bool):
        """Maps a boolean state to the internally defined calibration angles."""
        target_angle = self.open_angle if should_open else self.closed_angle
        state_str = "OPEN" if should_open else "CLOSED"
        print(f"[Driver] Shutter moving to state: {state_str} (Physical Target: {target_angle}°)")

    def close(self): 
        pass

class AeraMFCManager:
    def __init__(self, p, ranges): pass
    def set_flow(self, ch, f): print(f"[Driver] MFC Ch {ch} set to {f} sccm")
    def get_actual_flow(self, ch): import random; return random.uniform(10, 15)
    def stop_all(self): pass
    def close(self): pass


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


# ==============================================================================
# III. MAIN GUI WINDOW
# ==============================================================================
class GasSensingDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gas Sensing Dashboard 2026")
        self.resize(1400, 850) 
        
        self.setWindowIcon(QIcon("assets/sensor_icon.png")) # icon path (ensure you have an appropriate icon file in the assets folder)
        
        self.system_mono = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family() # Programmatically get 'Consolas' on Win, 'Menlo' on Mac, 'DejaVu' on Linux

        self.config_path = "config.yaml" 
        self.recipe_path = None
        self.log_file_obj = None  
        self.data_history = {"time": [], "resistance": [], "flows": [[], [], [], []], "shutter": []}
        self.console_queue = queue.Queue()

        self._create_dummy_files()
        self._setup_print_logging()

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        # LEFT PANEL
        left_panel = QVBoxLayout()
        left_frame = QFrame()
        left_frame.setFrameShape(QFrame.Shape.StyledPanel)
        left_frame.setLayout(left_panel)

        self.status_label = QLabel("Status: Idle / Ready")
        self.status_label.setStyleSheet("font-weight: bold; color: #34495e; padding: 5px; font-size: 13px;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        res_indicator_layout = QVBoxLayout()
        res_indicator_layout.addWidget(QLabel("Current Resistance:"))
        self.res_display = QLabel("--- Ω")
        
        # Resistance Display
        self.res_display.setStyleSheet(f"font-size: 32px; font-family: '{self.system_mono}'; color: #2c3e50; border: 2px solid #bdc3c7; padding: 10px; background: white;")
        self.res_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        res_indicator_layout.addWidget(self.res_display)

        # TAB LAYOUT CONTROLS
        self.control_tabs = QTabWidget()
        
        # TAB 1: AUTOMATED RECIPE
        recipe_tab = QWidget()
        recipe_layout = QVBoxLayout(recipe_tab)
        self.load_recipe_btn = QPushButton("Load YAML Recipe...")
        self.load_recipe_btn.setStyleSheet("height: 35px;")
        self.load_recipe_btn.clicked.connect(self.select_recipe)
        self.start_recipe_btn = QPushButton("RUN RECIPE")
        self.start_recipe_btn.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; height: 45px;")
        self.start_recipe_btn.setEnabled(False) 
        self.start_recipe_btn.clicked.connect(self.start_recipe_mode)
        recipe_layout.addWidget(QLabel("Recipe Automation Controls:"))
        recipe_layout.addWidget(self.load_recipe_btn)
        recipe_layout.addSpacing(10)
        recipe_layout.addWidget(self.start_recipe_btn)
        recipe_layout.addStretch()

        # TAB 2: MANUAL OVERRIDE CONTROL
        manual_tab = QWidget()
        manual_layout = QVBoxLayout(manual_tab)
        self.start_manual_btn = QPushButton("START MANUAL SESSION")
        self.start_manual_btn.setStyleSheet("background-color: #2980b9; color: white; font-weight: bold; height: 35px;")
        self.start_manual_btn.clicked.connect(self.start_manual_mode)

        input_group = QGroupBox("Manual Target Adjustments")
        grid = QGridLayout(input_group)
        
        grid.addWidget(QLabel("MFC 1 (sccm):"), 0, 0)
        self.mfc1_val = QSpinBox(); self.mfc1_val.setRange(0, 2000); grid.addWidget(self.mfc1_val, 0, 1)
        grid.addWidget(QLabel("MFC 2 (sccm):"), 1, 0)
        self.mfc2_val = QSpinBox(); self.mfc2_val.setRange(0, 2000); grid.addWidget(self.mfc2_val, 1, 1)
        grid.addWidget(QLabel("MFC 3 (sccm):"), 2, 0)
        self.mfc3_val = QSpinBox(); self.mfc3_val.setRange(0, 500); grid.addWidget(self.mfc3_val, 2, 1)
        grid.addWidget(QLabel("MFC 4 (sccm):"), 3, 0)
        self.mfc4_val = QSpinBox(); self.mfc4_val.setRange(0, 500); grid.addWidget(self.mfc4_val, 3, 1)
        
        # CHANGED: Replaced the angular numeric QSpinBox with a clean operational checkbox
        grid.addWidget(QLabel("Shutter Control:"), 4, 0)
        self.shutter_checkbox = QCheckBox("Open Shutter")
        self.shutter_checkbox.setStyleSheet("font-weight: bold;")
        grid.addWidget(self.shutter_checkbox, 4, 1)

        self.apply_manual_btn = QPushButton("Apply Setpoint Changes")
        self.apply_manual_btn.setStyleSheet("background-color: #8e44ad; color: white; font-weight: bold; height: 35px;")
        self.apply_manual_btn.setEnabled(False)
        self.apply_manual_btn.clicked.connect(self.apply_manual_changes)

        manual_layout.addWidget(self.start_manual_btn)
        manual_layout.addWidget(input_group)
        manual_layout.addWidget(self.apply_manual_btn)
        manual_layout.addStretch()

        self.stop_btn = QPushButton("STOP ENGINE (Emergency)")
        self.stop_btn.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold; height: 40px;")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_experiment)

        console_layout = QVBoxLayout()
        console_layout.addWidget(QLabel("Live System Console Log:"))
        
        # Live System Console Log 
        self.console_display = QTextEdit()
        self.console_display.setReadOnly(True)
        self.console_display.setStyleSheet(f"background-color: #1e1e1e; color: #64e314; font-family: '{self.system_mono}'; font-size: 11px;")
        console_layout.addWidget(self.console_display)

        self.control_tabs.addTab(recipe_tab, "Automated Recipe")
        self.control_tabs.addTab(manual_tab, "Manual Overrides")

        left_panel.addWidget(self.status_label)
        left_panel.addLayout(res_indicator_layout)
        left_panel.addSpacing(10)
        left_panel.addWidget(self.control_tabs)
        left_panel.addWidget(self.stop_btn)
        left_panel.addSpacing(10)
        left_panel.addLayout(console_layout, stretch=1)

        # RIGHT PANEL: GRAPH MATRIX
        graph_splitter = QSplitter(Qt.Orientation.Vertical)
        
        self.res_plot = pg.PlotWidget(title="1. Sensor Resistance Data Loop (R vs. t)")
        self.res_plot.showGrid(x=True, y=True)
        self.res_curve = self.res_plot.plot(pen=pg.mkPen(color='#3498db', width=2))
        graph_splitter.addWidget(self.res_plot)

        mfc_container = QWidget()
        mfc_box_layout = QVBoxLayout(mfc_container)
        mfc_box_layout.setContentsMargins(0,0,0,0)

        self.mfc_plot = pg.PlotWidget(title="2. MFC Gas Flows & Shutter Profiles")
        self.mfc_plot.showGrid(x=True, y=True)
        self.mfc_plot.setLabel('left', 'Gas Flow Speed', units='sccm')
        self.mfc_plot.setLabel('bottom', 'Elapsed Timeline Counter', units='s')
        
        self.res_plot.setXLink(self.mfc_plot)
        
        # Secondary Y-Axis for Shutter State Tracking
        self.shutter_view = pg.ViewBox()
        self.mfc_plot.scene().addItem(self.shutter_view)
        self.mfc_plot.getAxis('right').linkToView(self.shutter_view)
        self.shutter_view.setXLink(self.mfc_plot)
        
        # CHANGED: The right axis label now scales cleanly from 0 (Closed) to 1 (Open)
        self.mfc_plot.getAxis('right').setLabel('Shutter State', units='1=Open, 0=Closed')
        self.shutter_view.setYRange(-0.1, 1.1, padding=0) # Keeps the binary square waves clean
        
        self.shutter_curve = pg.PlotCurveItem(
            pen=pg.mkPen(color=(142, 68, 173, 200), width=1.5, style=Qt.PenStyle.DashLine),
            fillLevel=0.0, brush=pg.mkBrush(142, 68, 173, 35)
        )
        self.shutter_view.addItem(self.shutter_curve)
        self.mfc_plot.getViewBox().sigResized.connect(self.sync_secondary_axis_views)

        mfc_colors = ['#e67e22', '#f1c40f', '#1abc9c', '#2ecc71']
        self.mfc_curves = [self.mfc_plot.plot(pen=pg.mkPen(color=c, width=1.8)) for c in mfc_colors]
        mfc_box_layout.addWidget(self.mfc_plot)

        legend_layout = QHBoxLayout()
        legend_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        items_to_toggle = [
            ("MFC 1", mfc_colors[0], self.mfc_curves[0]), ("MFC 2", mfc_colors[1], self.mfc_curves[1]),
            ("MFC 3", mfc_colors[2], self.mfc_curves[2]), ("MFC 4", mfc_colors[3], self.mfc_curves[3]),
            ("Shutter State", "#8e44ad", self.shutter_curve)
        ]
        for name, color, plot_item in items_to_toggle:
            cb = QCheckBox(name); cb.setChecked(True)
            cb.setStyleSheet(f"QCheckBox {{ color: {color}; font-weight: bold; margin-right: 15px; }}")
            cb.stateChanged.connect(lambda state, item=plot_item: item.setVisible(bool(state)))
            legend_layout.addWidget(cb)
            
        mfc_box_layout.addLayout(legend_layout)
        graph_splitter.addWidget(mfc_container)

        graph_splitter.setSizes([350, 650])
        main_layout.addWidget(left_frame, 2) 
        main_layout.addWidget(graph_splitter, 4) 

        self.queue_timer = QTimer(self)
        self.queue_timer.timeout.connect(self.flush_console_queue)
        self.queue_timer.start(100) 

    def sync_secondary_axis_views(self):
        self.shutter_view.setGeometry(self.mfc_plot.getViewBox().sceneBoundingRect())
        self.shutter_view.linkedViewChanged(self.mfc_plot.getViewBox(), pg.ViewBox.XAxis)

    def _setup_print_logging(self):
        try:
            with open(self.config_path, 'r') as f: config = yaml.safe_load(f)
            console_cfg = config.get('logging', {}).get('console_log', {})
            if console_cfg.get('enabled', False):
                log_dir = console_cfg.get('folder', 'console_logs')
                prefix = console_cfg.get('filename_prefix', 'system_console')
                os.makedirs(log_dir, exist_ok=True)
                self.log_file_obj = open(os.path.join(log_dir, f"{prefix}_{time.strftime('%Y%m%d_%H%M%S')}.log"), 'a', encoding='utf-8')
        except Exception as e:
            sys.__stdout__.write(f"Failed setting up print redirection: {e}\n")

        sys.stdout = WriteStream(sys.stdout, self.log_file_obj, self.console_queue)
        sys.stderr = WriteStream(sys.stderr, self.log_file_obj, self.console_queue)

    def flush_console_queue(self):
        text_to_append = ""
        while not self.console_queue.empty():
            try: text_to_append += self.console_queue.get_nowait()
            except queue.Empty: break
        if text_to_append:
            cursor = self.console_display.textCursor(); cursor.movePosition(cursor.MoveOperation.End)
            cursor.insertText(text_to_append); self.console_display.setTextCursor(cursor)
            self.console_display.ensureCursorVisible()

    def select_recipe(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select YAML Recipe", "", "YAML Files (*.yaml)")
        if file:
            self.recipe_path = file
            self.status_label.setText(f"Loaded: {os.path.basename(file)}")
            self.status_label.setStyleSheet("font-weight: bold; color: #27ae60;")
            self.start_recipe_btn.setEnabled(True)

    def prepare_data_arrays(self):
        self.data_history = {"time": [], "resistance": [], "flows": [[], [], [], []], "shutter": []}
        self.res_curve.setData([], [])
        self.shutter_curve.setData([], [])
        for curve in self.mfc_curves: curve.setData([], [])

    def start_recipe_mode(self):
        self.prepare_data_arrays()
        self.worker = ExperimentWorker(self.config_path, self.recipe_path, mode='recipe')
        self.connect_and_start_worker()
        self.control_tabs.setTabEnabled(1, False) 
        self.start_recipe_btn.setEnabled(False)
        self.load_recipe_btn.setEnabled(False)

    def start_manual_mode(self):
        self.prepare_data_arrays()
        self.worker = ExperimentWorker(self.config_path, mode='manual')
        self.connect_and_start_worker()
        self.control_tabs.setTabEnabled(0, False) 
        self.start_manual_btn.setEnabled(False)
        self.apply_manual_btn.setEnabled(True)
        self.apply_manual_changes()

    def connect_and_start_worker(self):
        self.worker.data_sig.connect(self.update_live_data)
        self.worker.status_sig.connect(self.update_status)
        self.worker.error_sig.connect(self.handle_worker_error)
        self.worker.finished_sig.connect(self.on_experiment_finished)
        self.stop_btn.setEnabled(True)
        self.worker.start()

    def apply_manual_changes(self):
        if hasattr(self, 'worker') and self.worker.isRunning():
            flow_targets = {
                1: self.mfc1_val.value(), 2: self.mfc2_val.value(),
                3: self.mfc3_val.value(), 4: self.mfc4_val.value()
            }
            # CHANGED: Extracts the manual targets directly as a clean boolean state flag
            shutter_open_target = self.shutter_checkbox.isChecked()
            self.worker.update_manual_setpoints(shutter_open_target, flow_targets)
            print(f"[Manual Mode Update]: Staging Shutter_Open={shutter_open_target}, Flows={list(flow_targets.values())}")

    def update_live_data(self, data):
        self.res_display.setText(f"{data['resistance']:.4e} Ω")
        elapsed_t = len(self.data_history['time'])
        self.data_history['time'].append(elapsed_t)
        
        self.data_history['resistance'].append(data['resistance'])
        self.res_curve.setData(self.data_history['time'], self.data_history['resistance'])
        
        self.data_history['shutter'].append(data['shutter'])
        self.shutter_curve.setData(self.data_history['time'], self.data_history['shutter'])
        
        for i in range(4):
            self.data_history['flows'][i].append(data['flows'][i])
            self.mfc_curves[i].setData(self.data_history['time'], self.data_history['flows'][i])

    def update_status(self, text): self.status_label.setText(text)
    def handle_worker_error(self, err): print(f"[CRITICAL WARNING]: {err}"); self.stop_experiment()
    def stop_experiment(self):
        if hasattr(self, 'worker') and self.worker.isRunning(): self.worker.is_running = False

    def on_experiment_finished(self, log_path):
        self.stop_btn.setEnabled(False)
        self.apply_manual_btn.setEnabled(False)
        self.control_tabs.setTabEnabled(0, True)
        self.control_tabs.setTabEnabled(1, True)
        self.start_manual_btn.setEnabled(True)
        if self.recipe_path: self.start_recipe_btn.setEnabled(True)
        self.load_recipe_btn.setEnabled(True)
        print(f"Hardware loop cleanly halted. Session log saved to: {log_path}")

    def closeEvent(self, event):
        sys.stdout = sys.__stdout__; sys.stderr = sys.__stderr__
        if self.log_file_obj: self.log_file_obj.close()
        super().closeEvent(event)

    def _create_dummy_files(self):
        if not os.path.exists(self.config_path):
            config = {
                'hardware': {
                    'keithley_2400': {'port': 'MOCK_PORT', 'auto_range': False, 'manual_range': 200000, 'four_wire': True},
                    'shutter': {'port': 'MOCK_SHUTTER', 'baud_rate': 115200, 'open_angle': 90, 'closed_angle': 0},
                    'mfc_controller': {'port': 'MOCK_MFC', 'range_sccm': {1: 1000, 2: 1000, 3: 200, 4: 200}}
                },
                'logging': {
                    'data_log': {'folder': 'data', 'filename_prefix': 'gas_experiment'},
                    'console_log': {'enabled': True, 'folder': 'console_logs', 'filename_prefix': 'system_console'}
                }
            }
            with open(self.config_path, 'w') as f: yaml.dump(config, f)

        # CHANGED: The automatically generated mock recipe file now tracks state parameters cleanly!
        self.recipe_path = "dummy_recipe.yaml"
        if not os.path.exists(self.recipe_path):
            recipe = {
                'steps': [
                    {'name': 'Purge_Phase', 'duration': 4, 'shutter_open': False, 'mfc_flows': {1: 120, 2: 10}},
                    {'name': 'Expose_Gas', 'duration': 6, 'shutter_open': True, 'mfc_flows': {1: 50, 3: 180}},
                    {'name': 'Recovery_Phase', 'duration': 4, 'shutter_open': False, 'mfc_flows': {1: 120, 2: 10}}
                ]
            }
            with open(self.recipe_path, 'w') as f: yaml.dump(recipe, f)

if __name__ == "__main__":
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
    app.setWindowIcon(QIcon("assets/sensor_icon.png")) 
    # ==================================

    window = GasSensingDashboard()
    window.show()
    sys.exit(app.exec())
    
from pathlib import Path
import importlib
import pyqtgraph as pg

STYLE_DIR = Path(__file__).parent.parent / "assets" / "styles"
DEFAULT_THEME = "dark"

def apply_pyqtgraph_theme(theme):
    module = importlib.import_module(
        f"gas_sensing_app.themes.{theme}"
    )

    for key, value in module.PYQTGRAPH_CONFIG.items():
        pg.setConfigOption(key, value)

def load_theme(theme: str = DEFAULT_THEME) -> str:
    files = [
        "base.qss",
        f"{theme}.qss"
    ]
    
    stylesheet = ""
    
    for file in files:
        file_style_path = STYLE_DIR / file
        if not file_style_path.exists(): 
            print(f"[Error] Failed to load style: {theme}")
            continue
        stylesheet += file_style_path.read_text() + "\n"
        
    return stylesheet
    
from pathlib import Path

STYLE_DIR = Path(__file__).parent.parent / "assets" / "styles"
DEFAULT_THEME = "dark"

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
    
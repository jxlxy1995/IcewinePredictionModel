from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "local_data" / "icewine_prediction.sqlite3"
BEIJING_TIMEZONE = "Asia/Shanghai"

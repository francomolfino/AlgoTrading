from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path


DEFAULT_SETTINGS_PATH = Path("configs/ui_settings.json")


@dataclass(frozen=True)
class UISettings:
    data_dir: str = "data/raw"
    experiments_dir: str = "experiments"
    default_tickers: str = "SPY QQQ BTC-USD ETH-USD"
    benchmark: str = "buy_and_hold"
    initial_capital: float = 10_000.0
    commission_bps: float = 1.0
    slippage_bps: float = 2.0
    interval: str = "1d"
    debug: bool = False


def load_ui_settings(path: Path | str = DEFAULT_SETTINGS_PATH) -> UISettings:
    settings_path = Path(path)
    if not settings_path.exists():
        return UISettings()
    payload = json.loads(settings_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("La configuracion UI debe ser un objeto JSON.")
    defaults = asdict(UISettings())
    defaults.update(payload)
    return UISettings(**defaults)


def save_ui_settings(settings: UISettings, path: Path | str = DEFAULT_SETTINGS_PATH) -> Path:
    settings_path = Path(path)
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(asdict(settings), indent=2, sort_keys=True), encoding="utf-8")
    return settings_path

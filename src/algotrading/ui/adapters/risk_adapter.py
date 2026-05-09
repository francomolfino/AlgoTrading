from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskSettings:
    position_fraction: float = 1.0
    max_total_exposure: float = 1.0
    max_drawdown_pct: float | None = None
    max_trades_per_day: int | None = None
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None
    volatility_target_pct: float | None = None
    volatility_window: int = 20


def validate_risk_settings(settings: RiskSettings) -> list[str]:
    warnings: list[str] = []
    if not 0 < settings.position_fraction <= 1:
        raise ValueError("El position sizing debe estar entre 1% y 100%.")
    if not 0 < settings.max_total_exposure <= 1:
        raise ValueError("La exposicion maxima debe estar entre 1% y 100%.")
    if settings.position_fraction > settings.max_total_exposure:
        warnings.append("El position sizing supera la exposicion maxima; se va a capear.")
    if settings.max_drawdown_pct is not None and not 0 < settings.max_drawdown_pct < 1:
        raise ValueError("El max drawdown permitido debe estar entre 1% y 99%.")
    if settings.max_trades_per_day is not None and settings.max_trades_per_day < 0:
        raise ValueError("El limite de trades por dia no puede ser negativo.")
    if settings.stop_loss_pct is not None and not 0 < settings.stop_loss_pct < 1:
        raise ValueError("El stop loss debe estar entre 1% y 99%.")
    if settings.take_profit_pct is not None and settings.take_profit_pct <= 0:
        raise ValueError("El take profit debe ser mayor a cero.")
    if settings.volatility_target_pct is not None and settings.volatility_target_pct <= 0:
        raise ValueError("El volatility target debe ser mayor a cero.")
    if settings.volatility_window <= 1:
        raise ValueError("La ventana de volatilidad debe ser mayor a uno.")

    if settings.position_fraction > 0.8:
        warnings.append("Usar mas del 80% del capital por entrada es agresivo.")
    if settings.max_total_exposure > 0.9:
        warnings.append("La exposicion maxima esta cerca de 100%; revisa drawdown y liquidez.")
    if settings.stop_loss_pct is not None and settings.stop_loss_pct < 0.03:
        warnings.append("Stop loss muy ajustado: puede dispararse por ruido normal.")
    if settings.take_profit_pct is not None and settings.take_profit_pct < 0.03:
        warnings.append("Take profit muy ajustado: puede cortar trades antes de tiempo.")
    return warnings

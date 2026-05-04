"""Cron entrypoint for the Alpaca majors leg."""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from core.kill_switch import current_state
from core.notifications import send
from core.phase import current_phase
from core.risk_gates import run_universal_gates
from core.sizing import position_size_majors
from core.types import AccountState, OrderIntent
from majors.alpaca_client import AlpacaClient, AlpacaError, AlpacaOrder, AlpacaPosition
from majors.executor import execute_buy
from majors.strategy import compute_signal
from majors.trail import compute_new_stop

DEFAULT_UNIVERSE = ["BTC/USD", "ETH/USD", "SOL/USD", "DOGE/USD", "AVAX/USD", "LINK/USD", "UNI/USD"]


@dataclass(frozen=True)
class ScannerConfig:
    universe: list[str]
    memory_dir: Path
    daily_loss_limit_pct: Decimal
    drawdown_limit_pct: Decimal
    max_positions: int
    max_position_pct: Decimal
    rate_limit_per_hour: int
    intended_position_pct: Decimal
    max_spread_pct: Decimal
    alpaca_api_key: str
    alpaca_secret_key: str
    alpaca_base_url: str
    alpaca_data_url: str
    telegram_token: str | None
    telegram_chat_id: str | None


@dataclass(frozen=True)
class ScanReport:
    aborted_reason: str | None
    entries_placed: int
    entries_skipped_by_gate: int
    trails_tightened: int
    errors: list[str]


def run_scan(config: ScannerConfig, now: datetime | None = None) -> ScanReport:
    when = now or datetime.now(UTC)
    kill_path = config.memory_dir / "KILL-SWITCH.md"
    phase_path = config.memory_dir / "PHASE.md"
    monitor_log_path = config.memory_dir / "MONITOR-LOG.md"
    notifications_path = config.memory_dir / "NOTIFICATIONS.md"
    trade_log_path = config.memory_dir / "TRADE-LOG.md"

    kill_switch_state = current_state(kill_path)
    if kill_switch_state != "ACTIVE":
        send(
            f"[majors-scanner] kill switch is {kill_switch_state}; skipping tick",
            urgency="info",
            telegram_token=config.telegram_token,
            telegram_chat_id=config.telegram_chat_id,
            fallback_path=notifications_path,
        )
        return ScanReport(
            aborted_reason=f"kill_switch_{kill_switch_state}",
            entries_placed=0,
            entries_skipped_by_gate=0,
            trails_tightened=0,
            errors=[],
        )

    client = AlpacaClient(
        api_key=config.alpaca_api_key,
        secret_key=config.alpaca_secret_key,
        base_url=config.alpaca_base_url,
        data_url=config.alpaca_data_url,
    )

    try:
        account = client.get_account()
        positions = client.list_positions()
        open_orders = client.list_open_orders()
    except AlpacaError as exc:
        send(
            f"[majors-scanner] Alpaca read failed: {exc}",
            urgency="alert",
            telegram_token=config.telegram_token,
            telegram_chat_id=config.telegram_chat_id,
            fallback_path=notifications_path,
        )
        return ScanReport(
            aborted_reason=f"alpaca_read_error:{exc}",
            entries_placed=0,
            entries_skipped_by_gate=0,
            trails_tightened=0,
            errors=[str(exc)],
        )

    errors: list[str] = []
    trails_tightened = _manage_trailing_stops(client, positions, open_orders, when, errors)
    entries_placed, entries_skipped = _scan_entries(
        client=client,
        config=config,
        when=when,
        account=account,
        positions=positions,
        open_orders=open_orders,
        kill_switch_state=kill_switch_state,
        phase=current_phase(phase_path),
        monitor_log_path=monitor_log_path,
        trade_log_path=trade_log_path,
        errors=errors,
    )

    send(
        (
            f"[majors-scanner] entries={entries_placed} skipped={entries_skipped} "
            f"trails={trails_tightened} errors={len(errors)}"
        ),
        urgency="alert" if errors else "info",
        telegram_token=config.telegram_token,
        telegram_chat_id=config.telegram_chat_id,
        fallback_path=notifications_path,
    )
    return ScanReport(
        aborted_reason=None,
        entries_placed=entries_placed,
        entries_skipped_by_gate=entries_skipped,
        trails_tightened=trails_tightened,
        errors=errors,
    )


def _manage_trailing_stops(
    client: AlpacaClient,
    positions: list[AlpacaPosition],
    open_orders: list[AlpacaOrder],
    when: datetime,
    errors: list[str],
) -> int:
    stop_orders_by_symbol = {
        order.symbol: order
        for order in open_orders
        if order.type == "stop_limit" and order.side == "sell"
    }
    tightened = 0
    for position in positions:
        existing = stop_orders_by_symbol.get(position.symbol)
        if existing is None or existing.stop_price is None:
            continue
        new_stop = compute_new_stop(
            entry=position.avg_entry_price,
            current_price=position.current_price,
            current_stop=existing.stop_price,
        )
        if new_stop is None:
            continue
        try:
            client.cancel_order(existing.id)
            client.place_stop_limit_sell(
                symbol=position.symbol,
                qty=position.qty,
                stop_price=new_stop,
                limit_price=(new_stop * Decimal("0.999")).quantize(Decimal("0.01")),
                client_order_id=f"majors-{position.symbol}-trail-{when:%Y%m%dT%H%M}",
            )
            tightened += 1
        except AlpacaError as exc:
            errors.append(f"trail {position.symbol}: {exc}")
    return tightened


def _scan_entries(
    *,
    client: AlpacaClient,
    config: ScannerConfig,
    when: datetime,
    account: Any,
    positions: list[AlpacaPosition],
    open_orders: list[AlpacaOrder],
    kill_switch_state: str,
    phase: str,
    monitor_log_path: Path,
    trade_log_path: Path,
    errors: list[str],
) -> tuple[int, int]:
    held_symbols = {position.symbol for position in positions}
    gate_state = AccountState(
        equity=account.equity,
        cash=account.cash,
        venue="alpaca",
        day_pl_pct=Decimal("0"),
        phase_pl_pct=Decimal("0"),
        open_positions_count=len(positions),
        trades_last_hour=_count_recent_trades(open_orders),
    )
    entries_placed = 0
    entries_skipped = 0

    for symbol in config.universe:
        if symbol in held_symbols:
            continue
        try:
            signal = compute_signal(client.get_bars(symbol, timeframe="1Hour", limit=100))
        except (AlpacaError, ValueError, KeyError) as exc:
            errors.append(f"signal {symbol}: {exc}")
            continue
        if signal.symbol_action != "BUY":
            continue
        try:
            quote = client.get_latest_quote(symbol)
        except AlpacaError as exc:
            errors.append(f"quote {symbol}: {exc}")
            continue
        if quote.spread_pct >= config.max_spread_pct:
            entries_skipped += 1
            _append_monitor_log(
                monitor_log_path,
                when,
                symbol,
                f"gate spread: {quote.spread_pct:.4%} >= {config.max_spread_pct:.4%}",
            )
            continue

        cost = position_size_majors(
            equity=account.equity,
            available_cash=account.cash,
            intended_pct=config.intended_position_pct,
            max_pct=config.max_position_pct,
        ).quantize(Decimal("0.01"))
        intent = OrderIntent(
            symbol=symbol,
            venue="alpaca",
            side="buy",
            qty=Decimal("0"),
            intended_cost_usd=cost,
            leg="majors",
        )
        failed_gate = next(
            (
                result
                for result in run_universal_gates(
                    kill_switch_state=kill_switch_state,
                    phase=phase,
                    state=gate_state,
                    intent=intent,
                    daily_loss_limit_pct=config.daily_loss_limit_pct,
                    drawdown_limit_pct=config.drawdown_limit_pct,
                    max_positions=config.max_positions,
                    max_position_pct=config.max_position_pct,
                    rate_limit_per_hour=config.rate_limit_per_hour,
                )
                if not result.passed
            ),
            None,
        )
        if failed_gate is not None:
            entries_skipped += 1
            _append_monitor_log(
                monitor_log_path,
                when,
                symbol,
                f"gate {failed_gate.gate_name}: {failed_gate.reason}",
            )
            continue
        try:
            execute_buy(
                client=client,
                intent=intent,
                now=when,
                trade_log_path=trade_log_path,
                thesis=signal.reason,
            )
            entries_placed += 1
        except (AlpacaError, RuntimeError) as exc:
            errors.append(f"execute {symbol}: {exc}")
    return entries_placed, entries_skipped


def _count_recent_trades(open_orders: list[AlpacaOrder]) -> int:
    return sum(
        1
        for order in open_orders
        if not (order.type == "stop_limit" and order.side == "sell")
    )


def _append_monitor_log(path: Path, when: datetime, symbol: str, reason: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(f"\n## {when.isoformat()} - {symbol} skipped\n- {reason}\n")


def _load_config_from_env() -> ScannerConfig:
    import os

    from dotenv import load_dotenv

    load_dotenv()
    return ScannerConfig(
        universe=DEFAULT_UNIVERSE,
        memory_dir=Path(__file__).resolve().parent.parent / "memory",
        daily_loss_limit_pct=Decimal(os.environ.get("DAILY_LOSS_LIMIT_PCT", "0.03")),
        drawdown_limit_pct=Decimal(os.environ.get("PHASE_DRAWDOWN_LIMIT_PCT", "0.15")),
        max_positions=int(os.environ.get("MAX_POSITIONS_MAJORS", "6")),
        max_position_pct=Decimal(os.environ.get("MAX_POSITION_PCT_MAJORS", "0.20")),
        rate_limit_per_hour=int(os.environ.get("RATE_LIMIT_TRADES_PER_HOUR_MAJORS", "5")),
        intended_position_pct=Decimal(os.environ.get("MAX_POSITION_PCT_MAJORS", "0.20")),
        max_spread_pct=Decimal(os.environ.get("MAX_SPREAD_PCT_MAJORS", "0.005")),
        alpaca_api_key=os.environ["ALPACA_API_KEY"],
        alpaca_secret_key=os.environ.get("ALPACA_SECRET_KEY", os.environ.get("ALPACA_API_SECRET", "")),
        alpaca_base_url=os.environ.get("ALPACA_BASE_URL", "https://paper-api.alpaca.markets"),
        alpaca_data_url=os.environ.get("ALPACA_DATA_URL", "https://data.alpaca.markets"),
        telegram_token=os.environ.get("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=os.environ.get("TELEGRAM_CHAT_ID"),
    )


if __name__ == "__main__":
    print(run_scan(_load_config_from_env()))

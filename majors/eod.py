"""End-of-day snapshot writer for the majors leg."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from core.notifications import send
from core.phase import current_phase
from majors.alpaca_client import AlpacaClient


@dataclass(frozen=True)
class EodConfig:
    memory_dir: Path
    alpaca_api_key: str
    alpaca_secret_key: str
    alpaca_base_url: str
    alpaca_data_url: str
    telegram_token: str | None
    telegram_chat_id: str | None


def run_eod(config: EodConfig, now: datetime | None = None) -> None:
    when = now or datetime.now()
    date_str = when.date().isoformat()
    trade_log = config.memory_dir / "TRADE-LOG.md"
    existing = trade_log.read_text(encoding="utf-8") if trade_log.exists() else ""
    section_marker = f"{date_str} EOD"
    if section_marker in existing:
        return

    client = AlpacaClient(
        api_key=config.alpaca_api_key,
        secret_key=config.alpaca_secret_key,
        base_url=config.alpaca_base_url,
        data_url=config.alpaca_data_url,
    )
    account = client.get_account()
    positions = client.list_positions()
    phase = current_phase(config.memory_dir / "PHASE.md")

    lines = [
        "",
        f"## Day {_next_day_number(existing)} - {date_str} EOD",
        (
            f"**Phase:** {phase} | **Equity:** ${account.equity} | "
            f"**Cash:** ${account.cash} | **Open positions:** {len(positions)} majors"
        ),
    ]
    for position in positions:
        pl_pct = (position.unrealized_plpc * Decimal("100")).quantize(Decimal("0.01"))
        sign = "+" if pl_pct >= 0 else ""
        lines.append(
            f"- {position.symbol}: {position.qty} @ ${position.avg_entry_price} ({sign}{pl_pct}%)"
        )
    section = "\n".join(lines) + "\n"
    trade_log.parent.mkdir(parents=True, exist_ok=True)
    with trade_log.open("a", encoding="utf-8") as file:
        file.write(section)

    send(
        f"[majors-eod] {date_str}: equity ${account.equity}, {len(positions)} open",
        urgency="info",
        telegram_token=None,
        telegram_chat_id=None,
        fallback_path=config.memory_dir / "NOTIFICATIONS.md",
    )


def _next_day_number(existing_trade_log: str) -> int:
    return existing_trade_log.count(" EOD") + 1


def _load_config_from_env() -> EodConfig:
    import os

    from dotenv import load_dotenv

    load_dotenv()
    return EodConfig(
        memory_dir=Path(__file__).resolve().parent.parent / "memory",
        alpaca_api_key=os.environ["ALPACA_API_KEY"],
        alpaca_secret_key=os.environ.get("ALPACA_SECRET_KEY", os.environ.get("ALPACA_API_SECRET", "")),
        alpaca_base_url=os.environ.get("ALPACA_BASE_URL", "https://paper-api.alpaca.markets"),
        alpaca_data_url=os.environ.get("ALPACA_DATA_URL", "https://data.alpaca.markets"),
        telegram_token=os.environ.get("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=os.environ.get("TELEGRAM_CHAT_ID"),
    )


if __name__ == "__main__":
    run_eod(_load_config_from_env())

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values


@dataclass(frozen=True)
class Config:
    bot_token: str
    allowed_user_id: int
    model: str
    opencode_host: str
    opencode_port: int
    opencode_password: str
    install_dir: Path
    memory_dir: Path
    data_dir: Path
    tz: str
    log_level: str
    shell_timeout: int
    opencode_url: str

    @classmethod
    def load(cls) -> "Config":
        env_path = Path(os.environ.get("ENV_PATH", "/root/.opencode-telegram/.env"))
        if not env_path.exists():
            env_path = Path(__file__).resolve().parent.parent / ".env"
        values = dotenv_values(env_path)
        for k, v in values.items():
            os.environ.setdefault(k, v or "")

        host = values.get("OPENCODE_HOST", "127.0.0.1")
        port = int(values.get("OPENCODE_PORT", "4096"))

        return cls(
            bot_token=values.get("TELEGRAM_BOT_TOKEN", ""),
            allowed_user_id=int(values.get("TELEGRAM_ALLOWED_USER_ID", "0")),
            model=values.get("OPENCODE_MODEL", "opencode/minimax-m3-free"),
            opencode_host=host,
            opencode_port=port,
            opencode_password=values.get("OPENCODE_SERVER_PASSWORD", ""),
            install_dir=Path(values.get("INSTALL_DIR", "/root/.opencode-telegram")),
            memory_dir=Path(values.get("MEMORY_DIR", "/root/.opencode-telegram/memory")),
            data_dir=Path(values.get("DATA_DIR", "/root/.opencode-telegram/data")),
            tz=values.get("TZ", "UTC"),
            log_level=values.get("LOG_LEVEL", "INFO"),
            shell_timeout=int(values.get("SHELL_TIMEOUT", "120")),
            opencode_url=f"http://{host}:{port}",
        )


CONFIG = Config.load()

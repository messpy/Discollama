# config_loader.py
from __future__ import annotations
import os
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import yaml  # pip install pyyaml
except Exception:
    yaml = None

try:
    from dotenv import load_dotenv  # pip install python-dotenv
except Exception:
    load_dotenv = None

def _deep_merge(dst: dict, src: dict) -> dict:
    for k, v in (src or {}).items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _deep_merge(dst[k], v)
        else:
            dst[k] = v
    return dst

def _find_config_dir() -> Path:
    for env in ("NEUROHUB_CONFIG",):
        p = os.getenv(env)
        if p:
            pp = Path(p).expanduser().resolve()
            if pp.is_dir():
                return pp
    for env in ("NEUROHUB_ROOT",):
        p = os.getenv(env)
        if p:
            pp = Path(p).expanduser().resolve() / "config"
            if pp.is_dir():
                return pp
    # fallback: ./config
    here = Path(__file__).resolve().parent
    for base in [here, *here.parents, Path.cwd(), *Path.cwd().parents]:
        cand = base / "config"
        if (cand / "config.yaml").exists() or (cand / ".env").exists():
            return cand
    return Path("./config").resolve()

class Config:
    def __init__(self) -> None:
        self.config_dir: Path = _find_config_dir()
        self.data: Dict[str, Any] = {}

        # 1) .env 読み込み
        if load_dotenv:
            dotenv_path = self.config_dir / ".env"
            if dotenv_path.exists():
                load_dotenv(dotenv_path.as_posix())

        # 2) YAML 読み込み（config.yaml → config.local.yaml で上書き）
        base = self.config_dir / "config.yaml"
        local = self.config_dir / "config.local.yaml"
        if yaml:
            if base.exists():
                with base.open(encoding="utf-8") as f:
                    d = yaml.safe_load(f) or {}
                    if isinstance(d, dict):
                        self.data = d
            if local.exists():
                with local.open(encoding="utf-8") as f:
                    d = yaml.safe_load(f) or {}
                    if isinstance(d, dict):
                        _deep_merge(self.data, d)

    def get(self, dotted: str, default: Optional[Any] = None) -> Any:
        cur: Any = self.data
        for part in dotted.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return default
            cur = cur[part]
        return cur

def getenv_or_cfg(env_key: str, dotted: str, default: Optional[Any] = None) -> Any:
    v = os.getenv(env_key)
    if v is not None and v != "":
        return v
    return Config().get(dotted, default)


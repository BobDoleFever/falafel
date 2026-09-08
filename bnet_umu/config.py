"""App configuration: ~/.config/bnet-umu/config.toml.

Reads with stdlib `tomllib` (Python 3.11+, read-only) and writes with a small
hand-rolled serializer, since our schema is simple (top-level scalars plus one
level of nested tables for per-game state) and doesn't need a full TOML
writer dependency.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .core.prefix import default_external_root, default_prefix_path, xdg_config_home

CONFIG_FILENAME = "config.toml"


def default_config_path() -> Path:
    return xdg_config_home() / "bnet-umu" / CONFIG_FILENAME


@dataclass
class AppConfig:
    prefix_path: Path = field(default_factory=default_prefix_path)
    external_root: Path = field(default_factory=default_external_root)
    proton_path: str = "GE-Proton"
    installed: dict[str, bool] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "AppConfig":
        return cls(
            prefix_path=Path(data.get("prefix_path", default_prefix_path())),
            external_root=Path(data.get("external_root", default_external_root())),
            proton_path=data.get("proton_path", "GE-Proton"),
            installed=dict(data.get("games", {}).get("installed", {})),
        )

    def to_dict(self) -> dict:
        return {
            "prefix_path": str(self.prefix_path),
            "external_root": str(self.external_root),
            "proton_path": self.proton_path,
            "games": {"installed": dict(self.installed)},
        }


def _toml_scalar(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    raise TypeError(f"Unsupported TOML scalar type: {type(value)!r}")


def _dumps(data: dict) -> str:
    lines: list[str] = []
    tables: dict[str, dict] = {}

    for key, value in data.items():
        if isinstance(value, dict):
            tables[key] = value
        else:
            lines.append(f"{key} = {_toml_scalar(value)}")

    for table_name, table_value in tables.items():
        nested_tables = {k: v for k, v in table_value.items() if isinstance(v, dict)}
        scalars = {k: v for k, v in table_value.items() if not isinstance(v, dict)}

        lines.append(f"\n[{table_name}]")
        for key, value in scalars.items():
            lines.append(f"{key} = {_toml_scalar(value)}")

        for sub_name, sub_value in nested_tables.items():
            lines.append(f"\n[{table_name}.{sub_name}]")
            for key, value in sub_value.items():
                lines.append(f"{key} = {_toml_scalar(value)}")

    return "\n".join(lines) + "\n"


def load(path: Path | None = None) -> AppConfig:
    path = path or default_config_path()
    if not path.exists():
        return AppConfig()
    with open(path, "rb") as f:
        data = tomllib.load(f)
    return AppConfig.from_dict(data)


def save(config: AppConfig, path: Path | None = None) -> Path:
    path = path or default_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dumps(config.to_dict()))
    return path

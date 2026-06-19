from dataclasses import dataclass
import json as _json


@dataclass
class Envelope:
    ok: bool
    tool: str = "bgs-papyrus"
    command: str = ""
    data: dict | None = None
    error: dict | None = None

    def to_json(self) -> str:
        return _json.dumps(
            {
                "ok": self.ok,
                "tool": self.tool,
                "command": self.command,
                "data": self.data,
                "error": self.error,
            }
        )

    def human(self) -> str:
        return f"[{self.tool}] {self.command}: " + ("OK" if self.ok else f"ERROR {self.error}")

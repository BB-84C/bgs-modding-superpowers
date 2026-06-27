from pathlib import Path

from mo2_assets_engine.types import Mod


def test_mod_dataclass_basic_construction() -> None:
    mod = Mod(name="ExampleMod", priority=10, enabled=True, root=Path("/tmp/mods/Example"))
    assert mod.name == "ExampleMod"
    assert mod.priority == 10
    assert mod.enabled is True

"""Two-stage close confirmation dialog tests."""

from __future__ import annotations

import os
import tkinter as tk

import pytest


def _need_tk_runtime() -> None:
    if os.environ.get("CI"):
        pytest.skip("Tk close-handler tests skipped under CI")
    tkinter = pytest.importorskip("tkinter")
    try:
        tkinter.Tk().destroy()
    except tkinter.TclError as exc:
        pytest.skip(f"Tk runtime unavailable: {exc}")


def _buttons(parent: tk.Misc) -> dict[str, tk.Widget]:
    found: dict[str, tk.Widget] = {}

    def walk(widget: tk.Misc) -> None:
        for child in widget.winfo_children():
            text = ""
            try:
                text = str(child.cget("text"))
            except tk.TclError:
                pass
            if text:
                found[text] = child
            walk(child)

    walk(parent)
    return found


def _invoke(button: tk.Widget) -> None:
    command = getattr(button, "invoke", None)
    assert callable(command)
    command()


def _is_destroyed(root: tk.Tk) -> bool:
    try:
        return not bool(root.winfo_exists())
    except tk.TclError:
        return True


def test_stage_one_dialog_shows_three_button_options() -> None:
    _need_tk_runtime()
    from bgs_translator.gui.close_handler import CloseHandler

    root = tk.Tk()
    try:
        handler = CloseHandler(root, get_in_flight_count=lambda: 2, get_unsaved_count=lambda: 1)
        handler.request_close()
        root.update_idletasks()

        dialogs = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]
        assert len(dialogs) == 1
        button_texts = set(_buttons(dialogs[0]))
        assert {"Close window only", "Stop everything (cancel batches)", "Cancel"} <= button_texts
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass


def test_close_window_only_with_zero_unsaved_closes_without_stage_two() -> None:
    _need_tk_runtime()
    from bgs_translator.gui.close_handler import CloseHandler

    closed = False

    def on_closed() -> None:
        nonlocal closed
        closed = True

    root = tk.Tk()
    handler = CloseHandler(root, get_unsaved_count=lambda: 0, on_window_close=on_closed)
    handler.request_close()
    root.update_idletasks()
    dialog = next(w for w in root.winfo_children() if isinstance(w, tk.Toplevel))
    _invoke(_buttons(dialog)["Close window only"])

    assert closed is True
    assert _is_destroyed(root)


def test_close_window_only_with_unsaved_edits_opens_stage_two() -> None:
    _need_tk_runtime()
    from bgs_translator.gui.close_handler import CloseHandler

    root = tk.Tk()
    try:
        handler = CloseHandler(root, get_unsaved_count=lambda: 3)
        handler.request_close()
        root.update_idletasks()
        stage_one = next(w for w in root.winfo_children() if isinstance(w, tk.Toplevel))
        _invoke(_buttons(stage_one)["Close window only"])
        root.update_idletasks()

        dialogs = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]
        assert len(dialogs) == 1
        assert {"Save SST and quit", "Discard and quit", "Cancel"} <= set(_buttons(dialogs[0]))
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass


def test_stage_two_discard_and_quit_exits_cleanly() -> None:
    _need_tk_runtime()
    from bgs_translator.gui.close_handler import CloseHandler

    root = tk.Tk()
    handler = CloseHandler(root, get_unsaved_count=lambda: 1)
    handler.request_close()
    root.update_idletasks()
    stage_one = next(w for w in root.winfo_children() if isinstance(w, tk.Toplevel))
    _invoke(_buttons(stage_one)["Close window only"])
    root.update_idletasks()
    stage_two = next(w for w in root.winfo_children() if isinstance(w, tk.Toplevel))
    _invoke(_buttons(stage_two)["Discard and quit"])

    assert _is_destroyed(root)


def test_stage_two_save_sst_and_quit_invokes_export_then_exits() -> None:
    _need_tk_runtime()
    from bgs_translator.gui.close_handler import CloseHandler

    exported: list[str] = []

    def export_project(project_name: str) -> None:
        exported.append(project_name)

    root = tk.Tk()
    handler = CloseHandler(
        root,
        get_unsaved_count=lambda: 1,
        get_active_project=lambda: "demo",
        export_project=export_project,
    )
    handler.request_close()
    root.update_idletasks()
    stage_one = next(w for w in root.winfo_children() if isinstance(w, tk.Toplevel))
    _invoke(_buttons(stage_one)["Close window only"])
    root.update_idletasks()
    stage_two = next(w for w in root.winfo_children() if isinstance(w, tk.Toplevel))
    _invoke(_buttons(stage_two)["Save SST and quit"])

    assert exported == ["demo"]
    assert _is_destroyed(root)

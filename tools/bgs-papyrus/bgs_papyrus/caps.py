from .model import Envelope


def run() -> Envelope:
    return Envelope(ok=True, command="capabilities", data={})

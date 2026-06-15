import json
from pathlib import Path

import jsonschema


SCHEMA_PATH = Path(__file__).parent.parent / "broker-schema.json"


def _load_schema():
    return json.loads(SCHEMA_PATH.read_text())


def _validate_definition(schema, definition_name, instance):
    validator = jsonschema.Draft202012Validator(
        {**schema, "$ref": f"#/definitions/{definition_name}"}
    )
    validator.validate(instance)


def test_schema_loads_as_valid_json_schema():
    schema = _load_schema()

    jsonschema.Draft202012Validator.check_schema(schema["definitions"]["request"])
    jsonschema.Draft202012Validator.check_schema(schema["definitions"]["response"])


def test_valid_request_passes_validation():
    schema = _load_schema()
    request = {
        "protocol_version": "1",
        "request_id": "req-001",
        "session_id": "sess-abc",
        "method": "system.ping",
        "payload": {},
    }

    _validate_definition(schema, "request", request)


def test_valid_response_ok_passes():
    schema = _load_schema()
    response = {
        "protocol_version": "1",
        "request_id": "req-001",
        "ok": True,
        "result": {"pong": True},
        "error": None,
    }

    _validate_definition(schema, "response", response)


def test_valid_response_error_passes():
    schema = _load_schema()
    response = {
        "protocol_version": "1",
        "request_id": "req-001",
        "ok": False,
        "result": None,
        "error": {"code": "method_not_found", "message": "..."},
    }

    _validate_definition(schema, "response", response)

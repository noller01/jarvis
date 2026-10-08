"""Example plugin — drop .py files here; JARVIS discovers them on next launch."""

NAME = "example_echo"

TOOL = {
    "name": "echo_plugin",
    "description": "Echo text back (example user plugin)",
    "parameters": {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    },
}


def handler(args: dict):
    return {"ok": True, "echo": args.get("text", ""), "display": args.get("text", "")}

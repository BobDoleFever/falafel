"""Minimal binary VDF (de)serialization, scoped to what shortcuts.vdf needs.

Binary VDF is a sequence of (type byte, null-terminated key, value) triples,
terminated by a lone 0x08 byte; type 0x00 means the value is itself a
nested map (recursively terminated the same way), 0x01 a null-terminated
string, 0x02 a 4-byte little-endian uint32. That's the whole grammar
shortcuts.vdf uses — no need for the rest of the general VDF type space.

Fields are kept as plain dicts (insertion order preserved, same as the file
order) so unknown/extra fields — Steam writes some we don't otherwise care
about, e.g. "sortas" — round-trip untouched instead of being silently
dropped. Verified byte-for-byte round-trip against a real shortcuts.vdf
before this was ever used to write one.
"""

from __future__ import annotations

MAP_TYPE = 0x00
STRING_TYPE = 0x01
UINT32_TYPE = 0x02
END_MARKER = 0x08


def parse_map(data: bytes, pos: int = 0) -> tuple[dict, int]:
    result: dict = {}
    while True:
        type_byte = data[pos]
        pos += 1
        if type_byte == END_MARKER:
            return result, pos
        end = data.index(b"\x00", pos)
        key = data[pos:end].decode("utf-8")
        pos = end + 1
        if type_byte == MAP_TYPE:
            value, pos = parse_map(data, pos)
        elif type_byte == STRING_TYPE:
            end = data.index(b"\x00", pos)
            value = data[pos:end].decode("utf-8")
            pos = end + 1
        elif type_byte == UINT32_TYPE:
            value = int.from_bytes(data[pos : pos + 4], "little", signed=False)
            pos += 4
        else:
            raise ValueError(f"unsupported VDF type byte {type_byte:#x} at offset {pos - 1}")
        result[key] = value


def _serialize_value(key: str, value: dict | str | int) -> bytes:
    kb = key.encode("utf-8") + b"\x00"
    if isinstance(value, dict):
        return bytes([MAP_TYPE]) + kb + serialize_map(value) + bytes([END_MARKER])
    if isinstance(value, str):
        return bytes([STRING_TYPE]) + kb + value.encode("utf-8") + b"\x00"
    if isinstance(value, int):
        return bytes([UINT32_TYPE]) + kb + (value & 0xFFFFFFFF).to_bytes(4, "little")
    raise TypeError(f"unsupported VDF value type {type(value)} for key {key!r}")


def serialize_map(d: dict) -> bytes:
    return b"".join(_serialize_value(k, v) for k, v in d.items())


def loads(data: bytes) -> dict:
    root, pos = parse_map(data, 0)
    if pos != len(data):
        raise ValueError(f"trailing data after root map: {len(data) - pos} byte(s) unparsed")
    return root


def dumps(root: dict) -> bytes:
    return serialize_map(root) + bytes([END_MARKER])

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any, Dict, Optional


PROTOCOL_VERSION = 1


def make_packet(message_type: str, vehicle_id: str = "", **payload: Any) -> Dict[str, Any]:
    return {
        "v": PROTOCOL_VERSION,
        "type": str(message_type),
        "vehicle_id": str(vehicle_id),
        "ts": time.time(),
        **payload,
    }


def _canonical(data: Dict[str, Any]) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def encode_packet(packet: Dict[str, Any], secret: str = "") -> bytes:
    body = dict(packet)
    body.pop("auth", None)
    if secret:
        body["auth"] = hmac.new(secret.encode("utf-8"), _canonical(body), hashlib.sha256).hexdigest()
    return _canonical(body)


def decode_packet(data: bytes, secret: str = "", *, max_size: int = 65507) -> Dict[str, Any]:
    if len(data) > max_size:
        raise ValueError("UDP packet too large")
    try:
        packet = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid UDP JSON packet") from exc
    if not isinstance(packet, dict):
        raise ValueError("UDP packet must be a JSON object")
    if int(packet.get("v", -1)) != PROTOCOL_VERSION:
        raise ValueError("unsupported UDP protocol version")
    if secret:
        received = str(packet.get("auth", ""))
        unsigned = dict(packet)
        unsigned.pop("auth", None)
        expected = hmac.new(secret.encode("utf-8"), _canonical(unsigned), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(received, expected):
            raise ValueError("UDP packet authentication failed")
    return packet

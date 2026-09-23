import socket

import pytest

from smartcar.udp_protocol import decode_packet, encode_packet, make_packet


def test_signed_packet_round_trip_and_tamper_detection():
    packet = make_packet('vehicle_status', 'car_1', state='IDLE')
    payload = encode_packet(packet, 'secret')
    decoded = decode_packet(payload, 'secret')
    assert decoded['vehicle_id'] == 'car_1'
    assert decoded['state'] == 'IDLE'

    tampered = payload.replace(b'IDLE', b'BUSY')
    with pytest.raises(ValueError):
        decode_packet(tampered, 'secret')


def test_udp_loopback_datagram():
    receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiver.bind(('127.0.0.1', 0))
    sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sender.sendto(encode_packet(make_packet('ping', 'car_2')), receiver.getsockname())
        data, _ = receiver.recvfrom(4096)
        assert decode_packet(data)['type'] == 'ping'
    finally:
        sender.close()
        receiver.close()

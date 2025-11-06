#!/usr/bin/env python3
"""
Test script for FIITMeteo Binary Protocol
"""

import protocol
import time

def test_register():
    print("Testing REGISTER message...")
    msg = protocol.encode_register("ThermoNode")
    print(f"  Encoded size: {len(msg)} bytes")
    print(f"  Hex: {msg.hex()}")

    decoded = protocol.decode_register(msg)
    print(f"  Decoded: {decoded}")
    assert decoded["type"] == "register"
    assert decoded["device_type"] == "ThermoNode"
    print("  ✓ PASS\n")

def test_register_ack():
    print("Testing REGISTER_ACK message...")
    msg = protocol.encode_register_ack("WindSense", 12345)
    print(f"  Encoded size: {len(msg)} bytes")
    print(f"  Hex: {msg.hex()}")

    decoded = protocol.decode_register_ack(msg)
    print(f"  Decoded: {decoded}")
    assert decoded["type"] == "register_ack"
    assert decoded["device_type"] == "WindSense"
    assert decoded["token"] == 12345
    print("  ✓ PASS\n")

def test_data_thermonode():
    print("Testing DATA message (ThermoNode)...")
    data = {
        "temperature": 25.3,
        "humidity": 65.7,
        "dew_point": 15.2,
        "pressure": 1013.25
    }
    msg = protocol.encode_data("ThermoNode", 4660, data, battery_low=False)
    print(f"  Encoded size: {len(msg)} bytes (vs ~250 bytes JSON)")
    print(f"  Hex: {msg.hex()}")

    decoded = protocol.decode_data(msg)
    print(f"  Decoded: {decoded}")
    assert decoded["type"] == "data"
    assert decoded["device_type"] == "ThermoNode"
    assert decoded["token"] == 4660
    assert abs(decoded["data"]["temperature"] - 25.3) < 0.1
    assert abs(decoded["data"]["humidity"] - 65.7) < 0.1
    print("  ✓ PASS\n")

def test_data_windsense():
    print("Testing DATA message (WindSense)...")
    data = {
        "wind_speed": 12.5,
        "wind_gust": 18.3,
        "wind_direction": 270,
        "turbulence": 0.6
    }
    msg = protocol.encode_data("WindSense", 5000, data)
    print(f"  Encoded size: {len(msg)} bytes")
    print(f"  Hex: {msg.hex()}")

    decoded = protocol.decode_data(msg)
    print(f"  Decoded: {decoded}")
    assert decoded["device_type"] == "WindSense"
    assert abs(decoded["data"]["wind_speed"] - 12.5) < 0.1
    assert decoded["data"]["wind_direction"] == 270
    print("  ✓ PASS\n")

def test_data_raindetect():
    print("Testing DATA message (RainDetect)...")
    data = {
        "rainfall": 25.8,
        "soil_moisture": 75.5,
        "flood_risk": 2,
        "rain_duration": 45
    }
    msg = protocol.encode_data("RainDetect", 6000, data)
    print(f"  Encoded size: {len(msg)} bytes")
    print(f"  Hex: {msg.hex()}")

    decoded = protocol.decode_data(msg)
    print(f"  Decoded: {decoded}")
    assert decoded["device_type"] == "RainDetect"
    assert abs(decoded["data"]["rainfall"] - 25.8) < 0.1
    assert decoded["data"]["flood_risk"] == 2
    print("  ✓ PASS\n")

def test_data_airquality():
    print("Testing DATA message (AirQualityBox)...")
    data = {
        "co2": 450,
        "ozone": 85.5,
        "air_quality_index": 125
    }
    msg = protocol.encode_data("AirQualityBox", 7000, data)
    print(f"  Encoded size: {len(msg)} bytes")
    print(f"  Hex: {msg.hex()}")

    decoded = protocol.decode_data(msg)
    print(f"  Decoded: {decoded}")
    assert decoded["device_type"] == "AirQualityBox"
    assert decoded["data"]["co2"] == 450
    assert abs(decoded["data"]["ozone"] - 85.5) < 0.1
    print("  ✓ PASS\n")

def test_data_ack():
    print("Testing DATA_ACK message...")
    msg = protocol.encode_data_ack("ThermoNode", "OK")
    print(f"  Encoded size: {len(msg)} bytes")
    print(f"  Hex: {msg.hex()}")

    decoded = protocol.decode_data_ack(msg)
    print(f"  Decoded: {decoded}")
    assert decoded["type"] == "data_ack"
    assert decoded["status"] == "OK"
    print("  ✓ PASS\n")

def test_error():
    print("Testing ERROR message...")
    msg = protocol.encode_error("WindSense", "CRC_FAIL", "resend_last")
    print(f"  Encoded size: {len(msg)} bytes")
    print(f"  Hex: {msg.hex()}")

    decoded = protocol.decode_error(msg)
    print(f"  Decoded: {decoded}")
    assert decoded["type"] == "error"
    assert decoded["error"] == "CRC_FAIL"
    assert decoded["request"] == "resend_last"
    print("  ✓ PASS\n")

def test_ping():
    print("Testing PING message...")
    msg = protocol.encode_ping("RainDetect")
    print(f"  Encoded size: {len(msg)} bytes")
    print(f"  Hex: {msg.hex()}")

    decoded = protocol.decode_ping(msg)
    print(f"  Decoded: {decoded}")
    assert decoded["type"] == "ping"
    assert decoded["device_type"] == "RainDetect"
    print("  ✓ PASS\n")

def test_pong():
    print("Testing PONG message...")
    msg = protocol.encode_pong("AirQualityBox", 9999)
    print(f"  Encoded size: {len(msg)} bytes")
    print(f"  Hex: {msg.hex()}")

    decoded = protocol.decode_pong(msg)
    print(f"  Decoded: {decoded}")
    assert decoded["type"] == "pong"
    assert decoded["token"] == 9999
    print("  ✓ PASS\n")

def test_crc_detection():
    print("Testing CRC error detection...")
    data = {"temperature": 25.0, "humidity": 60.0, "dew_point": 15.0, "pressure": 1013.0}
    msg = protocol.encode_data("ThermoNode", 1234, data, corrupt_crc=True)
    print(f"  Corrupted message hex: {msg.hex()}")

    try:
        decoded = protocol.decode_data(msg)
        print("  ✗ FAIL - Should have detected CRC error!")
        assert False
    except ValueError as e:
        print(f"  ✓ PASS - CRC error detected: {e}\n")

def test_battery_flag():
    print("Testing battery low flag...")
    data = {"temperature": 20.0, "humidity": 50.0, "dew_point": 10.0, "pressure": 1000.0}
    msg = protocol.encode_data("ThermoNode", 5555, data, battery_low=True)
    print(f"  Encoded with battery_low=True")

    decoded = protocol.decode_data(msg)
    print(f"  Decoded battery_low: {decoded['battery_low']}")
    assert decoded["battery_low"] == True
    print("  ✓ PASS\n")

def test_decode_message_auto():
    print("Testing automatic message type detection...")

    # Test with different message types
    msg1 = protocol.encode_register("ThermoNode")
    decoded1 = protocol.decode_message(msg1)
    assert decoded1["type"] == "register"
    print("  ✓ Auto-detected REGISTER")

    msg2 = protocol.encode_data("WindSense", 1111, {"wind_speed": 10.0, "wind_gust": 15.0, "wind_direction": 180, "turbulence": 0.5})
    decoded2 = protocol.decode_message(msg2)
    assert decoded2["type"] == "data"
    print("  ✓ Auto-detected DATA")

    msg3 = protocol.encode_ping("RainDetect")
    decoded3 = protocol.decode_message(msg3)
    assert decoded3["type"] == "ping"
    print("  ✓ Auto-detected PING")

    print("  ✓ PASS\n")

def print_size_comparison():
    print("=" * 70)
    print("MESSAGE SIZE COMPARISON (JSON vs Binary)")
    print("=" * 70)

    import json

    # REGISTER comparison
    json_register = json.dumps({
        "type": "register",
        "device_type": "ThermoNode",
        "timestamp": int(time.time()),
        "battery_low": False,
        "crc": "12345678"
    }).encode()
    binary_register = protocol.encode_register("ThermoNode")
    print(f"REGISTER:      JSON={len(json_register):3d} bytes  Binary={len(binary_register):2d} bytes  Savings={100*(1-len(binary_register)/len(json_register)):.1f}%")

    # DATA comparison
    json_data = json.dumps({
        "type": "data",
        "device_type": "ThermoNode",
        "timestamp": int(time.time()),
        "token": 12345,
        "battery_low": False,
        "data": {
            "temperature": 25.3,
            "humidity": 65.7,
            "dew_point": 15.2,
            "pressure": 1013.25
        },
        "crc": "ABCDEF12"
    }).encode()
    binary_data = protocol.encode_data("ThermoNode", 12345, {
        "temperature": 25.3,
        "humidity": 65.7,
        "dew_point": 15.2,
        "pressure": 1013.25
    })
    print(f"DATA:          JSON={len(json_data):3d} bytes  Binary={len(binary_data):2d} bytes  Savings={100*(1-len(binary_data)/len(json_data)):.1f}%")

    # PING comparison
    json_ping = json.dumps({
        "type": "ping",
        "device_type": "WindSense",
        "timestamp": int(time.time())
    }).encode()
    binary_ping = protocol.encode_ping("WindSense")
    print(f"PING:          JSON={len(json_ping):3d} bytes  Binary={len(binary_ping):2d} bytes  Savings={100*(1-len(binary_ping)/len(json_ping)):.1f}%")

    print("=" * 70)
    print()

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("FIITMeteo Binary Protocol - Unit Tests")
    print("=" * 70 + "\n")

    try:
        test_register()
        test_register_ack()
        test_data_thermonode()
        test_data_windsense()
        test_data_raindetect()
        test_data_airquality()
        test_data_ack()
        test_error()
        test_ping()
        test_pong()
        test_crc_detection()
        test_battery_flag()
        test_decode_message_auto()

        print("=" * 70)
        print("ALL TESTS PASSED! ✓")
        print("=" * 70 + "\n")

        print_size_comparison()

    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}\n")
        import traceback
        traceback.print_exc()

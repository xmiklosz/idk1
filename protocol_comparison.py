#!/usr/bin/env python3
"""
Protocol Efficiency Comparison Tool
Compares JSON vs Binary protocol for FIITMeteo project
"""

import json
import struct
import zlib
import sys

# Binary protocol encoding functions
def make_binary_header(msg_type, device_type, flags=0):
    byte0 = (msg_type << 6) | (device_type << 4) | (flags & 0x0F)
    timestamp = 1234567890
    return struct.pack('!BI', byte0, timestamp)

def make_binary_data(device_type, token, data, battery_low=False):
    flags = 0x01 if battery_low else 0x00
    header = make_binary_header(0x2, device_type, flags)
    token_bytes = struct.pack('!I', token)

    # Encode device-specific data
    if device_type == 0:  # ThermoNode
        temp = int(data["temperature"] * 10)
        hum = int(data["humidity"] * 10)
        dew = int(data["dew_point"] * 10)
        press = int(data["pressure"] * 100 - 80000)
        payload = struct.pack('!hHhH', temp, hum, dew, press)
    elif device_type == 1:  # WindSense
        speed = int(data["wind_speed"] * 10)
        gust = int(data["wind_gust"] * 10)
        direction = int(data["wind_direction"])
        turb = int(data["turbulence"] * 10)
        payload = struct.pack('!HHHB', speed, gust, direction, turb)
    elif device_type == 2:  # RainDetect
        rain = int(data["rainfall"] * 10)
        moist = int(data["soil_moisture"] * 10)
        risk = int(data["flood_risk"])
        duration = int(data["rain_duration"])
        payload = struct.pack('!HHBH', rain, moist, risk, duration)
    else:  # AirQualityBox
        co2 = int(data["co2"])
        ozone = int(data["ozone"] * 10)
        aqi = int(data["air_quality_index"])
        payload = struct.pack('!HHH', co2, ozone, aqi)

    message_without_crc = header + token_bytes + payload
    crc = zlib.crc32(message_without_crc)
    crc_bytes = struct.pack('!I', crc)
    return message_without_crc + crc_bytes

# JSON protocol encoding functions
def make_json_data(device_type_name, token, data, battery_low=False):
    msg = {
        "type": "data",
        "device_type": device_type_name,
        "timestamp": 1234567890,
        "battery_low": battery_low,
        "token": f"T-{token}",
        "data": data
    }
    msg["crc"] = format(zlib.crc32(json.dumps(msg, sort_keys=True).encode()), "08X")
    return json.dumps(msg).encode()

# Sample data for each device type
devices = {
    "ThermoNode": {
        "type": 0,
        "data": {
            "temperature": 25.5,
            "humidity": 65.3,
            "dew_point": 15.2,
            "pressure": 1013.25
        }
    },
    "WindSense": {
        "type": 1,
        "data": {
            "wind_speed": 12.5,
            "wind_gust": 18.3,
            "wind_direction": 270,
            "turbulence": 0.5
        }
    },
    "RainDetect": {
        "type": 2,
        "data": {
            "rainfall": 5.5,
            "soil_moisture": 75.0,
            "flood_risk": 1,
            "rain_duration": 30
        }
    },
    "AirQualityBox": {
        "type": 3,
        "data": {
            "co2": 450,
            "ozone": 85.5,
            "air_quality_index": 75
        }
    }
}

# Calculate L2-L4 overhead
def calculate_overhead():
    """Calculate Ethernet + IP + UDP overhead"""
    ethernet = 14  # Ethernet header (no VLAN)
    ip = 20        # IPv4 header (no options)
    udp = 8        # UDP header
    return ethernet + ip + udp

# MQTT payload size estimation
def estimate_mqtt_size(device_name, data, battery_low):
    """Estimate MQTT message size for comparison"""
    # MQTT Fixed Header: 2 bytes (typ.)
    # Topic: e.g., "fiitmeteo/ThermoNode/data" = ~30 bytes
    # Payload: JSON data
    topic = f"fiitmeteo/{device_name}/data"
    payload = {
        "timestamp": 1234567890,
        "battery_low": battery_low,
        "data": data
    }
    payload_bytes = json.dumps(payload).encode()

    # MQTT overhead: Fixed header (2) + Topic length (2) + Topic + QoS overhead
    mqtt_overhead = 2 + 2 + len(topic) + 2  # simplified
    return mqtt_overhead + len(payload_bytes)

def print_separator():
    print("=" * 100)

def print_comparison():
    print("\n" + "="*100)
    print("FIITMeteo Protocol Efficiency Comparison")
    print("="*100)

    token = 12345
    overhead = calculate_overhead()

    print(f"\nL2-L4 Overhead (Ethernet + IP + UDP): {overhead} bytes")
    print_separator()

    total_json = 0
    total_binary = 0
    total_mqtt = 0

    for device_name, device_info in devices.items():
        print(f"\n{device_name} (Normal Operation)")
        print("-" * 100)

        device_type = device_info["type"]
        data = device_info["data"]

        # JSON protocol
        json_msg = make_json_data(device_name, token, data, False)
        json_size = len(json_msg)
        json_total = json_size + overhead

        # Binary protocol
        binary_msg = make_binary_data(device_type, token, data, False)
        binary_size = len(binary_msg)
        binary_total = binary_size + overhead

        # MQTT estimation
        mqtt_size = estimate_mqtt_size(device_name, data, False)
        mqtt_total = mqtt_size + overhead

        # Calculate improvements
        json_improvement = ((json_size - binary_size) / json_size) * 100
        json_total_improvement = ((json_total - binary_total) / json_total) * 100

        mqtt_improvement = ((mqtt_size - binary_size) / mqtt_size) * 100

        print(f"  JSON Protocol:")
        print(f"    Application Layer: {json_size} bytes")
        print(f"    Total (with L2-L4): {json_total} bytes")

        print(f"  Binary Protocol:")
        print(f"    Application Layer: {binary_size} bytes")
        print(f"    Total (with L2-L4): {binary_total} bytes")
        print(f"    Improvement vs JSON: {json_improvement:.1f}% (app), {json_total_improvement:.1f}% (total)")

        print(f"  MQTT (estimated):")
        print(f"    Application Layer: {mqtt_size} bytes")
        print(f"    Total (with L2-L4): {mqtt_total} bytes")
        print(f"    Binary vs MQTT: {mqtt_improvement:.1f}% smaller")

        total_json += json_size
        total_binary += binary_size
        total_mqtt += mqtt_size

        # With battery warning
        json_msg_bat = make_json_data(device_name, token, data, True)
        binary_msg_bat = make_binary_data(device_type, token, data, True)

        print(f"  With Battery Warning:")
        print(f"    JSON: {len(json_msg_bat)} bytes (+{len(json_msg_bat) - json_size} bytes)")
        print(f"    Binary: {len(binary_msg_bat)} bytes (+{len(binary_msg_bat) - binary_size} bytes)")

    print_separator()
    print(f"\nSummary for All 4 Devices (one message each):")
    print(f"  JSON Total: {total_json} bytes")
    print(f"  Binary Total: {total_binary} bytes")
    print(f"  MQTT Total (est.): {total_mqtt} bytes")
    print(f"  Binary saves: {total_json - total_binary} bytes ({((total_json - total_binary)/total_json)*100:.1f}%) vs JSON")
    print(f"  Binary saves: {total_mqtt - total_binary} bytes ({((total_mqtt - total_binary)/total_mqtt)*100:.1f}%) vs MQTT")

    print_separator()
    print(f"\nControl Messages:")
    print("-" * 100)

    # REGISTER
    json_register = json.dumps({
        "type": "register",
        "device_type": "ThermoNode",
        "timestamp": 1234567890
    }).encode()
    binary_register = make_binary_header(0x0, 0, 0)
    print(f"  REGISTER:")
    print(f"    JSON: {len(json_register)} bytes")
    print(f"    Binary: {len(binary_register)} bytes")
    print(f"    Improvement: {((len(json_register) - len(binary_register))/len(json_register))*100:.1f}%")

    # REGISTER_ACK
    json_register_ack = json.dumps({
        "type": "register_ack",
        "device_type": "ThermoNode",
        "timestamp": 1234567890,
        "token": f"T-{token}"
    }).encode()
    binary_register_ack = make_binary_header(0x1, 0, 0) + struct.pack('!I', token)
    print(f"  REGISTER_ACK:")
    print(f"    JSON: {len(json_register_ack)} bytes")
    print(f"    Binary: {len(binary_register_ack)} bytes")
    print(f"    Improvement: {((len(json_register_ack) - len(binary_register_ack))/len(json_register_ack))*100:.1f}%")

    # PING
    json_ping = json.dumps({
        "type": "ping",
        "device_type": "ThermoNode",
        "timestamp": 1234567890
    }).encode()
    binary_ping = make_binary_header(0x3, 0, 0x1)
    print(f"  PING:")
    print(f"    JSON: {len(json_ping)} bytes")
    print(f"    Binary: {len(binary_ping)} bytes")
    print(f"    Improvement: {((len(json_ping) - len(binary_ping))/len(json_ping))*100:.1f}%")

    # DATA_ACK
    json_ack = json.dumps({
        "type": "data_ack",
        "device_type": "ThermoNode",
        "timestamp": 1234567890,
        "status": "OK"
    }).encode()
    binary_ack = make_binary_header(0x3, 0, 0x0)
    print(f"  DATA_ACK:")
    print(f"    JSON: {len(json_ack)} bytes")
    print(f"    Binary: {len(binary_ack)} bytes")
    print(f"    Improvement: {((len(json_ack) - len(binary_ack))/len(json_ack))*100:.1f}%")

    print_separator()
    print(f"\nScenario: 10 minutes of operation (all 4 sensors, 10s interval)")
    print("-" * 100)
    messages_per_sensor = 60  # 6 messages per minute * 10 minutes
    total_messages = messages_per_sensor * 4

    # Average message size
    avg_json = total_json / 4
    avg_binary = total_binary / 4

    # Add control messages (1 register + 1 register_ack per sensor)
    control_json = (len(json_register) + len(json_register_ack)) * 4
    control_binary = (len(binary_register) + len(binary_register_ack)) * 4

    total_json_10min = (avg_json * total_messages) + control_json
    total_binary_10min = (avg_binary * total_messages) + control_binary

    # With L2-L4 overhead
    total_json_10min_full = total_json_10min + (overhead * (total_messages + 8))
    total_binary_10min_full = total_binary_10min + (overhead * (total_messages + 8))

    print(f"  Total messages: {total_messages} data + 8 control = {total_messages + 8} messages")
    print(f"  JSON Protocol:")
    print(f"    Application Layer: {total_json_10min:,} bytes ({total_json_10min/1024:.2f} KB)")
    print(f"    With L2-L4: {total_json_10min_full:,} bytes ({total_json_10min_full/1024:.2f} KB)")
    print(f"  Binary Protocol:")
    print(f"    Application Layer: {total_binary_10min:,} bytes ({total_binary_10min/1024:.2f} KB)")
    print(f"    With L2-L4: {total_binary_10min_full:,} bytes ({total_binary_10min_full/1024:.2f} KB)")
    print(f"  Data Saved: {total_json_10min - total_binary_10min:,} bytes ({((total_json_10min - total_binary_10min)/total_json_10min)*100:.1f}%) at app layer")
    print(f"  Data Saved: {total_json_10min_full - total_binary_10min_full:,} bytes ({((total_json_10min_full - total_binary_10min_full)/total_json_10min_full)*100:.1f}%) with overhead")

    print_separator()
    print(f"\nBinary Protocol Breakdown (ThermoNode DATA message):")
    print("-" * 100)
    binary_msg = make_binary_data(0, token, devices["ThermoNode"]["data"], False)
    print(f"  Header: 5 bytes")
    print(f"    - Message Type (2 bits) + Device Type (2 bits) + Flags (4 bits): 1 byte")
    print(f"    - Timestamp (32-bit): 4 bytes")
    print(f"  Token: 4 bytes")
    print(f"  Payload (ThermoNode): 8 bytes")
    print(f"    - Temperature (int16): 2 bytes")
    print(f"    - Humidity (uint16): 2 bytes")
    print(f"    - Dew Point (int16): 2 bytes")
    print(f"    - Pressure (uint16): 2 bytes")
    print(f"  CRC32: 4 bytes")
    print(f"  Total: {len(binary_msg)} bytes")

    print_separator()
    print()

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--export":
        # Export data to CSV for charting
        print("device,json_size,binary_size,mqtt_size,improvement")
        token = 12345
        for device_name, device_info in devices.items():
            device_type = device_info["type"]
            data = device_info["data"]
            json_msg = make_json_data(device_name, token, data, False)
            binary_msg = make_binary_data(device_type, token, data, False)
            mqtt_size = estimate_mqtt_size(device_name, data, False)
            improvement = ((len(json_msg) - len(binary_msg)) / len(json_msg)) * 100
            print(f"{device_name},{len(json_msg)},{len(binary_msg)},{mqtt_size},{improvement:.1f}")
    else:
        print_comparison()

if __name__ == "__main__":
    main()

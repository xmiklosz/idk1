"""
FIITMeteo Binary Protocol

Protocol Specification:
======================

Header (1 byte):
- Bits 0-2: Message Type (3 bits)
  0 = REGISTER
  1 = REGISTER_ACK
  2 = DATA
  3 = DATA_ACK
  4 = ERROR
  5 = PING
  6 = PONG
- Bits 3-4: Device Type (2 bits)
  0 = ThermoNode
  1 = WindSense
  2 = RainDetect
  3 = AirQualityBox
- Bits 5-7: Flags (3 bits)
  Bit 5: battery_low
  Bits 6-7: reserved

Common Fields:
- Timestamp: 4 bytes (32-bit unsigned int)
- Token: 2 bytes (16-bit unsigned int) when applicable
- CRC32: 4 bytes (32-bit unsigned int) - always at end

Message Structures:
===================

REGISTER: [Header(1)] [Timestamp(4)] [CRC32(4)] = 9 bytes

REGISTER_ACK: [Header(1)] [Timestamp(4)] [Token(2)] [CRC32(4)] = 11 bytes

DATA: [Header(1)] [Timestamp(4)] [Token(2)] [Payload(variable)] [CRC32(4)]

DATA_ACK: [Header(1)] [Timestamp(4)] [Status(1)] [CRC32(4)] = 10 bytes

ERROR: [Header(1)] [Timestamp(4)] [ErrorCode(1)] [Request(1)] [CRC32(4)] = 11 bytes

PING: [Header(1)] [Timestamp(4)] [CRC32(4)] = 9 bytes

PONG: [Header(1)] [Timestamp(4)] [Token(2)] [CRC32(4)] = 11 bytes

Data Payloads (device-specific):
=================================

ThermoNode (8 bytes):
- temperature: signed 16-bit (value * 10), range: -50.0 to 60.0, precision: 0.1
- humidity: unsigned 16-bit (value * 10), range: 0.0 to 100.0, precision: 0.1
- dew_point: signed 16-bit (value * 10), range: -50.0 to 60.0, precision: 0.1
- pressure: unsigned 16-bit (value * 100), range: 800.0 to 1100.0, precision: 0.01

WindSense (7 bytes):
- wind_speed: unsigned 16-bit (value * 10), range: 0.0 to 50.0, precision: 0.1
- wind_gust: unsigned 16-bit (value * 10), range: 0.0 to 70.0, precision: 0.1
- wind_direction: unsigned 16-bit, range: 0 to 359
- turbulence: unsigned 8-bit (value * 10), range: 0.0 to 1.0, precision: 0.1

RainDetect (7 bytes):
- rainfall: unsigned 16-bit (value * 10), range: 0.0 to 500.0, precision: 0.1
- soil_moisture: unsigned 16-bit (value * 10), range: 0.0 to 100.0, precision: 0.1
- flood_risk: unsigned 8-bit, range: 0 to 3
- rain_duration: unsigned 16-bit, range: 0 to 60

AirQualityBox (6 bytes):
- co2: unsigned 16-bit, range: 300 to 5000
- ozone: unsigned 16-bit (value * 10), range: 0.0 to 500.0, precision: 0.1
- air_quality_index: unsigned 16-bit, range: 0 to 500
"""

import struct
import zlib
import time

# Message types
MSG_REGISTER = 0
MSG_REGISTER_ACK = 1
MSG_DATA = 2
MSG_DATA_ACK = 3
MSG_ERROR = 4
MSG_PING = 5
MSG_PONG = 6

MSG_TYPE_NAMES = {
    MSG_REGISTER: "REGISTER",
    MSG_REGISTER_ACK: "REGISTER_ACK",
    MSG_DATA: "DATA",
    MSG_DATA_ACK: "DATA_ACK",
    MSG_ERROR: "ERROR",
    MSG_PING: "PING",
    MSG_PONG: "PONG"
}

# Device types
DEV_THERMONODE = 0
DEV_WINDSENSE = 1
DEV_RAINDETECT = 2
DEV_AIRQUALITYBOX = 3

DEVICE_TYPE_MAP = {
    "ThermoNode": DEV_THERMONODE,
    "WindSense": DEV_WINDSENSE,
    "RainDetect": DEV_RAINDETECT,
    "AirQualityBox": DEV_AIRQUALITYBOX
}

DEVICE_TYPE_NAMES = {v: k for k, v in DEVICE_TYPE_MAP.items()}

# Error codes
ERR_INVALID_TOKEN = 0
ERR_CRC_FAIL = 1

# Error request codes
REQ_NONE = 0
REQ_RESEND_LAST = 1


def calc_crc32(data: bytes) -> int:
    """Calculate CRC32 checksum of data"""
    return zlib.crc32(data) & 0xFFFFFFFF


def pack_header(msg_type: int, device_type: int, battery_low: bool = False) -> int:
    """Pack header byte"""
    header = msg_type & 0x07  # 3 bits for message type
    header |= (device_type & 0x03) << 3  # 2 bits for device type
    header |= (1 if battery_low else 0) << 5  # 1 bit for battery_low flag
    return header


def unpack_header(header: int) -> tuple:
    """Unpack header byte"""
    msg_type = header & 0x07
    device_type = (header >> 3) & 0x03
    battery_low = bool((header >> 5) & 0x01)
    return msg_type, device_type, battery_low


def encode_register(device_name: str) -> bytes:
    """Encode REGISTER message"""
    device_type = DEVICE_TYPE_MAP[device_name]
    header = pack_header(MSG_REGISTER, device_type)
    timestamp = int(time.time())

    # Pack without CRC first
    data = struct.pack('!BI', header, timestamp)

    # Calculate and append CRC
    crc = calc_crc32(data)
    data += struct.pack('!I', crc)

    return data


def decode_register(data: bytes) -> dict:
    """Decode REGISTER message"""
    if len(data) != 9:
        raise ValueError(f"Invalid REGISTER message length: {len(data)}")

    header, timestamp, crc = struct.unpack('!BII', data)

    # Verify CRC
    expected_crc = calc_crc32(data[:-4])
    if crc != expected_crc:
        raise ValueError(f"CRC mismatch: got {crc:08X}, expected {expected_crc:08X}")

    msg_type, device_type, battery_low = unpack_header(header)

    return {
        "type": "register",
        "device_type": DEVICE_TYPE_NAMES[device_type],
        "timestamp": timestamp,
        "battery_low": battery_low
    }


def encode_register_ack(device_name: str, token: int) -> bytes:
    """Encode REGISTER_ACK message"""
    device_type = DEVICE_TYPE_MAP[device_name]
    header = pack_header(MSG_REGISTER_ACK, device_type)
    timestamp = int(time.time())

    # Pack without CRC first
    data = struct.pack('!BIH', header, timestamp, token & 0xFFFF)

    # Calculate and append CRC
    crc = calc_crc32(data)
    data += struct.pack('!I', crc)

    return data


def decode_register_ack(data: bytes) -> dict:
    """Decode REGISTER_ACK message"""
    if len(data) != 11:
        raise ValueError(f"Invalid REGISTER_ACK message length: {len(data)}")

    header, timestamp, token, crc = struct.unpack('!BIHI', data)

    # Verify CRC
    expected_crc = calc_crc32(data[:-4])
    if crc != expected_crc:
        raise ValueError(f"CRC mismatch: got {crc:08X}, expected {expected_crc:08X}")

    msg_type, device_type, battery_low = unpack_header(header)

    return {
        "type": "register_ack",
        "device_type": DEVICE_TYPE_NAMES[device_type],
        "timestamp": timestamp,
        "token": token
    }


def encode_data_payload(device_name: str, data_dict: dict) -> bytes:
    """Encode device-specific data payload"""
    if device_name == "ThermoNode":
        # temperature, humidity, dew_point, pressure
        temp = int(data_dict["temperature"] * 10)
        humidity = int(data_dict["humidity"] * 10)
        dew = int(data_dict["dew_point"] * 10)
        # Pressure: offset from 800.0 hPa, stored in 0.01 hPa units
        # Range: 800.0 to 1100.0 → 0 to 30000 (fits in 16-bit)
        pressure = int((data_dict["pressure"] - 800.0) * 100)
        return struct.pack('!hHhH', temp, humidity, dew, pressure)

    elif device_name == "WindSense":
        # wind_speed, wind_gust, wind_direction, turbulence
        speed = int(data_dict["wind_speed"] * 10)
        gust = int(data_dict["wind_gust"] * 10)
        direction = int(data_dict["wind_direction"])
        turbulence = int(data_dict["turbulence"] * 10)
        return struct.pack('!HHHB', speed, gust, direction, turbulence)

    elif device_name == "RainDetect":
        # rainfall, soil_moisture, flood_risk, rain_duration
        rainfall = int(data_dict["rainfall"] * 10)
        moisture = int(data_dict["soil_moisture"] * 10)
        risk = int(data_dict["flood_risk"])
        duration = int(data_dict["rain_duration"])
        return struct.pack('!HHBH', rainfall, moisture, risk, duration)

    elif device_name == "AirQualityBox":
        # co2, ozone, air_quality_index
        co2 = int(data_dict["co2"])
        ozone = int(data_dict["ozone"] * 10)
        aqi = int(data_dict["air_quality_index"])
        return struct.pack('!HHH', co2, ozone, aqi)

    else:
        raise ValueError(f"Unknown device type: {device_name}")


def decode_data_payload(device_name: str, payload: bytes) -> dict:
    """Decode device-specific data payload"""
    if device_name == "ThermoNode":
        if len(payload) != 8:
            raise ValueError(f"Invalid ThermoNode payload length: {len(payload)}")
        temp, humidity, dew, pressure = struct.unpack('!hHhH', payload)
        return {
            "temperature": temp / 10.0,
            "humidity": humidity / 10.0,
            "dew_point": dew / 10.0,
            "pressure": (pressure / 100.0) + 800.0  # Add back the offset
        }

    elif device_name == "WindSense":
        if len(payload) != 7:
            raise ValueError(f"Invalid WindSense payload length: {len(payload)}")
        speed, gust, direction, turbulence = struct.unpack('!HHHB', payload)
        return {
            "wind_speed": speed / 10.0,
            "wind_gust": gust / 10.0,
            "wind_direction": direction,
            "turbulence": turbulence / 10.0
        }

    elif device_name == "RainDetect":
        if len(payload) != 7:
            raise ValueError(f"Invalid RainDetect payload length: {len(payload)}")
        rainfall, moisture, risk, duration = struct.unpack('!HHBH', payload)
        return {
            "rainfall": rainfall / 10.0,
            "soil_moisture": moisture / 10.0,
            "flood_risk": risk,
            "rain_duration": duration
        }

    elif device_name == "AirQualityBox":
        if len(payload) != 6:
            raise ValueError(f"Invalid AirQualityBox payload length: {len(payload)}")
        co2, ozone, aqi = struct.unpack('!HHH', payload)
        return {
            "co2": co2,
            "ozone": ozone / 10.0,
            "air_quality_index": aqi
        }

    else:
        raise ValueError(f"Unknown device type: {device_name}")


def encode_data(device_name: str, token: int, data_dict: dict, battery_low: bool = False, corrupt_crc: bool = False) -> bytes:
    """Encode DATA message"""
    device_type = DEVICE_TYPE_MAP[device_name]
    header = pack_header(MSG_DATA, device_type, battery_low)
    timestamp = int(time.time())

    # Encode payload
    payload = encode_data_payload(device_name, data_dict)

    # Pack without CRC first
    data = struct.pack('!BIH', header, timestamp, token & 0xFFFF) + payload

    # Calculate and append CRC
    crc = calc_crc32(data)
    if corrupt_crc:
        crc ^= 0xFF  # Flip some bits to corrupt it
    data += struct.pack('!I', crc)

    return data


def decode_data(data: bytes) -> dict:
    """Decode DATA message"""
    if len(data) < 11:
        raise ValueError(f"DATA message too short: {len(data)}")

    # Extract header, timestamp, token
    header, timestamp, token = struct.unpack('!BIH', data[:7])

    # Extract CRC from end
    crc = struct.unpack('!I', data[-4:])[0]

    # Verify CRC
    expected_crc = calc_crc32(data[:-4])
    if crc != expected_crc:
        raise ValueError(f"CRC mismatch: got {crc:08X}, expected {expected_crc:08X}")

    msg_type, device_type, battery_low = unpack_header(header)
    device_name = DEVICE_TYPE_NAMES[device_type]

    # Extract and decode payload
    payload = data[7:-4]
    data_dict = decode_data_payload(device_name, payload)

    return {
        "type": "data",
        "device_type": device_name,
        "timestamp": timestamp,
        "token": token,
        "battery_low": battery_low,
        "data": data_dict
    }


def encode_data_ack(device_name: str, status: str = "OK") -> bytes:
    """Encode DATA_ACK message"""
    device_type = DEVICE_TYPE_MAP[device_name]
    header = pack_header(MSG_DATA_ACK, device_type)
    timestamp = int(time.time())
    status_byte = 1 if status == "OK" else 0

    # Pack without CRC first
    data = struct.pack('!BIB', header, timestamp, status_byte)

    # Calculate and append CRC
    crc = calc_crc32(data)
    data += struct.pack('!I', crc)

    return data


def decode_data_ack(data: bytes) -> dict:
    """Decode DATA_ACK message"""
    if len(data) != 10:
        raise ValueError(f"Invalid DATA_ACK message length: {len(data)}")

    header, timestamp, status_byte, crc = struct.unpack('!BIBI', data)

    # Verify CRC
    expected_crc = calc_crc32(data[:-4])
    if crc != expected_crc:
        raise ValueError(f"CRC mismatch: got {crc:08X}, expected {expected_crc:08X}")

    msg_type, device_type, battery_low = unpack_header(header)

    return {
        "type": "data_ack",
        "device_type": DEVICE_TYPE_NAMES[device_type],
        "timestamp": timestamp,
        "status": "OK" if status_byte == 1 else "FAIL"
    }


def encode_error(device_name: str, error: str, request: str = None) -> bytes:
    """Encode ERROR message"""
    device_type = DEVICE_TYPE_MAP[device_name]
    header = pack_header(MSG_ERROR, device_type)
    timestamp = int(time.time())

    # Map error strings to codes
    error_code = ERR_CRC_FAIL if error == "CRC_FAIL" else ERR_INVALID_TOKEN
    request_code = REQ_RESEND_LAST if request == "resend_last" else REQ_NONE

    # Pack without CRC first
    data = struct.pack('!BIBB', header, timestamp, error_code, request_code)

    # Calculate and append CRC
    crc = calc_crc32(data)
    data += struct.pack('!I', crc)

    return data


def decode_error(data: bytes) -> dict:
    """Decode ERROR message"""
    if len(data) != 11:
        raise ValueError(f"Invalid ERROR message length: {len(data)}")

    header, timestamp, error_code, request_code, crc = struct.unpack('!BIBBI', data)

    # Verify CRC
    expected_crc = calc_crc32(data[:-4])
    if crc != expected_crc:
        raise ValueError(f"CRC mismatch: got {crc:08X}, expected {expected_crc:08X}")

    msg_type, device_type, battery_low = unpack_header(header)

    # Map codes to strings
    error_str = "CRC_FAIL" if error_code == ERR_CRC_FAIL else "INVALID_TOKEN"
    request_str = "resend_last" if request_code == REQ_RESEND_LAST else None

    result = {
        "type": "error",
        "device_type": DEVICE_TYPE_NAMES[device_type],
        "timestamp": timestamp,
        "error": error_str
    }

    if request_str:
        result["request"] = request_str

    return result


def encode_ping(device_name: str) -> bytes:
    """Encode PING message"""
    device_type = DEVICE_TYPE_MAP[device_name]
    header = pack_header(MSG_PING, device_type)
    timestamp = int(time.time())

    # Pack without CRC first
    data = struct.pack('!BI', header, timestamp)

    # Calculate and append CRC
    crc = calc_crc32(data)
    data += struct.pack('!I', crc)

    return data


def decode_ping(data: bytes) -> dict:
    """Decode PING message"""
    if len(data) != 9:
        raise ValueError(f"Invalid PING message length: {len(data)}")

    header, timestamp, crc = struct.unpack('!BII', data)

    # Verify CRC
    expected_crc = calc_crc32(data[:-4])
    if crc != expected_crc:
        raise ValueError(f"CRC mismatch: got {crc:08X}, expected {expected_crc:08X}")

    msg_type, device_type, battery_low = unpack_header(header)

    return {
        "type": "ping",
        "device_type": DEVICE_TYPE_NAMES[device_type],
        "timestamp": timestamp
    }


def encode_pong(device_name: str, token: int) -> bytes:
    """Encode PONG message"""
    device_type = DEVICE_TYPE_MAP[device_name]
    header = pack_header(MSG_PONG, device_type)
    timestamp = int(time.time())

    # Pack without CRC first
    data = struct.pack('!BIH', header, timestamp, token & 0xFFFF)

    # Calculate and append CRC
    crc = calc_crc32(data)
    data += struct.pack('!I', crc)

    return data


def decode_pong(data: bytes) -> dict:
    """Decode PONG message"""
    if len(data) != 11:
        raise ValueError(f"Invalid PONG message length: {len(data)}")

    header, timestamp, token, crc = struct.unpack('!BIHI', data)

    # Verify CRC
    expected_crc = calc_crc32(data[:-4])
    if crc != expected_crc:
        raise ValueError(f"CRC mismatch: got {crc:08X}, expected {expected_crc:08X}")

    msg_type, device_type, battery_low = unpack_header(header)

    return {
        "type": "pong",
        "device_type": DEVICE_TYPE_NAMES[device_type],
        "timestamp": timestamp,
        "token": token
    }


def decode_message(data: bytes) -> dict:
    """Decode any message type"""
    if len(data) < 9:
        raise ValueError(f"Message too short: {len(data)}")

    header = data[0]
    msg_type, device_type, battery_low = unpack_header(header)

    if msg_type == MSG_REGISTER:
        return decode_register(data)
    elif msg_type == MSG_REGISTER_ACK:
        return decode_register_ack(data)
    elif msg_type == MSG_DATA:
        return decode_data(data)
    elif msg_type == MSG_DATA_ACK:
        return decode_data_ack(data)
    elif msg_type == MSG_ERROR:
        return decode_error(data)
    elif msg_type == MSG_PING:
        return decode_ping(data)
    elif msg_type == MSG_PONG:
        return decode_pong(data)
    else:
        raise ValueError(f"Unknown message type: {msg_type}")

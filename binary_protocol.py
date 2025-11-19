"""
Binary protocol implementation for sensor communication.
Efficient binary encoding with minimal bit usage.
"""

import struct
import crc

# Message types (3 bits)
MSG_TYPE_REGISTER = 0
MSG_TYPE_ACK = 1
MSG_TYPE_DATA = 2
MSG_TYPE_PING = 3
MSG_TYPE_PING_RESPONSE = 4
MSG_TYPE_CHECKSUM_ERROR = 5
MSG_TYPE_INVALID_TOKEN = 6
MSG_TYPE_ERROR = 7

# Device types (2 bits)
DEVICE_TYPE_THERMONODE = 0
DEVICE_TYPE_WINDSENSE = 1
DEVICE_TYPE_RAINDETECT = 2
DEVICE_TYPE_AIRQUALITYBOX = 3

DEVICE_NAME_TO_TYPE = {
    "ThermoNode": DEVICE_TYPE_THERMONODE,
    "WindSense": DEVICE_TYPE_WINDSENSE,
    "RainDetect": DEVICE_TYPE_RAINDETECT,
    "AirQualityBox": DEVICE_TYPE_AIRQUALITYBOX,
}

DEVICE_TYPE_TO_NAME = {
    DEVICE_TYPE_THERMONODE: "ThermoNode",
    DEVICE_TYPE_WINDSENSE: "WindSense",
    DEVICE_TYPE_RAINDETECT: "RainDetect",
    DEVICE_TYPE_AIRQUALITYBOX: "AirQualityBox",
}


class BitWriter:
    """Helper class for writing bits to a byte buffer."""
    def __init__(self):
        self.bytes = bytearray()
        self.current_byte = 0
        self.bit_pos = 0

    def write_bits(self, value, num_bits):
        """Write num_bits from value to the buffer."""
        for i in range(num_bits - 1, -1, -1):
            bit = (value >> i) & 1
            self.current_byte = (self.current_byte << 1) | bit
            self.bit_pos += 1
            if self.bit_pos == 8:
                self.bytes.append(self.current_byte)
                self.current_byte = 0
                self.bit_pos = 0

    def flush(self):
        """Flush remaining bits with padding."""
        if self.bit_pos > 0:
            self.current_byte <<= (8 - self.bit_pos)
            self.bytes.append(self.current_byte)
            self.current_byte = 0
            self.bit_pos = 0
        return bytes(self.bytes)


class BitReader:
    """Helper class for reading bits from a byte buffer."""
    def __init__(self, data):
        self.data = data
        self.byte_pos = 0
        self.bit_pos = 0

    def read_bits(self, num_bits):
        """Read num_bits from the buffer."""
        value = 0
        for _ in range(num_bits):
            if self.byte_pos >= len(self.data):
                raise ValueError("Not enough data to read")
            byte = self.data[self.byte_pos]
            bit = (byte >> (7 - self.bit_pos)) & 1
            value = (value << 1) | bit
            self.bit_pos += 1
            if self.bit_pos == 8:
                self.byte_pos += 1
                self.bit_pos = 0
        return value

    def align_to_byte(self):
        """Skip to next byte boundary."""
        if self.bit_pos > 0:
            self.byte_pos += 1
            self.bit_pos = 0


def calculate_checksum(data):
    """Calculate CRC32 checksum of binary data."""
    crc32_func = crc.Calculator(crc.Crc32.CRC32)
    return crc32_func.checksum(data)


def token_to_bytes(token):
    """Convert token string (TKN-XXXXXXXXXXXX) to 12 bytes."""
    if not token:
        return b'\x00' * 12
    if token.startswith("TKN-"):
        token = token[4:]
    # Pad or truncate to 12 characters
    token = token.ljust(12, '0')[:12]
    return token.encode('ascii')


def bytes_to_token(token_bytes):
    """Convert 12 bytes to token string."""
    token_str = token_bytes.decode('ascii').rstrip('0')
    if not token_str:
        return ""
    return "TKN-" + token_str


def encode_thermonode_payload(payload):
    """Encode ThermoNode payload to bits.
    - temp: -50.0 .. 60.0, 0.1 resolution -> 11 bits
    - hum: 0.0 .. 100.0, 0.1 resolution -> 10 bits
    - dew: -50.0 .. 60.0, 0.1 resolution -> 11 bits
    - pressure: 800.0 .. 1100.0, 0.01 resolution -> 15 bits
    Total: 47 bits
    """
    writer = BitWriter()

    # Parse temp (e.g., "23.4°C")
    temp_str = payload.get("temp", "0.0°C").replace("°C", "")
    temp = float(temp_str)
    temp_encoded = int((temp + 50.0) * 10)  # -50..60 -> 0..1100
    temp_encoded = max(0, min(1100, temp_encoded))
    writer.write_bits(temp_encoded, 11)

    # Parse hum (e.g., "50.5%")
    hum_str = payload.get("hum", "0.0%").replace("%", "")
    hum = float(hum_str)
    hum_encoded = int(hum * 10)  # 0..100 -> 0..1000
    hum_encoded = max(0, min(1000, hum_encoded))
    writer.write_bits(hum_encoded, 10)

    # Parse dew (e.g., "10.2°C")
    dew_str = payload.get("dew", "0.0°C").replace("°C", "")
    dew = float(dew_str)
    dew_encoded = int((dew + 50.0) * 10)  # -50..60 -> 0..1100
    dew_encoded = max(0, min(1100, dew_encoded))
    writer.write_bits(dew_encoded, 11)

    # Parse pressure (e.g., "1013.25hPa")
    pressure_str = payload.get("pressure", "800.0hPa").replace("hPa", "")
    pressure = float(pressure_str)
    pressure_encoded = int((pressure - 800.0) * 100)  # 800..1100 -> 0..30000
    pressure_encoded = max(0, min(30000, pressure_encoded))
    writer.write_bits(pressure_encoded, 15)

    return writer.flush()


def decode_thermonode_payload(reader):
    """Decode ThermoNode payload from bits."""
    temp_encoded = reader.read_bits(11)
    temp = (temp_encoded / 10.0) - 50.0

    hum_encoded = reader.read_bits(10)
    hum = hum_encoded / 10.0

    dew_encoded = reader.read_bits(11)
    dew = (dew_encoded / 10.0) - 50.0

    pressure_encoded = reader.read_bits(15)
    pressure = (pressure_encoded / 100.0) + 800.0

    return {
        "temp": f"{temp:.1f}°C",
        "hum": f"{hum:.1f}%",
        "dew": f"{dew:.1f}°C",
        "pressure": f"{pressure:.2f}hPa"
    }


def encode_windsense_payload(payload):
    """Encode WindSense payload to bits.
    - speed: 0.0 .. 50.0, 0.1 resolution -> 9 bits
    - gust: 0.0 .. 70.0, 0.1 resolution -> 10 bits
    - direction: 0 .. 359 -> 9 bits
    - turbulance: 0.0 .. 1.0, 0.1 resolution -> 4 bits
    Total: 32 bits
    """
    writer = BitWriter()

    # Parse speed (e.g., "12.3m/s")
    speed_str = payload.get("speed", "0.0m/s").replace("m/s", "")
    speed = float(speed_str)
    speed_encoded = int(speed * 10)  # 0..50 -> 0..500
    speed_encoded = max(0, min(500, speed_encoded))
    writer.write_bits(speed_encoded, 9)

    # Parse gust (e.g., "15.2m/s")
    gust_str = payload.get("gust", "0.0m/s").replace("m/s", "")
    gust = float(gust_str)
    gust_encoded = int(gust * 10)  # 0..70 -> 0..700
    gust_encoded = max(0, min(700, gust_encoded))
    writer.write_bits(gust_encoded, 10)

    # Parse direction (e.g., "270°")
    direction_str = payload.get("direction", "0°").replace("°", "")
    direction = int(direction_str)
    direction = max(0, min(359, direction))
    writer.write_bits(direction, 9)

    # Parse turbulance (e.g., "0.5")
    turbulance_str = payload.get("turbulance", "0.0")
    turbulance = float(turbulance_str)
    turbulance_encoded = int(turbulance * 10)  # 0..1 -> 0..10
    turbulance_encoded = max(0, min(10, turbulance_encoded))
    writer.write_bits(turbulance_encoded, 4)

    return writer.flush()


def decode_windsense_payload(reader):
    """Decode WindSense payload from bits."""
    speed_encoded = reader.read_bits(9)
    speed = speed_encoded / 10.0

    gust_encoded = reader.read_bits(10)
    gust = gust_encoded / 10.0

    direction = reader.read_bits(9)

    turbulance_encoded = reader.read_bits(4)
    turbulance = turbulance_encoded / 10.0

    return {
        "speed": f"{speed:.1f}m/s",
        "gust": f"{gust:.1f}m/s",
        "direction": f"{direction}°",
        "turbulance": f"{turbulance:.1f}"
    }


def encode_raindetect_payload(payload):
    """Encode RainDetect payload to bits.
    - rainfall: 0.0 .. 500.0, 0.1 resolution -> 13 bits
    - soil: 0.0 .. 100.0, 0.1 resolution -> 10 bits
    - flood: 0 .. 3 -> 2 bits
    - duration: 0 .. 60 -> 6 bits
    Total: 31 bits
    """
    writer = BitWriter()

    # Parse rainfall (e.g., "25.3mm")
    rainfall_str = payload.get("rainfall", "0.0mm").replace("mm", "")
    rainfall = float(rainfall_str)
    rainfall_encoded = int(rainfall * 10)  # 0..500 -> 0..5000
    rainfall_encoded = max(0, min(5000, rainfall_encoded))
    writer.write_bits(rainfall_encoded, 13)

    # Parse soil (e.g., "45.2%")
    soil_str = payload.get("soil", "0.0%").replace("%", "")
    soil = float(soil_str)
    soil_encoded = int(soil * 10)  # 0..100 -> 0..1000
    soil_encoded = max(0, min(1000, soil_encoded))
    writer.write_bits(soil_encoded, 10)

    # Parse flood (e.g., "2")
    flood_str = payload.get("flood", "0")
    flood = int(flood_str)
    flood = max(0, min(3, flood))
    writer.write_bits(flood, 2)

    # Parse duration (e.g., "45s" or "45")
    duration_str = payload.get("duration", "0").replace("s", "")
    duration = int(duration_str)
    duration = max(0, min(60, duration))
    writer.write_bits(duration, 6)

    return writer.flush()


def decode_raindetect_payload(reader):
    """Decode RainDetect payload from bits."""
    rainfall_encoded = reader.read_bits(13)
    rainfall = rainfall_encoded / 10.0

    soil_encoded = reader.read_bits(10)
    soil = soil_encoded / 10.0

    flood = reader.read_bits(2)

    duration = reader.read_bits(6)

    return {
        "rainfall": f"{rainfall:.1f}mm",
        "soil": f"{soil:.1f}%",
        "flood": str(flood),
        "duration": str(duration)
    }


def encode_airqualitybox_payload(payload):
    """Encode AirQualityBox payload to bits.
    - CO2: 300 .. 5000 -> 13 bits
    - ozone: 0.0 .. 500.0, 0.1 resolution -> 13 bits
    - quality: 0 .. 500 -> 9 bits
    Total: 35 bits
    """
    writer = BitWriter()

    # Parse CO2 (e.g., "450ppm")
    CO2_str = payload.get("CO2", "300ppm").replace("ppm", "")
    CO2 = int(CO2_str)
    CO2_encoded = CO2 - 300  # 300..5000 -> 0..4700
    CO2_encoded = max(0, min(4700, CO2_encoded))
    writer.write_bits(CO2_encoded, 13)

    # Parse ozone (e.g., "12.5µg/m³")
    ozone_str = payload.get("ozone", "0.0µg/m³").replace("µg/m³", "")
    ozone = float(ozone_str)
    ozone_encoded = int(ozone * 10)  # 0..500 -> 0..5000
    ozone_encoded = max(0, min(5000, ozone_encoded))
    writer.write_bits(ozone_encoded, 13)

    # Parse quality (e.g., "125AQI")
    quality_str = payload.get("quality", "0AQI").replace("AQI", "")
    quality = int(quality_str)
    quality = max(0, min(500, quality))
    writer.write_bits(quality, 9)

    return writer.flush()


def decode_airqualitybox_payload(reader):
    """Decode AirQualityBox payload from bits."""
    CO2_encoded = reader.read_bits(13)
    CO2 = CO2_encoded + 300

    ozone_encoded = reader.read_bits(13)
    ozone = ozone_encoded / 10.0

    quality = reader.read_bits(9)

    return {
        "CO2": f"{CO2}ppm",
        "ozone": f"{ozone:.1f}µg/m³",
        "quality": f"{quality}AQI"
    }


def encode_message(msg):
    """Encode a message dictionary to binary format.

    Returns bytes with checksum appended at the end.
    """
    writer = BitWriter()
    msg_type_str = msg.get("type", "error")

    # Map message type string to numeric type
    type_map = {
        "register": MSG_TYPE_REGISTER,
        "ack": MSG_TYPE_ACK,
        "data": MSG_TYPE_DATA,
        "ping": MSG_TYPE_PING,
        "ping_response": MSG_TYPE_PING_RESPONSE,
        "checksum_error": MSG_TYPE_CHECKSUM_ERROR,
        "invalid_token": MSG_TYPE_INVALID_TOKEN,
        "error": MSG_TYPE_ERROR
    }
    msg_type = type_map.get(msg_type_str, MSG_TYPE_ERROR)

    # Write message type (3 bits)
    writer.write_bits(msg_type, 3)

    if msg_type == MSG_TYPE_REGISTER:
        # Register: type(3) + device_type(2) + timestamp(32) + low_battery(1) + padding(2)
        device_type = DEVICE_NAME_TO_TYPE.get(msg.get("device_type", "ThermoNode"), 0)
        writer.write_bits(device_type, 2)
        writer.write_bits(msg.get("timestamp", 0), 32)
        writer.write_bits(1 if msg.get("low_battery", False) else 0, 1)
        writer.write_bits(0, 2)  # padding

    elif msg_type == MSG_TYPE_ACK:
        # ACK: type(3) + device_type(2) + timestamp(32) + token(96) + padding(3)
        device_type = DEVICE_NAME_TO_TYPE.get(msg.get("device_type", "ThermoNode"), 0)
        writer.write_bits(device_type, 2)
        writer.write_bits(msg.get("timestamp", 0), 32)
        writer.write_bits(0, 3)  # padding to align
        # Flush and append token bytes
        data_so_far = writer.flush()
        token_bytes = token_to_bytes(msg.get("token", ""))
        data_so_far += token_bytes
        # Calculate and append checksum
        checksum = calculate_checksum(data_so_far)
        final_data = data_so_far + struct.pack('>I', checksum)
        return final_data

    elif msg_type == MSG_TYPE_DATA:
        # Data: type(3) + device_type(2) + timestamp(32) + low_battery(1) + padding(2) + token(96) + payload(variable)
        device_type = DEVICE_NAME_TO_TYPE.get(msg.get("device_type", "ThermoNode"), 0)
        writer.write_bits(device_type, 2)
        writer.write_bits(msg.get("timestamp", 0), 32)
        writer.write_bits(1 if msg.get("low_battery", False) else 0, 1)
        writer.write_bits(0, 2)  # padding
        # Flush and append token
        data_so_far = writer.flush()
        token_bytes = token_to_bytes(msg.get("token", ""))
        data_so_far += token_bytes

        # Encode payload based on device type
        payload = msg.get("payload", {})
        device_name = msg.get("device_type", "ThermoNode")

        if device_name == "ThermoNode":
            payload_bytes = encode_thermonode_payload(payload)
        elif device_name == "WindSense":
            payload_bytes = encode_windsense_payload(payload)
        elif device_name == "RainDetect":
            payload_bytes = encode_raindetect_payload(payload)
        elif device_name == "AirQualityBox":
            payload_bytes = encode_airqualitybox_payload(payload)
        else:
            payload_bytes = b''

        data_so_far += payload_bytes
        # Calculate and append checksum
        checksum = calculate_checksum(data_so_far)
        final_data = data_so_far + struct.pack('>I', checksum)
        return final_data

    elif msg_type == MSG_TYPE_PING:
        # Ping: type(3) + timestamp(32) + padding(5) + token(96)
        writer.write_bits(msg.get("timestamp", 0), 32)
        writer.write_bits(0, 5)  # padding
        data_so_far = writer.flush()
        token_bytes = token_to_bytes(msg.get("token", ""))
        data_so_far += token_bytes
        checksum = calculate_checksum(data_so_far)
        final_data = data_so_far + struct.pack('>I', checksum)
        return final_data

    elif msg_type == MSG_TYPE_PING_RESPONSE:
        # Ping response: type(3) + device_type(2) + timestamp(32) + padding(3) + token(96)
        device_type = DEVICE_NAME_TO_TYPE.get(msg.get("device_type", "ThermoNode"), 0)
        writer.write_bits(device_type, 2)
        writer.write_bits(msg.get("timestamp", 0), 32)
        writer.write_bits(0, 3)  # padding
        data_so_far = writer.flush()
        token_bytes = token_to_bytes(msg.get("token", ""))
        data_so_far += token_bytes
        checksum = calculate_checksum(data_so_far)
        final_data = data_so_far + struct.pack('>I', checksum)
        return final_data

    elif msg_type == MSG_TYPE_CHECKSUM_ERROR:
        # Checksum error: type(3) + timestamp(32) + padding(3) + message_length(8) + message(variable)
        writer.write_bits(msg.get("timestamp", 0), 32)
        writer.write_bits(0, 3)  # padding
        data_so_far = writer.flush()
        message_str = msg.get("message", "")
        message_bytes = message_str.encode('utf-8')
        message_len = min(len(message_bytes), 255)
        data_so_far += struct.pack('B', message_len)
        data_so_far += message_bytes[:message_len]
        checksum = calculate_checksum(data_so_far)
        final_data = data_so_far + struct.pack('>I', checksum)
        return final_data

    elif msg_type == MSG_TYPE_INVALID_TOKEN:
        # Invalid token: type(3) + timestamp(32) + padding(3) + token(96) + reason_length(8) + reason(variable)
        writer.write_bits(msg.get("timestamp", 0), 32)
        writer.write_bits(0, 3)  # padding
        data_so_far = writer.flush()
        token_bytes = token_to_bytes(msg.get("token", ""))
        data_so_far += token_bytes
        reason_str = msg.get("reason", "")
        reason_bytes = reason_str.encode('utf-8')
        reason_len = min(len(reason_bytes), 255)
        data_so_far += struct.pack('B', reason_len)
        data_so_far += reason_bytes[:reason_len]
        checksum = calculate_checksum(data_so_far)
        final_data = data_so_far + struct.pack('>I', checksum)
        return final_data

    elif msg_type == MSG_TYPE_ERROR:
        # Error: type(3) + timestamp(32) + padding(3) + message_length(8) + message(variable)
        writer.write_bits(msg.get("timestamp", 0), 32)
        writer.write_bits(0, 3)  # padding
        data_so_far = writer.flush()
        message_str = msg.get("message", "")
        message_bytes = message_str.encode('utf-8')
        message_len = min(len(message_bytes), 255)
        data_so_far += struct.pack('B', message_len)
        data_so_far += message_bytes[:message_len]
        checksum = calculate_checksum(data_so_far)
        final_data = data_so_far + struct.pack('>I', checksum)
        return final_data

    # Default: flush and add checksum
    data = writer.flush()
    checksum = calculate_checksum(data)
    return data + struct.pack('>I', checksum)


def decode_message(data):
    """Decode a binary message to dictionary format.

    Returns a dictionary with the message fields.
    """
    if len(data) < 5:  # Minimum: type(1 byte) + checksum(4 bytes)
        raise ValueError("Message too short")

    # Extract and verify checksum
    payload_data = data[:-4]
    received_checksum = struct.unpack('>I', data[-4:])[0]
    expected_checksum = calculate_checksum(payload_data)

    if received_checksum != expected_checksum:
        # Return a special dict indicating checksum error
        return {"_checksum_valid": False}

    reader = BitReader(payload_data)

    # Read message type (3 bits)
    msg_type = reader.read_bits(3)

    type_name_map = {
        MSG_TYPE_REGISTER: "register",
        MSG_TYPE_ACK: "ack",
        MSG_TYPE_DATA: "data",
        MSG_TYPE_PING: "ping",
        MSG_TYPE_PING_RESPONSE: "ping_response",
        MSG_TYPE_CHECKSUM_ERROR: "checksum_error",
        MSG_TYPE_INVALID_TOKEN: "invalid_token",
        MSG_TYPE_ERROR: "error"
    }

    msg = {
        "type": type_name_map.get(msg_type, "error"),
        "_checksum_valid": True
    }

    if msg_type == MSG_TYPE_REGISTER:
        device_type = reader.read_bits(2)
        msg["device_type"] = DEVICE_TYPE_TO_NAME.get(device_type, "ThermoNode")
        msg["timestamp"] = reader.read_bits(32)
        msg["low_battery"] = bool(reader.read_bits(1))
        reader.read_bits(2)  # padding
        msg["token"] = ""

    elif msg_type == MSG_TYPE_ACK:
        device_type = reader.read_bits(2)
        msg["device_type"] = DEVICE_TYPE_TO_NAME.get(device_type, "ThermoNode")
        msg["timestamp"] = reader.read_bits(32)
        reader.read_bits(3)  # padding
        reader.align_to_byte()
        token_bytes = payload_data[reader.byte_pos:reader.byte_pos+12]
        msg["token"] = bytes_to_token(token_bytes)

    elif msg_type == MSG_TYPE_DATA:
        device_type = reader.read_bits(2)
        device_name = DEVICE_TYPE_TO_NAME.get(device_type, "ThermoNode")
        msg["device_type"] = device_name
        msg["timestamp"] = reader.read_bits(32)
        msg["low_battery"] = bool(reader.read_bits(1))
        reader.read_bits(2)  # padding
        reader.align_to_byte()
        token_bytes = payload_data[reader.byte_pos:reader.byte_pos+12]
        msg["token"] = bytes_to_token(token_bytes)
        reader.byte_pos += 12

        # Decode payload based on device type
        payload_reader = BitReader(payload_data[reader.byte_pos:])

        if device_name == "ThermoNode":
            msg["payload"] = decode_thermonode_payload(payload_reader)
        elif device_name == "WindSense":
            msg["payload"] = decode_windsense_payload(payload_reader)
        elif device_name == "RainDetect":
            msg["payload"] = decode_raindetect_payload(payload_reader)
        elif device_name == "AirQualityBox":
            msg["payload"] = decode_airqualitybox_payload(payload_reader)
        else:
            msg["payload"] = {}

    elif msg_type == MSG_TYPE_PING:
        msg["timestamp"] = reader.read_bits(32)
        reader.read_bits(5)  # padding
        reader.align_to_byte()
        token_bytes = payload_data[reader.byte_pos:reader.byte_pos+12]
        msg["token"] = bytes_to_token(token_bytes)

    elif msg_type == MSG_TYPE_PING_RESPONSE:
        device_type = reader.read_bits(2)
        msg["device_type"] = DEVICE_TYPE_TO_NAME.get(device_type, "ThermoNode")
        msg["timestamp"] = reader.read_bits(32)
        reader.read_bits(3)  # padding
        reader.align_to_byte()
        token_bytes = payload_data[reader.byte_pos:reader.byte_pos+12]
        msg["token"] = bytes_to_token(token_bytes)

    elif msg_type == MSG_TYPE_CHECKSUM_ERROR:
        msg["timestamp"] = reader.read_bits(32)
        reader.read_bits(3)  # padding
        reader.align_to_byte()
        message_len = payload_data[reader.byte_pos]
        reader.byte_pos += 1
        message_bytes = payload_data[reader.byte_pos:reader.byte_pos+message_len]
        msg["message"] = message_bytes.decode('utf-8', errors='ignore')

    elif msg_type == MSG_TYPE_INVALID_TOKEN:
        msg["timestamp"] = reader.read_bits(32)
        reader.read_bits(3)  # padding
        reader.align_to_byte()
        token_bytes = payload_data[reader.byte_pos:reader.byte_pos+12]
        msg["token"] = bytes_to_token(token_bytes)
        reader.byte_pos += 12
        reason_len = payload_data[reader.byte_pos]
        reader.byte_pos += 1
        reason_bytes = payload_data[reader.byte_pos:reader.byte_pos+reason_len]
        msg["reason"] = reason_bytes.decode('utf-8', errors='ignore')

    elif msg_type == MSG_TYPE_ERROR:
        msg["timestamp"] = reader.read_bits(32)
        reader.read_bits(3)  # padding
        reader.align_to_byte()
        message_len = payload_data[reader.byte_pos]
        reader.byte_pos += 1
        message_bytes = payload_data[reader.byte_pos:reader.byte_pos+message_len]
        msg["message"] = message_bytes.decode('utf-8', errors='ignore')

    return msg

"""
FIITMeteo Server - Binary UDP Protocol
Course Assignment: PKS-B
"""

import asyncio
import time
import struct
import zlib

# ============================================================================
# BINARY PROTOCOL MODULE (Embedded)
# ============================================================================

# Message types
MSG_REGISTER = 0
MSG_REGISTER_ACK = 1
MSG_DATA = 2
MSG_DATA_ACK = 3
MSG_ERROR = 4
MSG_PING = 5
MSG_PONG = 6

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
    header = msg_type & 0x07
    header |= (device_type & 0x03) << 3
    header |= (1 if battery_low else 0) << 5
    return header


def unpack_header(header: int) -> tuple:
    """Unpack header byte"""
    msg_type = header & 0x07
    device_type = (header >> 3) & 0x03
    battery_low = bool((header >> 5) & 0x01)
    return msg_type, device_type, battery_low


def encode_register_ack(device_name: str, token: int) -> bytes:
    """Encode REGISTER_ACK message"""
    device_type = DEVICE_TYPE_MAP[device_name]
    header = pack_header(MSG_REGISTER_ACK, device_type)
    timestamp = int(time.time())
    data = struct.pack('!BIH', header, timestamp, token & 0xFFFF)
    crc = calc_crc32(data)
    data += struct.pack('!I', crc)
    return data


def encode_data_ack(device_name: str, status: str = "OK") -> bytes:
    """Encode DATA_ACK message"""
    device_type = DEVICE_TYPE_MAP[device_name]
    header = pack_header(MSG_DATA_ACK, device_type)
    timestamp = int(time.time())
    status_byte = 1 if status == "OK" else 0
    data = struct.pack('!BIB', header, timestamp, status_byte)
    crc = calc_crc32(data)
    data += struct.pack('!I', crc)
    return data


def encode_error(device_name: str, error: str, request: str = None) -> bytes:
    """Encode ERROR message"""
    device_type = DEVICE_TYPE_MAP[device_name]
    header = pack_header(MSG_ERROR, device_type)
    timestamp = int(time.time())
    error_code = ERR_CRC_FAIL if error == "CRC_FAIL" else ERR_INVALID_TOKEN
    request_code = REQ_RESEND_LAST if request == "resend_last" else REQ_NONE
    data = struct.pack('!BIBB', header, timestamp, error_code, request_code)
    crc = calc_crc32(data)
    data += struct.pack('!I', crc)
    return data


def encode_ping(device_name: str) -> bytes:
    """Encode PING message"""
    device_type = DEVICE_TYPE_MAP[device_name]
    header = pack_header(MSG_PING, device_type)
    timestamp = int(time.time())
    data = struct.pack('!BI', header, timestamp)
    crc = calc_crc32(data)
    data += struct.pack('!I', crc)
    return data


def decode_data_payload(device_name: str, payload: bytes) -> dict:
    """Decode device-specific data payload"""
    if device_name == "ThermoNode":
        temp, humidity, dew, pressure = struct.unpack('!hHhH', payload)
        return {
            "temperature": temp / 10.0,
            "humidity": humidity / 10.0,
            "dew_point": dew / 10.0,
            "pressure": (pressure / 100.0) + 800.0
        }
    elif device_name == "WindSense":
        speed, gust, direction, turbulence = struct.unpack('!HHHB', payload)
        return {
            "wind_speed": speed / 10.0,
            "wind_gust": gust / 10.0,
            "wind_direction": direction,
            "turbulence": turbulence / 10.0
        }
    elif device_name == "RainDetect":
        rainfall, moisture, risk, duration = struct.unpack('!HHBH', payload)
        return {
            "rainfall": rainfall / 10.0,
            "soil_moisture": moisture / 10.0,
            "flood_risk": risk,
            "rain_duration": duration
        }
    elif device_name == "AirQualityBox":
        co2, ozone, aqi = struct.unpack('!HHH', payload)
        return {
            "co2": co2,
            "ozone": ozone / 10.0,
            "air_quality_index": aqi
        }


def decode_message(data: bytes) -> dict:
    """Decode any message type"""
    if len(data) < 9:
        raise ValueError(f"Message too short: {len(data)}")

    header = data[0]
    msg_type, device_type, battery_low = unpack_header(header)
    device_name = DEVICE_TYPE_NAMES[device_type]

    if msg_type == MSG_REGISTER:
        header, timestamp, crc = struct.unpack('!BII', data)
        expected_crc = calc_crc32(data[:-4])
        if crc != expected_crc:
            raise ValueError(f"CRC mismatch: got {crc:08X}, expected {expected_crc:08X}")
        return {
            "type": "register",
            "device_type": device_name,
            "timestamp": timestamp,
            "battery_low": battery_low
        }
    elif msg_type == MSG_DATA:
        header, timestamp, token = struct.unpack('!BIH', data[:7])
        crc = struct.unpack('!I', data[-4:])[0]
        expected_crc = calc_crc32(data[:-4])
        if crc != expected_crc:
            raise ValueError(f"CRC mismatch: got {crc:08X}, expected {expected_crc:08X}")
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
    elif msg_type == MSG_PONG:
        header, timestamp, token, crc = struct.unpack('!BIHI', data)
        expected_crc = calc_crc32(data[:-4])
        if crc != expected_crc:
            raise ValueError(f"CRC mismatch: got {crc:08X}, expected {expected_crc:08X}")
        return {
            "type": "pong",
            "device_type": device_name,
            "timestamp": timestamp,
            "token": token
        }
    else:
        raise ValueError(f"Unknown message type: {msg_type}")


# ============================================================================
# SERVER IMPLEMENTATION
# ============================================================================

SERVER_IP = "127.0.0.1"
SERVER_PORT = 9999
registered_devices = {}
ignore_acks_for = None  # UAT5
activity_interval = 5
timeout_seconds = 15


def current_time():
    return int(time.time())


async def handle_message(message, addr, transport):
    global ignore_acks_for
    try:
        data = decode_message(message)
        msg_type = data.get("type")
        device_type = data.get("device_type")

        if msg_type == "register":
            token = int(time.time()) % 65536  # 16-bit token
            registered_devices[device_type] = {
                "token": token,
                "last_seen": time.time(),
                "address": addr,
                "disconnected": False,
                "ping_attempts": 0
            }
            print(f"INFO: {device_type} REGISTERED at {current_time()}")
            response = encode_register_ack(device_type, token)
            transport.sendto(response, addr)

        elif msg_type == "data":
            token = data.get("token")
            if device_type not in registered_devices or registered_devices[device_type]["token"] != token:
                response = encode_error(device_type, "INVALID_TOKEN")
                transport.sendto(response, addr)
                return

            # Update last activity time and reconnect if needed
            device_info = registered_devices[device_type]
            device_info["last_seen"] = time.time()
            device_info["ping_attempts"] = 0

            if device_info.get("disconnected"):
                device_info["disconnected"] = False
                print(f"INFO: {device_type} RECONNECTED!")

            battery = data.get("battery_low", False)

            if battery:
                print(f"{data['timestamp']} - WARNING: LOW BATTERY {device_type}")
            else:
                print(f"{data['timestamp']} - {device_type}")

            param_str = ""
            for k, v in data["data"].items():
                param_str += f"{k}: {v}; "
            print(param_str)

            if ignore_acks_for == device_type:
                if "no_ack_count" not in registered_devices[device_type]:
                    registered_devices[device_type]["no_ack_count"] = 0
                registered_devices[device_type]["no_ack_count"] += 1
                if registered_devices[device_type]["no_ack_count"] <= 3:
                    print(
                        f"[DEBUG] Ignorujem ACK pre {device_type} ({registered_devices[device_type]['no_ack_count']}/3)")
                    return
                else:
                    print(f"[DEBUG] Teraz posielam ACK pre {device_type}")
                    registered_devices[device_type]["no_ack_count"] = 0
                    ignore_acks_for = None

            response = encode_data_ack(device_type, status="OK")
            transport.sendto(response, addr)

        elif msg_type == "pong":
            if device_type in registered_devices:
                device_info = registered_devices[device_type]
                device_info["last_seen"] = time.time()
                device_info["ping_attempts"] = 0
                if device_info.get("disconnected", False):
                    device_info["disconnected"] = False
                    print(f"INFO: {device_type} RECONNECTED!")

    except ValueError as e:
        # CRC error detected
        if "CRC mismatch" in str(e):
            try:
                header = message[0]
                _, device_type_id, _ = unpack_header(header)
                device_name = DEVICE_TYPE_NAMES.get(device_type_id)
                if device_name:
                    timestamp = struct.unpack('!I', message[1:5])[0]
                    print(f"INFO: {device_name} CORRUPTED DATA at {timestamp}. REQUESTING DATA")
                    response = encode_error(device_name, "CRC_FAIL", "resend_last")
                    transport.sendto(response, addr)
            except:
                print(f"[ERROR] Error handling CRC failure: {e}")
        else:
            print(f"[ERROR] Error parsing message: {e}")
    except Exception as e:
        print(f"[ERROR] Error parsing message: {e}")


async def activity_checker(transport):
    while True:
        await asyncio.sleep(activity_interval)
        now = time.time()
        for device_type, info in list(registered_devices.items()):
            time_since_last = now - info["last_seen"]

            if time_since_last > timeout_seconds:
                if not info.get("disconnected", False):
                    info["disconnected"] = True
                    info["ping_attempts"] = 1
                    print(f"WARNING: {device_type} DISCONNECTED!")
                    ping = encode_ping(device_type)
                    transport.sendto(ping, info["address"])
                elif info["ping_attempts"] < 10:
                    info["ping_attempts"] += 1
                    if info["ping_attempts"] == 2:
                        print(f"WARNING: {device_type} DISCONNECTED!")
                    ping = encode_ping(device_type)
                    transport.sendto(ping, info["address"])


class ServerProtocol:
    def connection_made(self, transport):
        self.transport = transport
        asyncio.create_task(activity_checker(transport))

    def datagram_received(self, data, addr):
        asyncio.create_task(handle_message(data, addr, self.transport))

    def error_received(self, exc):
        if isinstance(exc, OSError):
            pass
        else:
            print(f"[ERROR] Protocol error: {exc}")


async def command_listener(loop):
    global ignore_acks_for
    while True:
        try:
            cmd = await loop.run_in_executor(None, input, "")
            if cmd.strip().lower() == "uat5":
                if registered_devices:
                    print("\nZaregistrované senzory:", list(registered_devices.keys()))
                    device = await loop.run_in_executor(None, input, "Zadaj názov senzora: ")
                    device = device.strip()
                    if device in registered_devices:
                        ignore_acks_for = device
                        registered_devices[device]["no_ack_count"] = 0
                        print(f"Nastavené: Server ignoruje prvé 3 ACK pre {device}\n")
                    else:
                        print(f"Senzor '{device}' nie je zaregistrovaný!\n")
                else:
                    print("Žiadne zaregistrované senzory!\n")
        except:
            await asyncio.sleep(0.1)


async def run_server():
    global SERVER_IP, SERVER_PORT, ignore_acks_for

    while True:
        print("\nFIITMeteo Server")
        print("1) Nastaviť IP a port")
        print("2) Spustiť server")
        print("3) Ukončiť")
        choice = input("Voľba: ").strip()

        if choice == "1":
            SERVER_IP = input(f"IP (default {SERVER_IP}): ").strip() or SERVER_IP
            port_input = input(f"Port (default {SERVER_PORT}): ").strip()
            SERVER_PORT = int(port_input) if port_input else SERVER_PORT
            print(f"Nastavené: {SERVER_IP}:{SERVER_PORT}")

        elif choice == "2":
            print(f"Server počúva na {SERVER_IP}:{SERVER_PORT}")
            print("Napíšte 'uat5' a stlačte Enter pre aktiváciu UAT5 testu\n")
            print("USING BINARY PROTOCOL (optimized)")
            loop = asyncio.get_running_loop()
            transport, protocol_obj = await loop.create_datagram_endpoint(
                lambda: ServerProtocol(),
                local_addr=(SERVER_IP, SERVER_PORT)
            )

            asyncio.create_task(command_listener(loop))

            try:
                await asyncio.Future()
            except KeyboardInterrupt:
                print("\nServer zastavený...")
            finally:
                transport.close()
                break

        elif choice == "3":
            print("Ukončujem server...")
            break


if __name__ == "__main__":
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        print("\nProgram ukončený používateľom.")

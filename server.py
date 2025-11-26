import asyncio
import struct
import time
import zlib

SERVER_IP = "127.0.0.1"
SERVER_PORT = 9999
registered_devices = {}
ignore_acks_for = None  # UAT5
activity_interval = 5
timeout_seconds = 15

# Protocol Constants
MSG_REGISTER = 0x0
MSG_REGISTER_ACK = 0x1
MSG_DATA = 0x2
MSG_CONTROL = 0x3

DEVICE_THERMONODE = 0x0
DEVICE_WINDSENSE = 0x1
DEVICE_RAINDETECT = 0x2
DEVICE_AIRQUALITY = 0x3

CTRL_DATA_ACK = 0x0
CTRL_PING = 0x1
CTRL_PONG = 0x2
CTRL_ERROR = 0x3

ERR_INVALID_TOKEN = 0x01
ERR_CRC_FAIL = 0x02
ERR_INVALID_DATA = 0x03

DEVICE_NAMES = {
    DEVICE_THERMONODE: "ThermoNode",
    DEVICE_WINDSENSE: "WindSense",
    DEVICE_RAINDETECT: "RainDetect",
    DEVICE_AIRQUALITY: "AirQualityBox"
}


def current_time():
    return int(time.time())


def make_header(msg_type, device_type, flags=0):
    """Create common 5-byte header"""
    byte0 = (msg_type << 6) | (device_type << 4) | (flags & 0x0F)
    timestamp = current_time()
    return struct.pack('!BI', byte0, timestamp)


def make_register_ack(device_type, token):
    """Create REGISTER_ACK message (9 bytes)"""
    header = make_header(MSG_REGISTER_ACK, device_type)
    return header + struct.pack('!I', token)


def make_data_ack(device_type):
    """Create DATA_ACK message (5 bytes)"""
    return make_header(MSG_CONTROL, device_type, CTRL_DATA_ACK)


def make_ping(device_type):
    """Create PING message (5 bytes)"""
    return make_header(MSG_CONTROL, device_type, CTRL_PING)


def make_error(device_type, error_code):
    """Create ERROR message (6 bytes)"""
    header = make_header(MSG_CONTROL, device_type, CTRL_ERROR)
    return header + struct.pack('!B', error_code)


def parse_header(data):
    """Parse common header, returns (msg_type, device_type, flags, timestamp)"""
    if len(data) < 5:
        return None
    byte0, timestamp = struct.unpack('!BI', data[:5])
    msg_type = (byte0 >> 6) & 0x03
    device_type = (byte0 >> 4) & 0x03
    flags = byte0 & 0x0F
    return msg_type, device_type, flags, timestamp


def parse_data_message(data, device_type):
    """Parse DATA message and extract payload"""
    if len(data) < 14:  # Min: header(5) + token(4) + crc(4) + at least 1 byte data
        return None

    # Extract token
    token = struct.unpack('!I', data[5:9])[0]

    # Extract CRC (last 4 bytes)
    received_crc = struct.unpack('!I', data[-4:])[0]

    # Calculate expected CRC (everything except last 4 bytes)
    calculated_crc = zlib.crc32(data[:-4])

    # Extract payload based on device type
    payload_data = data[9:-4]
    payload = None
    battery_low = False

    # Battery low flag is in bit 0 of flags field
    header = parse_header(data)
    if header:
        battery_low = (header[2] & 0x01) == 1

    if device_type == DEVICE_THERMONODE and len(payload_data) == 8:
        temp, hum, dew, press = struct.unpack('!hHhH', payload_data)
        payload = {
            "temperature": temp / 10.0,
            "humidity": hum / 10.0,
            "dew_point": dew / 10.0,
            "pressure": (press + 80000) / 100.0
        }
    elif device_type == DEVICE_WINDSENSE and len(payload_data) == 7:
        speed, gust, direction, turb = struct.unpack('!HHHB', payload_data)
        payload = {
            "wind_speed": speed / 10.0,
            "wind_gust": gust / 10.0,
            "wind_direction": direction,
            "turbulence": turb / 10.0
        }
    elif device_type == DEVICE_RAINDETECT and len(payload_data) == 7:
        rain, moist, risk, duration = struct.unpack('!HHBH', payload_data)
        payload = {
            "rainfall": rain / 10.0,
            "soil_moisture": moist / 10.0,
            "flood_risk": risk,
            "rain_duration": duration
        }
    elif device_type == DEVICE_AIRQUALITY and len(payload_data) == 6:
        co2, ozone, aqi = struct.unpack('!HHH', payload_data)
        payload = {
            "co2": co2,
            "ozone": ozone / 10.0,
            "air_quality_index": aqi
        }

    if payload is None:
        return None

    return {
        "token": token,
        "crc_valid": received_crc == calculated_crc,
        "payload": payload,
        "battery_low": battery_low,
        "timestamp": header[3] if header else current_time()
    }


async def handle_message(message, addr, transport):
    global ignore_acks_for

    if len(message) < 5:
        print(f"[ERROR] Message too short: {len(message)} bytes")
        return

    header = parse_header(message)
    if not header:
        print(f"[ERROR] Invalid header")
        return

    msg_type, device_type, flags, timestamp = header
    device_name = DEVICE_NAMES.get(device_type, f"Unknown-{device_type}")

    if msg_type == MSG_REGISTER:
        # Generate token
        token = int(time.time()) % 100000
        registered_devices[device_type] = {
            "token": token,
            "last_seen": time.time(),
            "address": addr,
            "disconnected": False,
            "ping_attempts": 0,
            "name": device_name
        }
        print(f"INFO: {device_name} REGISTERED at {current_time()}")
        transport.sendto(make_register_ack(device_type, token), addr)

    elif msg_type == MSG_DATA:
        parsed = parse_data_message(message, device_type)
        if not parsed:
            print(f"[ERROR] Failed to parse DATA message from {device_name}")
            transport.sendto(make_error(device_type, ERR_INVALID_DATA), addr)
            return

        # Validate token
        if device_type not in registered_devices or registered_devices[device_type]["token"] != parsed["token"]:
            transport.sendto(make_error(device_type, ERR_INVALID_TOKEN), addr)
            return

        # Check CRC
        if not parsed["crc_valid"]:
            print(f"INFO: {device_name} CORRUPTED DATA at {parsed['timestamp']}. REQUESTING DATA")
            transport.sendto(make_error(device_type, ERR_CRC_FAIL), addr)
            return

        # Update last activity time and reconnect if needed
        device_info = registered_devices[device_type]
        device_info["last_seen"] = time.time()
        device_info["ping_attempts"] = 0

        if device_info.get("disconnected"):
            device_info["disconnected"] = False
            print(f"INFO: {device_name} RECONNECTED!")

        # Print data
        if parsed["battery_low"]:
            print(f"{parsed['timestamp']} - WARNING: LOW BATTERY {device_name}")
        else:
            print(f"{parsed['timestamp']} - {device_name}")

        param_str = ""
        for k, v in parsed["payload"].items():
            param_str += f"{k}: {v}; "
        print(param_str)

        # UAT5: Ignore ACKs for specific device
        if ignore_acks_for == device_type:
            if "no_ack_count" not in registered_devices[device_type]:
                registered_devices[device_type]["no_ack_count"] = 0
            registered_devices[device_type]["no_ack_count"] += 1
            if registered_devices[device_type]["no_ack_count"] <= 3:
                print(f"[DEBUG] Ignorujem ACK pre {device_name} ({registered_devices[device_type]['no_ack_count']}/3)")
                return
            else:
                print(f"[DEBUG] Teraz posielam ACK pre {device_name}")
                registered_devices[device_type]["no_ack_count"] = 0
                ignore_acks_for = None

        transport.sendto(make_data_ack(device_type), addr)

    elif msg_type == MSG_CONTROL:
        ctrl_type = flags & 0x0F

        if ctrl_type == CTRL_PONG:
            if device_type in registered_devices:
                device_info = registered_devices[device_type]
                device_info["last_seen"] = time.time()
                device_info["ping_attempts"] = 0
                if device_info.get("disconnected", False):
                    device_info["disconnected"] = False
                    print(f"INFO: {device_name} RECONNECTED!")


async def activity_checker(transport):
    while True:
        await asyncio.sleep(activity_interval)
        now = time.time()
        for device_type, info in list(registered_devices.items()):
            time_since_last = now - info["last_seen"]
            device_name = info["name"]

            # If more than 15 seconds since last message
            if time_since_last > timeout_seconds:
                if not info.get("disconnected", False):
                    # First time detecting timeout - mark as disconnected and send ping
                    info["disconnected"] = True
                    info["ping_attempts"] = 1
                    print(f"WARNING: {device_name} DISCONNECTED!")
                    ping = make_ping(device_type)
                    transport.sendto(ping, info["address"])
                else:
                    # Continue sending pings every 5 seconds indefinitely
                    info["ping_attempts"] += 1
                    ping = make_ping(device_type)
                    transport.sendto(ping, info["address"])


class ServerProtocol:
    def connection_made(self, transport):
        self.transport = transport
        asyncio.create_task(activity_checker(transport))

    def datagram_received(self, data, addr):
        asyncio.create_task(handle_message(data, addr, self.transport))

    def error_received(self, exc):
        # Handle network errors gracefully
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
                    device_names = {info["name"]: dtype for dtype, info in registered_devices.items()}
                    print("\nZaregistrované senzory:", list(device_names.keys()))
                    device = await loop.run_in_executor(None, input, "Zadaj názov senzora: ")
                    device = device.strip()
                    if device in device_names:
                        device_type = device_names[device]
                        ignore_acks_for = device_type
                        registered_devices[device_type]["no_ack_count"] = 0
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
        print("\nFIITMeteo Server (Binary Protocol)")
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
            loop = asyncio.get_running_loop()
            transport, protocol = await loop.create_datagram_endpoint(
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

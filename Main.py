import asyncio
import json
import time
import zlib

# ==============================
# Konfigurácia
# ==============================
SERVER_IP = "127.0.0.1"
SERVER_PORT = 9999
registered_devices = {}
ignore_acks_for = None  # UAT5
activity_interval = 5
timeout_seconds = 15


# ==============================
# Pomocné funkcie
# ==============================
def current_time():
    return int(time.time())


def calc_crc(data: dict) -> str:
    return format(zlib.crc32(json.dumps(data, sort_keys=True).encode()), "08X")


def make_response(msg_type, device_type, **kwargs):
    return json.dumps({
        "type": msg_type,
        "device_type": device_type,
        "timestamp": current_time(),
        **kwargs
    }).encode()


# ==============================
# Spracovanie správ
# ==============================
async def handle_message(message, addr, transport):
    global ignore_acks_for
    try:
        data = json.loads(message.decode())
        msg_type = data.get("type")
        device_type = data.get("device_type")

        if msg_type == "register":
            token = f"T-{int(time.time()) % 100000}"
            registered_devices[device_type] = {
                "token": token,
                "last_seen": time.time(),
                "address": addr,
                "disconnected": False,
                "ping_attempts": 0
            }
            print(f"INFO: {device_type} REGISTERED at {current_time()}")
            transport.sendto(make_response("register_ack", device_type, token=token), addr)

        elif msg_type == "data":
            token = data.get("token")
            if device_type not in registered_devices or registered_devices[device_type]["token"] != token:
                transport.sendto(make_response("error", device_type, error="INVALID_TOKEN"), addr)
                return

            recv_crc = data.get("crc")
            expected_crc = calc_crc({k: v for k, v in data.items() if k != "crc"})
            if recv_crc != expected_crc:
                print(f"INFO: {device_type} CORRUTPED DATA at {data['timestamp']}. REQUESTING DATA")
                transport.sendto(make_response("error", device_type, error="CRC_FAIL", request="resend_last"), addr)
                return

            # Update last activity time and reconnect if needed
            device_info = registered_devices[device_type]
            device_info["last_seen"] = time.time()
            device_info["ping_attempts"] = 0

            if device_info.get("disconnected"):
                device_info["disconnected"] = False
                print(f"INFO: {device_type} RECONNECTED!")

            battery = data.get("battery_low", False)

            # Print according to format specification
            if battery:
                print(f"{data['timestamp']} - WARNING: LOW BATTERY {device_type}")
            else:
                print(f"{data['timestamp']} - {device_type}")

            # Print parameters on new line
            param_str = ""
            for k, v in data["data"].items():
                param_str += f"{k}: {v}; "
            print(param_str)

            # UAT5: Check if we should ignore ACK for this device
            if ignore_acks_for == device_type:
                if "no_ack_count" not in registered_devices[device_type]:
                    registered_devices[device_type]["no_ack_count"] = 0
                registered_devices[device_type]["no_ack_count"] += 1
                if registered_devices[device_type]["no_ack_count"] <= 3:
                    print(f"[DEBUG] (UAT5) Ignorujem ACK pre {device_type} ({registered_devices[device_type]['no_ack_count']}/3)")
                    return
                else:
                    # After 3 times, reset and start acknowledging
                    print(f"[DEBUG] (UAT5) Teraz posielam ACK pre {device_type}")
                    registered_devices[device_type]["no_ack_count"] = 0
                    ignore_acks_for = None

            transport.sendto(make_response("data_ack", device_type, status="OK"), addr)

        elif msg_type == "pong":
            if device_type in registered_devices:
                device_info = registered_devices[device_type]
                device_info["last_seen"] = time.time()
                device_info["ping_attempts"] = 0
                if device_info.get("disconnected", False):
                    device_info["disconnected"] = False
                    print(f"INFO: {device_type} RECONNECTED!")

    except Exception as e:
        print(f"[ERROR] Error parsing message: {e}")


# ==============================
# Kontrola aktivity zariadení
# ==============================
async def activity_checker(transport):
    while True:
        await asyncio.sleep(activity_interval)
        now = time.time()
        for device_type, info in list(registered_devices.items()):
            time_since_last = now - info["last_seen"]

            # If more than 15 seconds since last message
            if time_since_last > timeout_seconds:
                if not info.get("disconnected", False):
                    # First time detecting timeout - mark as disconnected and send ping
                    info["disconnected"] = True
                    info["ping_attempts"] = 1
                    print(f"WARNING: {device_type} DISCONNECTED!")
                    ping = make_response("ping", device_type)
                    transport.sendto(ping, info["address"])
                elif info["ping_attempts"] < 10:
                    # Continue sending pings every 5 seconds, max 10 times
                    info["ping_attempts"] += 1
                    ping = make_response("ping", device_type)
                    transport.sendto(ping, info["address"])


# ==============================
# UDP Server Protocol
# ==============================
class ServerProtocol:
    def connection_made(self, transport):
        self.transport = transport
        asyncio.create_task(activity_checker(transport))

    def datagram_received(self, data, addr):
        asyncio.create_task(handle_message(data, addr, self.transport))


# ==============================
# CLI menu
# ==============================
async def run_server():
    global SERVER_IP, SERVER_PORT, ignore_acks_for

    while True:
        print("\n===== FIITMeteo Server =====")
        print("1) Nastaviť IP a port")
        print("2) Spustiť server")
        print("3) Nepotvrdzovať správy pre senzor (UAT5)")
        print("4) Ukončiť")
        choice = input("Voľba: ").strip()

        if choice == "1":
            SERVER_IP = input(f"IP (default {SERVER_IP}): ").strip() or SERVER_IP
            port_input = input(f"Port (default {SERVER_PORT}): ").strip()
            SERVER_PORT = int(port_input) if port_input else SERVER_PORT
            print(f"Nastavené: {SERVER_IP}:{SERVER_PORT}")

        elif choice == "2":
            print(f"Server počúva na {SERVER_IP}:{SERVER_PORT}")
            loop = asyncio.get_running_loop()
            transport, protocol = await loop.create_datagram_endpoint(
                lambda: ServerProtocol(),
                local_addr=(SERVER_IP, SERVER_PORT)
            )
            try:
                await asyncio.Future()  # Run forever
            except KeyboardInterrupt:
                print("\nServer zastavený...")
            finally:
                transport.close()
                break

        elif choice == "3":
            if registered_devices:
                print("Zaregistrované senzory:", list(registered_devices.keys()))
                device = input("Zadaj názov senzora, ktorému ignorovať ACK (UAT5): ").strip()
                if device in registered_devices:
                    ignore_acks_for = device
                    registered_devices[device]["no_ack_count"] = 0
                    print(f"Nastavené: Server bude ignorovať prvé 3 ACK pre {device}")
                else:
                    print(f"Senzor '{device}' nie je zaregistrovaný!")
            else:
                print("Žiadne zaregistrované senzory!")

        elif choice == "4":
            print("Ukončujem server...")
            break


if __name__ == "__main__":
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        print("\nProgram ukončený používateľom.")
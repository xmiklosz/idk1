import asyncio
import time
import protocol  # Binary protocol module



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
        data = protocol.decode_message(message)
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
            response = protocol.encode_register_ack(device_type, token)
            transport.sendto(response, addr)

        elif msg_type == "data":
            token = data.get("token")
            if device_type not in registered_devices or registered_devices[device_type]["token"] != token:
                response = protocol.encode_error(device_type, "INVALID_TOKEN")
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

            response = protocol.encode_data_ack(device_type, status="OK")
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
            # Try to extract device type from the message
            try:
                header = message[0]
                _, device_type_id, _ = protocol.unpack_header(header)
                device_name = protocol.DEVICE_TYPE_NAMES.get(device_type_id)
                if device_name:
                    # Get timestamp from message
                    import struct
                    timestamp = struct.unpack('!I', message[1:5])[0]
                    print(f"INFO: {device_name} CORRUPTED DATA at {timestamp}. REQUESTING DATA")
                    response = protocol.encode_error(device_name, "CRC_FAIL", "resend_last")
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

            # If more than 15 seconds since last message
            if time_since_last > timeout_seconds:
                if not info.get("disconnected", False):
                    # First time detecting timeout - mark as disconnected and send ping
                    info["disconnected"] = True
                    info["ping_attempts"] = 1
                    print(f"WARNING: {device_type} DISCONNECTED!")
                    ping = protocol.encode_ping(device_type)
                    transport.sendto(ping, info["address"])
                elif info["ping_attempts"] < 10:
                    # Continue sending pings every 5 seconds, max 10 times
                    info["ping_attempts"] += 1
                    # Print DISCONNECTED for the 2nd ping attempt as well (to match UAT4 requirement)
                    if info["ping_attempts"] == 2:
                        print(f"WARNING: {device_type} DISCONNECTED!")
                    ping = protocol.encode_ping(device_type)
                    transport.sendto(ping, info["address"])


class ServerProtocol:
    def connection_made(self, transport):
        self.transport = transport
        asyncio.create_task(activity_checker(transport))

    def datagram_received(self, data, addr):
        asyncio.create_task(handle_message(data, addr, self.transport))

    def error_received(self, exc):
        # Handle network errors gracefully (e.g., when sending to disconnected clients)
        if isinstance(exc, OSError):
            # This is expected when sending to a closed socket, just ignore it
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

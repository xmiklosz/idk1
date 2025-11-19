import asyncio
import random
import time
import threading
from binary_protocol import encode_message, decode_message

print_lock = threading.Lock()


def now_unix():
    return int(time.time())


def make_token():
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    random_part = ''.join(random.choices(chars, k=12))
    return "TKN-" + random_part


def safe_print(*args, **kwargs):
    with print_lock:
        print(*args, **kwargs, flush=True)


def print_sensor_data(timestamp, token, payload, low_battery, device_type=None):
    battery_warning = " - WARNING: LOW BATTERY" if low_battery else ""
    if isinstance(payload, dict) and payload.get("error_sim") and "orig_payload" in payload:
        inner = payload.get("orig_payload") or {}
    else:
        inner = payload or {}

    if not isinstance(inner, dict):
        display_name = device_type if device_type else token
        header = f"@{timestamp}{battery_warning} @{display_name}"
        param_line = f"value: {inner};"
        safe_print(f"{header}\n{param_line}")
        return
    param_parts = [f"{name}: {value}" for name, value in inner.items()]
    param_line = "; ".join(param_parts) + ";"
    display_name = device_type if device_type else token
    header = f"@{timestamp}{battery_warning} @{display_name}"
    safe_print(f"{header}\n{param_line}")


class SensorServer:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.tokens = {}
        self.device_to_token = {}
        self.last_message_times = {}
        self.last_message_monotonic = {}
        self.transport = None
        self._monitor_task = None
        self._cleanup_task = None
        self._console_task = None
        self._stop_event = asyncio.Event()
        self.ack_suppression = {}  # str -> int

    async def start_server(self):
        loop = asyncio.get_event_loop()
        self.transport, _ = await loop.create_datagram_endpoint(
            lambda: SensorProtocol(self),
            local_addr=(self.ip, self.port)
        )
        safe_print(f"Server spustený: {self.ip}:{self.port}")
        safe_print("Menu:\n1. Vypnutie odosielania ACK")
        self._monitor_task = asyncio.create_task(self.disconnect_monitor())
        self._cleanup_task = asyncio.create_task(self.cleanup_old_sensors())
        self._console_task = asyncio.create_task(self.console_input_loop())

    async def stop_server(self):
        safe_print("Stopping server tasks")
        if self._monitor_task:
            self._monitor_task.cancel()
        if self._cleanup_task:
            self._cleanup_task.cancel()
        if self._console_task:
            self._console_task.cancel()
        if self.transport:
            self.transport.close()
        self._stop_event.set()

    async def send_binary(self, addr, obj):
        """Send a message object as binary data."""
        try:
            binary_data = encode_message(obj)
            self.transport.sendto(binary_data, addr)
        except Exception as e:
            safe_print(f"Error sending UDP to {addr}: {e}")

    async def handle_message(self, data, addr):
        try:
            msg = decode_message(data)
        except Exception as e:
            safe_print("Nie je možné dekódovať správu:", e)
            return

        # Check if checksum is valid
        if not msg.get("_checksum_valid", False):
            device_type = msg.get("device_type", "UNKNOWN")
            timestamp = msg.get("timestamp", "UNKNOWN")
            token = msg.get("token", "UNKNOWN")
            sensor_id = device_type if device_type != "UNKNOWN" else token
            safe_print(f"INFO: @{sensor_id} CORRUPTED DATA at @{timestamp}. REQUESTING DATA")

            resp = {
                "type": "checksum_error",
                "timestamp": now_unix(),
                "message": "Invalid checksum - please resend"
            }
            await self.send_binary(addr, resp)
            return

        mtype = msg.get("type")
        device_type = msg.get("device_type")
        token = msg.get("token")
        timestamp = msg.get("timestamp")
        low_battery = msg.get("low_battery", False)

        if mtype == "ping_response":
            if token in self.tokens:
                sensor_info = self.tokens[token]
                was_disconnected = sensor_info.get("disconnected", False)
                sensor_info["ping_attempts"] = 0
                sensor_info["awaiting_response"] = False
                sensor_info["last_ping_monotonic"] = None
                sensor_info["awaiting_ping_deadline"] = None
                sensor_info["gave_up"] = False
                sensor_info["disconnected"] = False
                sensor_info["disconnected_reported"] = False
                self.last_message_times[token] = now_unix()
                self.last_message_monotonic[token] = time.monotonic()
                if was_disconnected:
                    safe_print(f"INFO: @{sensor_info['device_type']} RECONNECTED!")
            return

        if mtype == "register":
            if device_type in self.device_to_token:
                token = self.device_to_token[device_type]
                resp = {"type": "ack", "token": token, "device_type": device_type, "timestamp": now_unix()}
                await self.send_binary(addr, resp)
                return

            token = make_token()
            self.tokens[token] = {
                "device_type": device_type,
                "registered_at": now_unix(),
                "last_msg": None,
                "low_battery": bool(low_battery),
                "last_addr": addr,
                "ping_attempts": 0,
                "last_ping_monotonic": None,
                "awaiting_response": False,
                "awaiting_ping_deadline": None,
                "disconnected": False,
                "gave_up": False,
                "disconnected_reported": False
            }
            self.device_to_token[device_type] = token
            self.last_message_times[token] = now_unix()
            self.last_message_monotonic[token] = time.monotonic()
            resp = {"type": "ack", "token": token, "device_type": device_type, "timestamp": now_unix()}
            await self.send_binary(addr, resp)
            safe_print(f"INFO: @{token} REGISTERED ({device_type})")
            return

        if mtype == "ping":
            resp = {"type": "ping_response", "timestamp": now_unix(), "token": token, "device_type": device_type or "ThermoNode"}
            await self.send_binary(addr, resp)
            return

        if mtype == "data":
            payload = msg.get("payload", {})
            if token in self.tokens:
                sensor_info = self.tokens[token]
                was_disconnected = sensor_info.get("disconnected", False)
                sensor_info["last_msg"] = {"payload": payload, "timestamp": timestamp}
                sensor_info["last_addr"] = addr
                sensor_info["ping_attempts"] = 0
                sensor_info["awaiting_response"] = False
                sensor_info["last_ping_monotonic"] = None
                sensor_info["awaiting_ping_deadline"] = None
                sensor_info["disconnected"] = False
                sensor_info["gave_up"] = False
                sensor_info["disconnected_reported"] = False
                self.last_message_times[token] = now_unix()
                self.last_message_monotonic[token] = time.monotonic()
                sensor_info["low_battery"] = bool(low_battery)

                if was_disconnected:
                    safe_print(f"INFO: @{device_type} RECONNECTED!")

                print_sensor_data(timestamp, token, payload, low_battery, device_type)
                should_send_ack = True
                dt = sensor_info.get("device_type")
                if dt and self.ack_suppression.get(dt, 0) > 0:
                    self.ack_suppression[dt] -= 1
                    should_send_ack = False
                    safe_print(f"(ACK potlačené) @{dt}, zostáva: {self.ack_suppression[dt]}")
                if should_send_ack:
                    resp = {"type": "ack", "device_type": dt, "timestamp": now_unix(), "token": token}
                    await self.send_binary(addr, resp)
                else:
                    pass
            else:
                resp = {
                    "type": "invalid_token",
                    "timestamp": now_unix(),
                    "token": token,
                    "reason": "unknown token"
                }
                await self.send_binary(addr, resp)
            return

        resp = {"type": "error", "timestamp": now_unix(), "message": "unsupported message type"}
        await self.send_binary(addr, resp)

    async def disconnect_monitor(self):
        try:
            sleep_interval = 0.2
            while True:
                now_m = time.monotonic()
                for device_type, token in list(self.device_to_token.items()):
                    sensor_info = self.tokens.get(token)
                    if not sensor_info:
                        continue

                    last_msg_m = self.last_message_monotonic.get(token, 0)
                    time_since_last = now_m - last_msg_m
                    ping_attempts = sensor_info.get("ping_attempts", 0)
                    awaiting_response = sensor_info.get("awaiting_response", False)
                    last_ping_m = sensor_info.get("last_ping_monotonic")
                    awaiting_deadline = sensor_info.get("awaiting_ping_deadline")
                    gave_up = sensor_info.get("gave_up", False)
                    disconnected_reported = sensor_info.get("disconnected_reported", False)
                    if time_since_last >= 15 and ping_attempts == 0 and not awaiting_response and not gave_up:
                        ping_msg = {
                            "type": "ping",
                            "timestamp": now_unix(),
                            "token": token,
                            "device_type": device_type
                        }
                        try:
                            await self.send_binary(sensor_info["last_addr"], ping_msg)
                            sensor_info["ping_attempts"] = 1
                            sensor_info["last_ping_monotonic"] = now_m
                            sensor_info["awaiting_response"] = True
                            sensor_info["awaiting_ping_deadline"] = now_m + 1.0
                            sensor_info["last_ping_time"] = now_unix()
                            safe_print(f"PING #1 sent to @{device_type}")
                        except Exception as e:
                            safe_print(f"Error sending ping to {device_type}: {e}")
                        continue
                    if awaiting_response and awaiting_deadline is not None:
                        if now_m >= awaiting_deadline:
                            if sensor_info.get("ping_attempts", 0) >= 1:
                                sensor_info["disconnected"] = True
                                safe_print(f"WARNING: @{device_type} DISCONNECTED!")
                            sensor_info["awaiting_response"] = False
                            sensor_info["awaiting_ping_deadline"] = None
                            continue
                    if not awaiting_response and 0 < ping_attempts < 10 and not gave_up:
                        if last_ping_m is None:
                            next_ping_due = now_m
                        else:
                            next_ping_due = last_ping_m + 5.0
                        if now_m >= next_ping_due:
                            ping_msg = {
                                "type": "ping",
                                "timestamp": now_unix(),
                                "token": token,
                                "device_type": device_type
                            }
                            try:
                                await self.send_binary(sensor_info["last_addr"], ping_msg)
                                sensor_info["ping_attempts"] = ping_attempts + 1
                                sensor_info["last_ping_monotonic"] = now_m
                                sensor_info["awaiting_response"] = True
                                sensor_info["awaiting_ping_deadline"] = now_m + 1.0
                                sensor_info["last_ping_time"] = now_unix()
                                safe_print(f"PING #{sensor_info['ping_attempts']} sent to @{device_type}")
                            except Exception as e:
                                safe_print(f"Error sending ping to {device_type}: {e}")
                            continue
                    if ping_attempts >= 10 and not gave_up:
                        safe_print(f"ERROR: @{device_type} unreachable after {ping_attempts} pings. Giving up.")
                        sensor_info["gave_up"] = True
                        sensor_info["disconnected"] = True
                        if not sensor_info.get("disconnected_reported", False):
                            sensor_info["disconnected_reported"] = True

                await asyncio.sleep(sleep_interval)
        except asyncio.CancelledError:
            pass

    async def cleanup_old_sensors(self):
        try:
            while True:
                current_time = now_unix()
                timeout_duration = 300
                tokens_to_remove = []
                for token, sensor_info in list(self.tokens.items()):
                    last_time = self.last_message_times.get(token, 0)
                    if current_time - last_time > timeout_duration:
                        device_type = sensor_info["device_type"]
                        tokens_to_remove.append((token, device_type))
                for token, device_type in tokens_to_remove:
                    self.tokens.pop(token, None)
                    self.device_to_token.pop(device_type, None)
                    self.last_message_times.pop(token, None)
                    self.last_message_monotonic.pop(token, None)
                    safe_print(f"INFO: Removed inactive sensor @{device_type} (token: {token})")

                await asyncio.sleep(60)
        except asyncio.CancelledError:
            pass

    async def console_input_loop(self):
        loop = asyncio.get_event_loop()
        sensors = ["ThermoNode", "WindSense", "RainDetect", "AirQualityBox"]
        try:
            while True:
                safe_print("Vyber senzor (číslo) a vypni ACK na 3 správy:")
                for i, s in enumerate(sensors, start=1):
                    safe_print(f"{i}. {s}")
                sel_in = await loop.run_in_executor(None, input, "Cislo: \n")
                try:
                    sel = int(sel_in.strip())
                    if 1 <= sel <= len(sensors):
                        chosen = sensors[sel - 1]
                        self.ack_suppression[chosen] = 3
                        safe_print(f"ACK vypnuté pre nasledujúce 3 dátové správy od {chosen}")
                    else:
                        safe_print("Neplatné číslo")
                except ValueError:
                    safe_print("Neplatný formát vstupu")
        except asyncio.CancelledError:
            pass


class SensorProtocol:
    def __init__(self, server):
        self.server = server

    def connection_made(self, transport):
        pass

    def datagram_received(self, data, addr):
        asyncio.create_task(self.server.handle_message(data, addr))

    def error_received(self, exc):
        safe_print(f"Chyba v komunikácii: {exc}")

    def connection_lost(self, exc):
        pass


async def main():
    loop = asyncio.get_event_loop()

    safe_print("Enter server IP:")
    ip = await loop.run_in_executor(None, input)
    ip = ip.strip()

    safe_print("Enter server port:")
    port_input = await loop.run_in_executor(None, input)
    try:
        port = int(port_input.strip())
    except ValueError:
        safe_print("Invalid port")
        return

    server = SensorServer(ip, port)
    try:
        await server.start_server()
        await server._stop_event.wait()
    except KeyboardInterrupt:
        safe_print("\nUkončenie")
    finally:
        await server.stop_server()


if __name__ == "__main__":
    asyncio.run(main())

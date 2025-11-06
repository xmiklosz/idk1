"""
FIITMeteo Tester - Binary UDP Protocol
Course Assignment: PKS-B
"""

import asyncio
import time
import random
import struct
import zlib

# ============================================================================
# BINARY PROTOCOL MODULE (Embedded)
# ============================================================================

# Message types
MSG_REGISTER = 0
MSG_DATA = 2
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


def encode_register(device_name: str) -> bytes:
    """Encode REGISTER message"""
    device_type = DEVICE_TYPE_MAP[device_name]
    header = pack_header(MSG_REGISTER, device_type)
    timestamp = int(time.time())
    data = struct.pack('!BI', header, timestamp)
    crc = calc_crc32(data)
    data += struct.pack('!I', crc)
    return data


def encode_data_payload(device_name: str, data_dict: dict) -> bytes:
    """Encode device-specific data payload"""
    if device_name == "ThermoNode":
        temp = int(data_dict["temperature"] * 10)
        humidity = int(data_dict["humidity"] * 10)
        dew = int(data_dict["dew_point"] * 10)
        pressure = int((data_dict["pressure"] - 800.0) * 100)
        return struct.pack('!hHhH', temp, humidity, dew, pressure)
    elif device_name == "WindSense":
        speed = int(data_dict["wind_speed"] * 10)
        gust = int(data_dict["wind_gust"] * 10)
        direction = int(data_dict["wind_direction"])
        turbulence = int(data_dict["turbulence"] * 10)
        return struct.pack('!HHHB', speed, gust, direction, turbulence)
    elif device_name == "RainDetect":
        rainfall = int(data_dict["rainfall"] * 10)
        moisture = int(data_dict["soil_moisture"] * 10)
        risk = int(data_dict["flood_risk"])
        duration = int(data_dict["rain_duration"])
        return struct.pack('!HHBH', rainfall, moisture, risk, duration)
    elif device_name == "AirQualityBox":
        co2 = int(data_dict["co2"])
        ozone = int(data_dict["ozone"] * 10)
        aqi = int(data_dict["air_quality_index"])
        return struct.pack('!HHH', co2, ozone, aqi)


def encode_data(device_name: str, token: int, data_dict: dict, battery_low: bool = False, corrupt_crc: bool = False) -> bytes:
    """Encode DATA message"""
    device_type = DEVICE_TYPE_MAP[device_name]
    header = pack_header(MSG_DATA, device_type, battery_low)
    timestamp = int(time.time())
    payload = encode_data_payload(device_name, data_dict)
    data = struct.pack('!BIH', header, timestamp, token & 0xFFFF) + payload
    crc = calc_crc32(data)
    if corrupt_crc:
        crc ^= 0xFF
    data += struct.pack('!I', crc)
    return data


def encode_pong(device_name: str, token: int) -> bytes:
    """Encode PONG message"""
    device_type = DEVICE_TYPE_MAP[device_name]
    header = pack_header(MSG_PONG, device_type)
    timestamp = int(time.time())
    data = struct.pack('!BIH', header, timestamp, token & 0xFFFF)
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

    if msg_type == 1:  # REGISTER_ACK
        header, timestamp, token, crc = struct.unpack('!BIHI', data)
        expected_crc = calc_crc32(data[:-4])
        if crc != expected_crc:
            raise ValueError(f"CRC mismatch")
        return {"type": "register_ack", "device_type": device_name, "timestamp": timestamp, "token": token}
    elif msg_type == 3:  # DATA_ACK
        return {"type": "data_ack"}
    elif msg_type == 5:  # PING
        return {"type": "ping", "device_type": device_name}
    elif msg_type == 4:  # ERROR
        header, timestamp, error_code, request_code, crc = struct.unpack('!BIBBI', data)
        error_str = "CRC_FAIL" if error_code == 1 else "INVALID_TOKEN"
        return {"type": "error", "error": error_str}
    elif msg_type == 2:  # DATA (for decoding corrupted messages)
        header, timestamp, token = struct.unpack('!BIH', data[:7])
        payload = data[7:-4]
        data_dict = decode_data_payload(device_name, payload)
        return {
            "type": "data",
            "device_type": device_name,
            "data": data_dict,
            "battery_low": battery_low
        }
    return {"type": "unknown"}


# ============================================================================
# TESTER IMPLEMENTATION
# ============================================================================

SERVER_IP = "127.0.0.1"
SERVER_PORT = 9999


class SimpleSensor(asyncio.DatagramProtocol):
    def __init__(self, device_name):
        self.device_name = device_name
        self.token = None
        self.transport = None
        self.running = True
        self.uat4_active = True
        self.uat4_ping_delay = 0
        self.uat4_completed = asyncio.Event()
        self.uat3_corrupt_next = False
        self.uat3_completed = asyncio.Event()
        self.uat5_waiting_ack = False
        self.uat5_ack_timer = None
        self.uat5_last_msg = None
        self.data_loop_task = None

    def connection_made(self, transport):
        self.transport = transport
        msg = encode_register(self.device_name)
        self.transport.sendto(msg, (SERVER_IP, SERVER_PORT))

    def datagram_received(self, data, addr):
        try:
            msg = decode_message(data)
            msg_type = msg["type"]

            if msg_type == "register_ack":
                self.token = msg["token"]
                if self.data_loop_task is None or self.data_loop_task.done():
                    self.data_loop_task = asyncio.create_task(self.data_loop())

            elif msg_type == "data_ack":
                self.uat5_waiting_ack = False
                if self.uat5_ack_timer:
                    self.uat5_ack_timer.cancel()
                    self.uat5_ack_timer = None

            elif msg_type == "ping":
                if self.uat4_ping_delay > 0:
                    print(f"[UAT4] {self.device_name}: Prijatý ping #{3 - self.uat4_ping_delay}, ignorujem...")
                    self.uat4_ping_delay -= 1
                else:
                    print(f"[UAT4] {self.device_name}: Prijatý ping, odpovedám PONG...")
                    pong = encode_pong(self.device_name, self.token)
                    self.transport.sendto(pong, (SERVER_IP, SERVER_PORT))
                    if not self.uat4_active:
                        self.uat4_active = True
                        print(f"[UAT4] {self.device_name}: OBNOVENÉ automatické odosielanie!")
                        self.uat4_completed.set()

            elif msg_type == "error":
                error_code = msg.get("error")
                if error_code == "CRC_FAIL":
                    print(f"[UAT3] {self.device_name}: Server detekoval CRC chybu, posielam znova...")
                    if self.uat5_last_msg:
                        last_msg_data = decode_message(self.uat5_last_msg)
                        clean_msg = encode_data(
                            self.device_name,
                            self.token,
                            last_msg_data.get("data"),
                            last_msg_data.get("battery_low", False),
                            corrupt_crc=False
                        )
                        self.transport.sendto(clean_msg, (SERVER_IP, SERVER_PORT))
                        self.uat3_completed.set()
        except Exception as e:
            print(f"[ERROR] {self.device_name} decode error: {e}")

    def error_received(self, exc):
        if not isinstance(exc, OSError):
            print(f"[ERROR] {self.device_name} protocol error: {exc}")

    async def data_loop(self):
        await asyncio.sleep(1)

        while self.running:
            if not self.transport or self.transport.is_closing():
                break

            if self.uat4_active:
                if self.device_name == "ThermoNode":
                    data = {
                        "temperature": round(random.uniform(20, 30), 1),
                        "humidity": round(random.uniform(40, 80), 1),
                        "dew_point": round(random.uniform(10, 20), 1),
                        "pressure": round(random.uniform(1000, 1020), 2)
                    }
                elif self.device_name == "WindSense":
                    data = {
                        "wind_speed": round(random.uniform(0, 20), 1),
                        "wind_gust": round(random.uniform(0, 30), 1),
                        "wind_direction": random.randint(0, 359),
                        "turbulence": round(random.uniform(0, 1), 1)
                    }
                elif self.device_name == "RainDetect":
                    data = {
                        "rainfall": round(random.uniform(0, 20), 1),
                        "soil_moisture": round(random.uniform(0, 100), 1),
                        "flood_risk": random.randint(0, 3),
                        "rain_duration": random.randint(0, 60)
                    }
                else:
                    data = {
                        "co2": random.randint(400, 1000),
                        "ozone": round(random.uniform(0, 200), 1),
                        "air_quality_index": random.randint(0, 200)
                    }

                corrupt = self.uat3_corrupt_next
                if corrupt:
                    print(f"[UAT3] {self.device_name}: Zavádzam CRC chybu do ďalšej správy...")
                    self.uat3_corrupt_next = False

                msg = encode_data(self.device_name, self.token, data, corrupt_crc=corrupt)
                self.transport.sendto(msg, (SERVER_IP, SERVER_PORT))

                self.uat5_last_msg = msg
                self.uat5_waiting_ack = True
                if self.uat5_ack_timer:
                    self.uat5_ack_timer.cancel()
                self.uat5_ack_timer = asyncio.create_task(self.uat5_wait_for_ack())

            await asyncio.sleep(10)

    async def uat5_wait_for_ack(self):
        await asyncio.sleep(1)
        if self.uat5_waiting_ack:
            print(f"[UAT5] {self.device_name}: Nedostal som ACK, posielam znova...")
            self.transport.sendto(self.uat5_last_msg, (SERVER_IP, SERVER_PORT))
            self.uat5_ack_timer = asyncio.create_task(self.uat5_wait_for_ack())

    def uat2_send_manual_data(self, data, battery_low):
        if not self.token:
            print(f"CHYBA: {self.device_name} nie je zaregistrovaný!")
            return

        msg = encode_data(self.device_name, self.token, data, battery_low=battery_low)
        self.transport.sendto(msg, (SERVER_IP, SERVER_PORT))
        print(f"Vlastná správa odoslaná pre {self.device_name}")
        if battery_low:
            print(f"(s upozornením na slabú batériu)")

        self.uat5_last_msg = msg
        self.uat5_waiting_ack = True
        if self.uat5_ack_timer:
            self.uat5_ack_timer.cancel()
        self.uat5_ack_timer = asyncio.create_task(self.uat5_wait_for_ack())

    def uat3_introduce_error(self):
        self.uat3_corrupt_next = True
        print(f" {self.device_name} pokazí CRC pri ďalšom automatickom odoslaní")

    def uat4_simulate_disconnect(self):
        self.uat4_active = False
        self.uat4_ping_delay = 2
        print(f"{self.device_name} zastavený (ignoruje 2 pingy, odpovie na 3.)")

    def stop(self):
        self.running = False
        if self.uat5_ack_timer and not self.uat5_ack_timer.done():
            self.uat5_ack_timer.cancel()
        if self.data_loop_task and not self.data_loop_task.done():
            self.data_loop_task.cancel()


async def ainput(prompt: str = "") -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, input, prompt)


def show_menu():
    print("FIITMeteo Tester MENU")
    print("1) Nastaviť IP a port")
    print("2) Spustiť automatické generovanie")
    print("3) Zastaviť automatické generovanie")
    print("4) Odoslať vlastnú správu")
    print("5) Zaviesť chybu do dát")
    print("6) Simulovať výpadok")
    print("7) Ukončiť")


async def main():
    global SERVER_IP, SERVER_PORT

    sensors = {}
    transports = {}
    loop = asyncio.get_event_loop()

    print("FIITMeteo Tester")
    print("USING BINARY PROTOCOL (optimized)")

    while True:
        show_menu()

        choice = await ainput("Voľba: ")

        if choice == "1":
            if sensors:
                print("Najprv zastavte senzory (voľba 3)")
            else:
                SERVER_IP = await ainput(f"IP servera (default {SERVER_IP}): ") or SERVER_IP
                port_input = await ainput(f"Port servera (default {SERVER_PORT}): ")
                SERVER_PORT = int(port_input) if port_input else SERVER_PORT
                print(f"Nastavené: {SERVER_IP}:{SERVER_PORT}")

        elif choice == "2":
            if sensors:
                print("Senzory už bežia!")
            else:
                print(f"\n→ Pripájam sa na server {SERVER_IP}:{SERVER_PORT}...")

                for name in ["ThermoNode", "WindSense", "RainDetect", "AirQualityBox"]:
                    transport, protocol_obj = await loop.create_datagram_endpoint(
                        lambda n=name: SimpleSensor(n),
                        remote_addr=(SERVER_IP, SERVER_PORT)
                    )
                    sensors[name] = protocol_obj
                    transports[name] = transport

                await asyncio.sleep(2)

                registered_count = sum(1 for s in sensors.values() if s.token is not None)
                active_tasks = sum(1 for s in sensors.values() if s.data_loop_task and not s.data_loop_task.done())

                if registered_count == 4 and active_tasks == 4:
                    print("Všetky senzory zaregistrované a bežia!")
                    print("Automatické generovanie ZAPNUTÉ (tiché - bez výpisov)")
                    print("Dáta sa posielajú každých 10 sekúnd na pozadí")
                    print("Použite voľbu 3 na zastavenie alebo 4-6 pre UAT testy")
                else:
                    print(f"Registrácia problematická: {registered_count}/4 senzorov, {active_tasks}/4 taskov")
                    print("Skúste zastaviť (3) a spustiť znova (2)")

        elif choice == "3":
            if sensors:
                print("→ Zastavujem všetky senzory...")

                for sensor in sensors.values():
                    sensor.stop()

                await asyncio.sleep(1.5)

                for transport in transports.values():
                    transport.close()

                sensors.clear()
                transports.clear()

                print("Všetky senzory zastavené a odpojené")
                print("Môžete ich znova spustiť voľbou 2")
            else:
                print("Žiadne senzory nebežia!")

        elif choice == "4":
            if not sensors:
                print("Najprv spustite automatické generovanie (voľba 2)!")
                continue

            print("\nDostupné senzory:")
            sensor_list = list(sensors.keys())
            for i, name in enumerate(sensor_list, 1):
                print(f"  {i}) {name}")

            sel_input = await ainput("Vyberte senzor (číslo): ")
            try:
                sel = int(sel_input)
                if 1 <= sel <= len(sensor_list):
                    selected_sensor = sensors[sensor_list[sel - 1]]

                    params = {
                        "ThermoNode": {
                            "temperature": (-50.0, 60.0, 1),
                            "humidity": (0.0, 100.0, 1),
                            "dew_point": (-50.0, 60.0, 1),
                            "pressure": (800.0, 1100.0, 2)
                        },
                        "WindSense": {
                            "wind_speed": (0.0, 50.0, 1),
                            "wind_gust": (0.0, 70.0, 1),
                            "wind_direction": (0, 359, 0),
                            "turbulence": (0.0, 1.0, 1)
                        },
                        "RainDetect": {
                            "rainfall": (0.0, 500.0, 1),
                            "soil_moisture": (0.0, 100.0, 1),
                            "flood_risk": (0, 3, 0),
                            "rain_duration": (0, 60, 0)
                        },
                        "AirQualityBox": {
                            "co2": (300, 5000, 0),
                            "ozone": (0.0, 500.0, 1),
                            "air_quality_index": (0, 500, 0)
                        }
                    }

                    battery_input = await ainput("Oznámiť serveru slabú batériu? (a/n): ")
                    battery_low = (battery_input.strip().lower() == 'a')

                    device_params = params[sensor_list[sel - 1]]
                    data = {}

                    print(f"\nZadajte hodnoty pre {sensor_list[sel - 1]}:")
                    for param_name, (min_val, max_val, decimals) in device_params.items():
                        while True:
                            try:
                                value_str = await ainput(f"  {param_name} ({min_val} - {max_val}): ")
                                if decimals == 0:
                                    value = int(float(value_str))
                                else:
                                    value = round(float(value_str), decimals)

                                if min_val <= value <= max_val:
                                    data[param_name] = value
                                    break
                                else:
                                    print(f"    Mimo rozsahu! Musí byť medzi {min_val} a {max_val}")
                            except ValueError:
                                print("    Neplatné číslo!")

                    selected_sensor.uat2_send_manual_data(data, battery_low)
                else:
                    print("Neplatný výber!")
            except ValueError:
                print("Zadajte číslo!")

        elif choice == "5":
            if not sensors:
                print("Najprv spustite automatické generovanie (voľba 2)!")
                continue

            print("\nDostupné senzory:")
            sensor_list = list(sensors.keys())
            for i, name in enumerate(sensor_list, 1):
                print(f"  {i}) {name}")

            sel_input = await ainput("Vyberte senzor (číslo): ")
            try:
                sel = int(sel_input)
                if 1 <= sel <= len(sensor_list):
                    selected_sensor = sensors[sensor_list[sel - 1]]
                    selected_sensor.uat3_introduce_error()

                    print("Čakám na ďalšie automatické odoslanie a detekciu chyby...")
                    try:
                        await asyncio.wait_for(selected_sensor.uat3_completed.wait(), timeout=15)
                        print("Test dokončený!\n")
                    except asyncio.TimeoutError:
                        print("Timeout - test nebol dokončený\n")
                    selected_sensor.uat3_completed.clear()
                else:
                    print("Neplatný výber!")
            except ValueError:
                print("Zadajte číslo!")

        elif choice == "6":
            if not sensors:
                print("Najprv spustite automatické generovanie (voľba 2)!")
                continue

            print("\nDostupné senzory:")
            sensor_list = list(sensors.keys())
            for i, name in enumerate(sensor_list, 1):
                print(f"  {i}) {name}")

            sel_input = await ainput("Vyberte senzor (číslo): ")
            try:
                sel = int(sel_input)
                if 1 <= sel <= len(sensor_list):
                    selected_sensor = sensors[sensor_list[sel - 1]]
                    selected_sensor.uat4_simulate_disconnect()

                    print("Čakám na disconnect, ping/pong cyklus a reconnect...")

                    try:
                        await asyncio.wait_for(selected_sensor.uat4_completed.wait(), timeout=40)
                        print("Test dokončený!\n")
                    except asyncio.TimeoutError:
                        print("Timeout - test nebol dokončený\n")

                    selected_sensor.uat4_completed.clear()
                else:
                    print("Neplatný výber!")
            except ValueError:
                print("Zadajte číslo!")

        elif choice == "7":
            print("→ Ukončujem...")

            for sensor in sensors.values():
                sensor.stop()

            for transport in transports.values():
                transport.close()
            break

        else:
            if choice.strip():
                print("Neplatná voľba!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nZastavené používateľom.")

import asyncio
import struct
import time
import zlib
import random

SERVER_IP = "127.0.0.1"
SERVER_PORT = 9999

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

DEVICE_TYPES = {
    "ThermoNode": DEVICE_THERMONODE,
    "WindSense": DEVICE_WINDSENSE,
    "RainDetect": DEVICE_RAINDETECT,
    "AirQualityBox": DEVICE_AIRQUALITY
}


def make_header(msg_type, device_type, flags=0):
    """Create common 5-byte header"""
    byte0 = (msg_type << 6) | (device_type << 4) | (flags & 0x0F)
    timestamp = int(time.time())
    return struct.pack('!BI', byte0, timestamp)


def make_register(device_type):
    """Create REGISTER message (5 bytes)"""
    return make_header(MSG_REGISTER, device_type)


def make_pong(device_type, token):
    """Create PONG message (9 bytes)"""
    header = make_header(MSG_CONTROL, device_type, CTRL_PONG)
    return header + struct.pack('!I', token)


def encode_device_data(device_type, data):
    """Encode device-specific data into binary format"""
    if device_type == DEVICE_THERMONODE:
        # temperature, humidity, dew_point, pressure
        temp = int(data["temperature"] * 10)
        hum = int(data["humidity"] * 10)
        dew = int(data["dew_point"] * 10)
        press = int(data["pressure"] * 100 - 80000)
        return struct.pack('!hHhH', temp, hum, dew, press)
    elif device_type == DEVICE_WINDSENSE:
        # wind_speed, wind_gust, wind_direction, turbulence
        speed = int(data["wind_speed"] * 10)
        gust = int(data["wind_gust"] * 10)
        direction = int(data["wind_direction"])
        turb = int(data["turbulence"] * 10)
        return struct.pack('!HHHB', speed, gust, direction, turb)
    elif device_type == DEVICE_RAINDETECT:
        # rainfall, soil_moisture, flood_risk, rain_duration
        rain = int(data["rainfall"] * 10)
        moist = int(data["soil_moisture"] * 10)
        risk = int(data["flood_risk"])
        duration = int(data["rain_duration"])
        return struct.pack('!HHBH', rain, moist, risk, duration)
    elif device_type == DEVICE_AIRQUALITY:
        # co2, ozone, air_quality_index
        co2 = int(data["co2"])
        ozone = int(data["ozone"] * 10)
        aqi = int(data["air_quality_index"])
        return struct.pack('!HHH', co2, ozone, aqi)
    return b''


def make_data(device_type, token, data, battery_low=False, corrupt_crc=False):
    """Create DATA message (variable size)"""
    flags = 0x01 if battery_low else 0x00
    header = make_header(MSG_DATA, device_type, flags)
    token_bytes = struct.pack('!I', token)
    payload = encode_device_data(device_type, data)

    # Calculate CRC over header + token + payload
    message_without_crc = header + token_bytes + payload
    crc = zlib.crc32(message_without_crc)

    if corrupt_crc:
        crc = crc ^ 0xFF  # Corrupt the CRC

    crc_bytes = struct.pack('!I', crc)
    return message_without_crc + crc_bytes


def parse_header(data):
    """Parse common header"""
    if len(data) < 5:
        return None
    byte0, timestamp = struct.unpack('!BI', data[:5])
    msg_type = (byte0 >> 6) & 0x03
    device_type = (byte0 >> 4) & 0x03
    flags = byte0 & 0x0F
    return msg_type, device_type, flags, timestamp


class SimpleSensor(asyncio.DatagramProtocol):
    def __init__(self, device_name):
        self.device_name = device_name
        self.device_type = DEVICE_TYPES[device_name]
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
        # Send REGISTER
        msg = make_register(self.device_type)
        self.transport.sendto(msg, (SERVER_IP, SERVER_PORT))

    def datagram_received(self, data, addr):
        if len(data) < 5:
            return

        header = parse_header(data)
        if not header:
            return

        msg_type, device_type, flags, timestamp = header

        if msg_type == MSG_REGISTER_ACK:
            # Extract token
            if len(data) >= 9:
                self.token = struct.unpack('!I', data[5:9])[0]
                if self.data_loop_task is None or self.data_loop_task.done():
                    self.data_loop_task = asyncio.create_task(self.data_loop())

        elif msg_type == MSG_CONTROL:
            ctrl_type = flags & 0x0F

            if ctrl_type == CTRL_DATA_ACK:
                # SILENT - no print for ACKs during automatic generation
                self.uat5_waiting_ack = False
                if self.uat5_ack_timer:
                    self.uat5_ack_timer.cancel()
                    self.uat5_ack_timer = None

            elif ctrl_type == CTRL_PING:
                if self.uat4_ping_delay > 0:
                    print(f"[UAT4] {self.device_name}: Prijatý ping #{3 - self.uat4_ping_delay}, ignorujem...")
                    self.uat4_ping_delay -= 1
                else:
                    print(f"[UAT4] {self.device_name}: Prijatý ping, odpovedám PONG...")
                    pong = make_pong(self.device_type, self.token)
                    self.transport.sendto(pong, (SERVER_IP, SERVER_PORT))
                    if not self.uat4_active:
                        self.uat4_active = True
                        print(f"[UAT4] {self.device_name}: OBNOVENÉ automatické odosielanie!")
                        self.uat4_completed.set()

            elif ctrl_type == CTRL_ERROR:
                if len(data) >= 6:
                    error_code = struct.unpack('!B', data[5:6])[0]
                    if error_code == ERR_CRC_FAIL:
                        print(f"[UAT3] {self.device_name}: Server detekoval CRC chybu, posielam znova...")
                        if self.uat5_last_msg:
                            # Resend without corruption
                            self.transport.sendto(self.uat5_last_msg, (SERVER_IP, SERVER_PORT))
                            self.uat3_completed.set()

    def error_received(self, exc):
        if isinstance(exc, OSError):
            pass
        else:
            print(f"[ERROR] {self.device_name} protocol error: {exc}")

    async def data_loop(self):
        await asyncio.sleep(1)

        while self.running:
            if not self.transport or self.transport.is_closing():
                break

            if self.uat4_active:
                # Generate random data based on device type
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
                else:  # AirQualityBox
                    data = {
                        "co2": random.randint(400, 1000),
                        "ozone": round(random.uniform(0, 200), 1),
                        "air_quality_index": random.randint(0, 200)
                    }

                corrupt = self.uat3_corrupt_next
                if corrupt:
                    print(f"[UAT3] {self.device_name}: Zavádzam CRC chybu do ďalšej správy...")
                    self.uat3_corrupt_next = False

                msg = make_data(self.device_type, self.token, data, corrupt_crc=corrupt)

                # For UAT3, we need to save the clean version for resend
                if corrupt:
                    self.uat5_last_msg = make_data(self.device_type, self.token, data, corrupt_crc=False)
                else:
                    self.uat5_last_msg = msg

                self.transport.sendto(msg, (SERVER_IP, SERVER_PORT))

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

        msg = make_data(self.device_type, self.token, data, battery_low=battery_low)
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
    print("FIITMeteo Tester MENU (Binary Protocol)")
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

    print("FIITMeteo Tester (Binary Protocol)")

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
                    transport, protocol = await loop.create_datagram_endpoint(
                        lambda n=name: SimpleSensor(n),
                        remote_addr=(SERVER_IP, SERVER_PORT)
                    )
                    sensors[name] = protocol
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

                    # Get parameter ranges
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

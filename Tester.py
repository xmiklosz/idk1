import asyncio
import json
import random
import time
import zlib

SERVER_IP = "127.0.0.1"
SERVER_PORT = 9999
SEND_INTERVAL = 10
ACK_TIMEOUT = 1  # 1 second for UAT5


# ==============================
# Pomocné funkcie
# ==============================
def current_time():
    return int(time.time())


def calc_crc(data: dict) -> str:
    return format(zlib.crc32(json.dumps(data, sort_keys=True).encode()), "08X")


def make_message(msg_type, device_type, token=None, data=None, battery=False, corrupt=False):
    msg = {
        "type": msg_type,
        "device_type": device_type,
        "timestamp": current_time(),
        "battery_low": battery
    }
    if token:
        msg["token"] = token
    if data:
        msg["data"] = data

    crc = calc_crc(msg)
    msg["crc"] = crc

    # Corrupt CRC if requested
    if corrupt:
        msg["crc"] = crc[:-1] + ("0" if crc[-1] != "0" else "1")

    return json.dumps(msg).encode()


# ==============================
# Profily zariadení s rozsahmi
# ==============================
DEVICE_PROFILES = {
    "ThermoNode": {
        "params": {
            "temperature": {"min": -50.0, "max": 60.0, "decimals": 1, "unit": "°C"},
            "humidity": {"min": 0.0, "max": 100.0, "decimals": 1, "unit": "%"},
            "dew_point": {"min": -50.0, "max": 60.0, "decimals": 1, "unit": "°C"},
            "pressure": {"min": 800.0, "max": 1100.0, "decimals": 2, "unit": "hPa"}
        },
        "generator": lambda: {
            "temperature": round(random.uniform(-10, 40), 1),
            "humidity": round(random.uniform(20, 90), 1),
            "dew_point": round(random.uniform(-10, 25), 1),
            "pressure": round(random.uniform(950, 1050), 2)
        }
    },
    "WindSense": {
        "params": {
            "wind_speed": {"min": 0.0, "max": 50.0, "decimals": 1, "unit": "m/s"},
            "wind_gust": {"min": 0.0, "max": 70.0, "decimals": 1, "unit": "m/s"},
            "wind_direction": {"min": 0, "max": 359, "decimals": 0, "unit": "°"},
            "turbulence": {"min": 0.0, "max": 1.0, "decimals": 1, "unit": ""}
        },
        "generator": lambda: {
            "wind_speed": round(random.uniform(0, 30), 1),
            "wind_gust": round(random.uniform(0, 50), 1),
            "wind_direction": random.randint(0, 359),
            "turbulence": round(random.uniform(0, 1), 1)
        }
    },
    "RainDetect": {
        "params": {
            "rainfall": {"min": 0.0, "max": 500.0, "decimals": 1, "unit": "mm"},
            "soil_moisture": {"min": 0.0, "max": 100.0, "decimals": 1, "unit": "%"},
            "flood_risk": {"min": 0, "max": 3, "decimals": 0, "unit": "",
                           "options": {0: "none", 1: "low", 2: "medium", 3: "high"}},
            "rain_duration": {"min": 0, "max": 60, "decimals": 0, "unit": "min"}
        },
        "generator": lambda: {
            "rainfall": round(random.uniform(0, 30), 1),
            "soil_moisture": round(random.uniform(0, 100), 1),
            "flood_risk": random.randint(0, 3),
            "rain_duration": random.randint(0, 60)
        }
    },
    "AirQualityBox": {
        "params": {
            "co2": {"min": 300, "max": 5000, "decimals": 0, "unit": "ppm"},
            "ozone": {"min": 0.0, "max": 500.0, "decimals": 1, "unit": "μg/m³"},
            "air_quality_index": {"min": 0, "max": 500, "decimals": 0, "unit": ""}
        },
        "generator": lambda: {
            "co2": random.randint(350, 2000),
            "ozone": round(random.uniform(0, 300), 1),
            "air_quality_index": random.randint(0, 500)
        }
    }
}


# ==============================
# Trieda senzora
# ==============================
class SensorClient:
    def __init__(self, device_type, loop):
        self.device_type = device_type
        self.token = None
        self.transport = None
        self.loop = loop
        self.active = True
        self.auto_send_active = False
        self.last_message = None
        self.last_data = None
        self.introduce_error_next = False
        self.wait_for_ack = False
        self.ack_timer = None
        self.ping_response_delay = 0  # For UAT4
        self.retransmit_count = 0

    def connection_made(self, transport):
        self.transport = transport
        self.register()

    def datagram_received(self, data, addr):
        try:
            msg = json.loads(data.decode())
            msg_type = msg.get("type")

            if msg_type == "register_ack":
                self.token = msg["token"]
                print(f"[{self.device_type}] Zaregistrovaný s tokenom {self.token}")

            elif msg_type == "data_ack":
                print(f"[{self.device_type}] Dáta potvrdené")
                self.wait_for_ack = False
                self.retransmit_count = 0
                if self.ack_timer:
                    self.ack_timer.cancel()
                    self.ack_timer = None

            elif msg_type == "error":
                error_type = msg.get("error")
                if error_type == "CRC_FAIL":
                    print(f"[{self.device_type}] Server detekoval chybu CRC, posielam dáta znova...")
                    # Resend last data without error
                    if self.last_data:
                        clean_msg = make_message("data", self.device_type, self.token, self.last_data, corrupt=False)
                        self.transport.sendto(clean_msg, (SERVER_IP, SERVER_PORT))
                elif error_type == "INVALID_TOKEN":
                    print(f"[{self.device_type}] Neplatný token! Registrujem sa znova...")
                    self.register()

            elif msg_type == "ping":
                # For UAT4: delay response based on ping_response_delay
                if self.ping_response_delay > 0:
                    print(f"[{self.device_type}] Ping prijatý, ale čakám {self.ping_response_delay} pingov pred odpoveďou...")
                    self.ping_response_delay -= 1
                else:
                    print(f"[{self.device_type}] Odpovedám na ping...")
                    pong = make_message("pong", self.device_type, self.token)
                    self.transport.sendto(pong, (SERVER_IP, SERVER_PORT))
                    # Reactivate sending after responding
                    if not self.active:
                        self.active = True
                        print(f"[{self.device_type}] Obnovujem automatické odosielanie...")
        except Exception as e:
            print(f"[{self.device_type}] Chyba pri spracovaní správy: {e}")

    def register(self):
        msg = make_message("register", self.device_type)
        self.transport.sendto(msg, (SERVER_IP, SERVER_PORT))
        print(f"[{self.device_type}] Registračná správa odoslaná")

    async def wait_for_ack_with_timeout(self):
        """UAT5: Wait for ACK, retransmit if timeout"""
        await asyncio.sleep(ACK_TIMEOUT)
        if self.wait_for_ack:
            # No ACK received, retransmit
            self.retransmit_count += 1
            print(f"[{self.device_type}] Nedostal som ACK, posielam znova... (pokus #{self.retransmit_count + 1})")
            self.transport.sendto(self.last_message, (SERVER_IP, SERVER_PORT))
            # Schedule another timeout check
            self.ack_timer = self.loop.create_task(self.wait_for_ack_with_timeout())

    async def auto_send_data(self):
        """Automatic data sending every SEND_INTERVAL seconds"""
        # Wait for token to be received before starting
        max_wait = 30
        waited = 0
        while not self.token and waited < max_wait:
            await asyncio.sleep(0.5)
            waited += 0.5

        if not self.token:
            print(f"[{self.device_type}] CHYBA: Token nebol prijatý!")
            return

        print(f"[{self.device_type}] Začínam automatické odosielanie dát...")

        while self.auto_send_active:
            if self.active:  # Only send if not disconnected (UAT4)
                # Generate data
                generator = DEVICE_PROFILES[self.device_type]["generator"]
                data = generator()
                self.last_data = data

                # Check if error should be introduced (UAT3)
                corrupt = self.introduce_error_next
                if corrupt:
                    print(f"[{self.device_type}] Zavádzam chybu CRC do správy...")
                    self.introduce_error_next = False

                # Create and send message
                msg = make_message("data", self.device_type, self.token, data, corrupt=corrupt)
                self.last_message = msg
                self.transport.sendto(msg, (SERVER_IP, SERVER_PORT))

                # UAT5: Start waiting for ACK
                self.wait_for_ack = True
                self.retransmit_count = 0
                if self.ack_timer:
                    self.ack_timer.cancel()
                self.ack_timer = self.loop.create_task(self.wait_for_ack_with_timeout())

            await asyncio.sleep(SEND_INTERVAL)

    def send_manual_data(self):
        """UAT2: Manual data entry and sending"""
        if not self.token:
            print(f"[{self.device_type}] CHYBA: Senzor nie je zaregistrovaný!")
            return

        print(f"\n=== Odoslanie vlastnej správy pre {self.device_type} ===")

        # Step 1: Ask about low battery
        battery_input = input("Oznámiť serveru slabú batériu? (a/n): ").strip().lower()
        battery_low = battery_input == 'a'

        # Step 2: Get values for each parameter
        params = DEVICE_PROFILES[self.device_type]["params"]
        data = {}

        for param_name, param_info in params.items():
            while True:
                if "options" in param_info:
                    # For parameters with discrete options (like flood_risk)
                    print(f"\n{param_name}:")
                    for key, val in param_info["options"].items():
                        print(f"  {key} - {val}")
                    value_input = input(f"Zadaj hodnotu ({param_info['min']}-{param_info['max']}): ").strip()
                else:
                    # For numeric parameters
                    print(f"\n{param_name}: ({param_info['min']} - {param_info['max']}) {param_info['unit']}")
                    value_input = input(f"Zadaj hodnotu: ").strip()

                try:
                    if param_info["decimals"] == 0:
                        value = int(float(value_input))
                    else:
                        value = round(float(value_input), param_info["decimals"])

                    # Validate range
                    if param_info["min"] <= value <= param_info["max"]:
                        data[param_name] = value
                        break
                    else:
                        print(f"Hodnota mimo rozsahu! ({param_info['min']} - {param_info['max']})")
                except ValueError:
                    print("Neplatná hodnota! Zadaj číslo.")

        # Step 3: Send the message
        self.last_data = data
        msg = make_message("data", self.device_type, self.token, data, battery=battery_low)
        self.last_message = msg
        self.transport.sendto(msg, (SERVER_IP, SERVER_PORT))

        # UAT5: Start waiting for ACK
        self.wait_for_ack = True
        self.retransmit_count = 0
        if self.ack_timer:
            self.ack_timer.cancel()
        self.ack_timer = self.loop.create_task(self.wait_for_ack_with_timeout())

        print(f"\n✓ Vlastná správa odoslaná pre {self.device_type}!")
        if battery_low:
            print("  (s upozornením na slabú batériu)")

    def simulate_error_next(self):
        """UAT3: Set flag to corrupt next automatic message"""
        self.introduce_error_next = True
        print(f"[{self.device_type}] Chyba CRC bude zavedená pri ďalšom automatickom odoslaní")

    def simulate_disconnect(self):
        """UAT4: Stop sending messages and delay ping response"""
        self.active = False
        self.ping_response_delay = 2  # Respond after 3rd ping (0, 1, 2 -> respond on 3rd)
        print(f"[{self.device_type}] Vypnutý – neodosiela správy (UAT4)")
        print(f"[{self.device_type}] Odpoviem na ping až po 3. pokuse servera")


# ==============================
# CLI menu pre tester
# ==============================
async def run_tester():
    global SERVER_IP, SERVER_PORT
    loop = asyncio.get_running_loop()
    sensors = {}
    auto_send_tasks = {}

    while True:
        print("\n===== FIITMeteo Tester =====")
        print("1) Nastaviť IP a port")
        print("2) Spustiť automatické generovanie")
        print("3) Zastaviť automatické generovanie")
        print("4) Odoslať vlastnú správu (UAT2)")
        print("5) Zaviesť chybu do dát (UAT3)")
        print("6) Simulovať výpadok (UAT4)")
        print("7) Ukončiť")
        choice = input("Voľba: ").strip()

        if choice == "1":
            SERVER_IP = input(f"IP servera (default {SERVER_IP}): ").strip() or SERVER_IP
            port_input = input(f"Port servera (default {SERVER_PORT}): ").strip()
            SERVER_PORT = int(port_input) if port_input else SERVER_PORT
            print(f"Nastavené: {SERVER_IP}:{SERVER_PORT}")

        elif choice == "2":
            if not sensors:
                print("\nRegistrujem senzory a spúšťam automatické generovanie...")
                for device_name in DEVICE_PROFILES.keys():
                    try:
                        # Create sensor
                        sensor_instance = SensorClient(device_name, loop)

                        # Create UDP endpoint
                        transport, _ = await loop.create_datagram_endpoint(
                            lambda s=sensor_instance: s,
                            remote_addr=(SERVER_IP, SERVER_PORT)
                        )

                        sensors[device_name] = sensor_instance
                        sensor_instance.auto_send_active = True
                        task = loop.create_task(sensor_instance.auto_send_data())
                        auto_send_tasks[device_name] = task
                        print(f"  ✓ {device_name} zaregistrovaný")
                    except Exception as e:
                        print(f"  ✗ Chyba pri registrácii {device_name}: {e}")
                        import traceback
                        traceback.print_exc()
                print("\nAutomatické generovanie spustené (každých 10 sekúnd)")
            else:
                # Reactivate if already created
                for device, sensor in sensors.items():
                    if not sensor.auto_send_active:
                        sensor.auto_send_active = True
                        task = loop.create_task(sensor.auto_send_data())
                        auto_send_tasks[device] = task
                print("Automatické generovanie znovu spustené")

        elif choice == "3":
            if sensors:
                for sensor in sensors.values():
                    sensor.auto_send_active = False
                for task in auto_send_tasks.values():
                    task.cancel()
                auto_send_tasks.clear()
                print("Automatické generovanie zastavené")
            else:
                print("Žiadne senzory nie sú aktívne!")

        elif choice == "4":
            if sensors:
                print("\nDostupné senzory:")
                device_list = list(sensors.keys())
                for i, device in enumerate(device_list, 1):
                    print(f"{i}) {device}")

                try:
                    selection = int(input("\nVyber senzor (číslo): ").strip())
                    if 1 <= selection <= len(device_list):
                        selected_device = device_list[selection - 1]
                        sensors[selected_device].send_manual_data()
                    else:
                        print("Neplatný výber!")
                except ValueError:
                    print("Zadaj číslo!")
            else:
                print("Najprv spusti automatické generovanie (voľba 2)!")

        elif choice == "5":
            if sensors:
                print("\nDostupné senzory:")
                device_list = list(sensors.keys())
                for i, device in enumerate(device_list, 1):
                    print(f"{i}) {device}")

                try:
                    selection = int(input("\nVyber senzor (číslo): ").strip())
                    if 1 <= selection <= len(device_list):
                        selected_device = device_list[selection - 1]
                        sensors[selected_device].simulate_error_next()
                    else:
                        print("Neplatný výber!")
                except ValueError:
                    print("Zadaj číslo!")
            else:
                print("Najprv spusti automatické generovanie (voľba 2)!")

        elif choice == "6":
            if sensors:
                print("\nDostupné senzory:")
                device_list = list(sensors.keys())
                for i, device in enumerate(device_list, 1):
                    print(f"{i}) {device}")

                try:
                    selection = int(input("\nVyber senzor (číslo): ").strip())
                    if 1 <= selection <= len(device_list):
                        selected_device = device_list[selection - 1]
                        sensors[selected_device].simulate_disconnect()
                    else:
                        print("Neplatný výber!")
                except ValueError:
                    print("Zadaj číslo!")
            else:
                print("Najprv spusti automatické generovanie (voľba 2)!")

        elif choice == "7":
            print("Tester ukončený.")
            # Cancel all tasks
            for task in auto_send_tasks.values():
                task.cancel()
            break


if __name__ == "__main__":
    try:
        asyncio.run(run_tester())
    except KeyboardInterrupt:
        print("\nProgram ukončený používateľom.")
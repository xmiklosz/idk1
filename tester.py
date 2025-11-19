import socket
import time
import random
import threading
from binary_protocol import encode_message, decode_message

IP = None
PORT = None
TIMEOUT = 1.0
TOKENS = {}
PAUSED_SENSORS = {}
SIMULATE_ERROR_SENSORS = {}

def now_unix():
    return int(time.time())

def verify_checksum_client(msg):
    """Check if message has valid checksum."""
    return msg.get("_checksum_valid", False)

def ThermoNode_payload():
    temp = round(random.uniform(-50.0, 60.0), 1)
    hum = round(random.uniform(0.0, 100.0), 1)
    dew = round(random.uniform(-50.0, 60.0), 1)
    pressure = round(random.uniform(800.0, 1100.0), 2)
    return {"temp": f"{temp}°C", "hum": f"{hum}%", "dew": f"{dew}°C", "pressure": f"{pressure}hPa"}

def WindSense_payload():
    speed = round(random.uniform(0.0, 50.0), 1)
    gust = round(random.uniform(0.0, 70.0), 1)
    direction = random.randint(0, 359)
    turbulance = round(random.uniform(0.0, 1.0), 1)
    return {"speed": f"{speed}m/s", "gust": f"{gust}m/s", "direction": f"{direction}°", "turbulance": f"{turbulance}"}

def RainDetect_payload():
    rainfall = round(random.uniform(0.0, 500.0), 1)
    soil = round(random.uniform(0.0, 100.0), 1)
    flood = random.randint(0, 3)
    duration = random.randint(0, 60)
    return {"rainfall": f"{rainfall}mm", "soil": f"{soil}%", "flood": str(flood), "duration": str(duration)}

def AirQualityBox_payload():
    CO2 = random.randint(300, 5000)
    ozone = round(random.uniform(0.0, 500.0), 1)
    quality = random.randint(0, 500)
    return {"CO2": f"{CO2}ppm", "ozone": f"{ozone}µg/m³", "quality": f"{quality}AQI"}

SENSOR_FUNCS = {
    "1": ("ThermoNode", ThermoNode_payload),
    "2": ("WindSense", WindSense_payload),
    "3": ("RainDetect", RainDetect_payload),
    "4": ("AirQualityBox", AirQualityBox_payload),
}

def choose_sensor(c):
    return SENSOR_FUNCS.get(c)

def send_and_wait(sock, addr, obj, timeout=TIMEOUT, max_retries=3, corrupt_first=False):
    created_local_sock = False
    if sock is None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        created_local_sock = True

    try:
        for attempt in range(1, max_retries + 1):
            try:
                # Encode message to binary
                binary_msg = encode_message(obj)

                if corrupt_first and attempt == 1:
                    # Corrupt the checksum (last 4 bytes)
                    binary_msg = binary_msg[:-4] + bytes([(binary_msg[-4] ^ 0xFF)]) + binary_msg[-3:]

                sock.sendto(binary_msg, addr)
            except Exception as e:
                print(f"Send error (attempt {attempt}):", e)
                if attempt >= max_retries:
                    return None
                time.sleep(0.1)
                continue

            sock.settimeout(timeout)
            try:
                data, _ = sock.recvfrom(65536)
                resp = decode_message(data)
            except socket.timeout:
                resp = None
            except Exception as e:
                print("Recv error:", e)
                return None

            if resp is None:
                if attempt < max_retries:
                    time.sleep(0.1)
                    continue
                else:
                    return None

            if not verify_checksum_client(resp):
                print(f"Odpoveď servera obsahuje chybný alebo chýbajúci checksum (pokus {attempt}). Opakujem pokus")
                if attempt < max_retries:
                    time.sleep(0.1)
                    continue
                else:
                    return None

            if resp.get("type") == "checksum_error":
                print(f"Odozva servera: checksum_error (pokus {attempt}). Opätovné odoslanie")
                if attempt < max_retries:
                    time.sleep(0.1)
                    continue
                else:
                    return resp

            return resp
        return None
    finally:
        if created_local_sock:
            sock.close()

def send_and_wait_until_ack(sock, addr, obj, stop_event=None, timeout=TIMEOUT, retry_interval=0.2):
    if sock is None:
        raise ValueError("send_and_wait_until_ack: sock must be provided")
    base_obj = obj.copy()
    while True:
        if stop_event and stop_event.is_set():
            return None
        try:
            binary_msg = encode_message(base_obj)
            try:
                sock.sendto(binary_msg, addr)
            except Exception as e:
                print("Chyba pri odosielaní:", e)
                if stop_event and stop_event.is_set():
                    return None
                time.sleep(retry_interval)
                continue
        except Exception as e:
            print("Chyba pri vytváraní správy:", e)
            return None
        try:
            sock.settimeout(timeout)
            data, _ = sock.recvfrom(65536)
            resp = decode_message(data)
        except socket.timeout:
            resp = None
        except Exception as e:
            print("Recv error while waiting for ack:", e)
            resp = None

        if resp is None:
            time.sleep(retry_interval)
            continue

        if not verify_checksum_client(resp):
            print("„Odpoveď servera obsahuje chybný alebo chýbajúci checksum. Opätovné odoslanie")
            time.sleep(retry_interval)
            continue

        rtype = resp.get("type")
        if rtype == "ack":
            return resp
        if rtype == "checksum_error":
            print("Server poslal odpoveď checksum_error — opätovne odosielanie správu")
            time.sleep(retry_interval)
            continue
        if rtype in ("invalid_token", "error"):
            print("Server odpovedal s chybou:", resp)
            return resp
        print("Od servera prišla ne-ACK odpoveď (ignorované):", resp)
        time.sleep(retry_interval)
        continue

def ping_listener(listen_sock, sensor_name, token, ping_counter, resume_event, stop_event):
    listen_sock.settimeout(1.0)
    try:
        while not stop_event.is_set() and not resume_event.is_set():
            try:
                data, addr = listen_sock.recvfrom(65536)
            except socket.timeout:
                continue
            except Exception:
                break
            try:
                msg = decode_message(data)
            except Exception:
                continue

            if msg.get("type") == "ping" and msg.get("token") == token:
                ping_counter['count'] += 1
                current_count = ping_counter['count']
                print(f"{sensor_name}: Ping #{current_count} prijaté zo servera")

                if current_count >= 3:
                    print(f"{sensor_name}: Prijaté 3 pingy, reštart a odoslanie odpovede")
                    resp = {
                        "type": "ping_response",
                        "token": token,
                        "timestamp": now_unix(),
                        "device_type": sensor_name
                    }
                    binary_resp = encode_message(resp)
                    try:
                        listen_sock.sendto(binary_resp, addr)
                    except Exception:
                        pass

                    resume_event.set()
                    break
                else:
                    print(f"{sensor_name}: Ešte neodpovedám, čakáme na 3. ping ({current_count}/3)")
    finally:
        return

def _pretty_print_payload_as_lines(sensor_name, payload, timestamp):
    print(f"INFO: @{sensor_name} CORRUPTED DATA at @{timestamp}. REQUESTING DATA")
    print(f"@{timestamp} @{sensor_name}")
    if isinstance(payload, dict):
        parts = []
        for k, v in payload.items():
            parts.append(f"{k}: {v}")
        print("; ".join(parts) + ";")
    else:
        print(str(payload))
    print("")

def background_sender(server_addr, sensor_name, sensor_func, token, stop_event, mode='1', custom_payload=None, pause_event=None, resume_event=None):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        while not stop_event.is_set():
            if pause_event and pause_event.is_set():
                ping_counter = {'count': 0}
                ping_thread = threading.Thread(
                    target=ping_listener,
                    args=(sock, sensor_name, token, ping_counter, resume_event, stop_event),
                    daemon=True
                )
                ping_thread.start()

                print(f"{sensor_name}: Spúšťa sa sledovanie pingov, čakáme na 3. ping")
                while not resume_event.is_set() and not stop_event.is_set():
                    time.sleep(0.1)
                if ping_thread.is_alive():
                    ping_thread.join(timeout=2.0)

                if resume_event.is_set():
                    print(f"{sensor_name}: Pokračovanie v odosielaní dát")
                    pause_event.clear()
                    resume_event.clear()
                    PAUSED_SENSORS[sensor_name] = False
                continue

            try:
                if SIMULATE_ERROR_SENSORS.get(sensor_name):
                    SIMULATE_ERROR_SENSORS[sensor_name] = False
                    print(f"{sensor_name}: Hibaszimuláció — a következő autosend körben csak a hibás üzenetet küldi (nem küld normál üzenetet ezen a körön).")

                    payload = sensor_func()
                    timestamp = now_unix()
                    data_msg = {
                        "type": "data",
                        "device_type": sensor_name,
                        "timestamp": timestamp,
                        "low_battery": False,
                        "token": token,
                        "payload": payload
                    }

                    _pretty_print_payload_as_lines(sensor_name, payload, timestamp)

                    resp = send_and_wait(sock, server_addr, data_msg, max_retries=1, corrupt_first=True)
                    if resp is None:
                        print(f"{sensor_name}: Žiadna odpoveď zo servera na chybné správy")
                        pass
                    else:
                        if resp.get("type") == "checksum_error":
                            print(f"{sensor_name}: Server vrátil checksum_error — okamžitá opätovná odosielka správnej správy")
                            resp2 = send_and_wait(sock, server_addr, data_msg, max_retries=3, corrupt_first=False)
                            if resp2 is None:
                                print(f"{sensor_name}: Žiadna odpoveď na správnu správu")
                            else:
                                print(f"{sensor_name}: Odpoveď na správnu správu: {resp2}")
                        else:
                            print(f"{sensor_name}: Odpoveď na chybnú správu (neočakávané): {resp}")
                    total = 10.0
                    step = 0.1
                    slept = 0.0
                    while slept < total and not stop_event.is_set():
                        time.sleep(step)
                        slept += step
                    continue
            except Exception as e:
                print(f"{sensor_name}: Chyba pri vykonávaní hibovej simulácie: {e}")

            if mode == '1':
                payload = sensor_func()
                data_msg = {
                    "type": "data",
                    "device_type": sensor_name,
                    "timestamp": now_unix(),
                    "low_battery": False,
                    "token": token,
                    "payload": payload
                }
                resp = send_and_wait_until_ack(sock, server_addr, data_msg, stop_event=stop_event)
            elif mode == '2':
                payload = custom_payload
                data_msg = {
                    "type": "data",
                    "device_type": sensor_name,
                    "timestamp": now_unix(),
                    "low_battery": False,
                    "token": token,
                    "payload": payload
                }
                resp = send_and_wait_until_ack(sock, server_addr, data_msg, stop_event=stop_event)
            elif mode == '3':
                payload = sensor_func()
                data_msg = {
                    "type": "data",
                    "device_type": sensor_name,
                    "timestamp": now_unix(),
                    "low_battery": False,
                    "token": token,
                    "payload": payload
                }
                resp = send_and_wait(sock, server_addr, data_msg, max_retries=1, corrupt_first=True)
                if resp is None:
                    print(f"{sensor_name}: Žiadna odpoveď zo servera na chybné správy")
                elif resp.get("type") == "checksum_error":
                    print(f"{sensor_name}: Server checksum_error – odosielanie správnu správu")
                    resp2 = send_and_wait(sock, server_addr, data_msg, max_retries=3, corrupt_first=False)
                    if resp2 is None:
                        print(f"{sensor_name}: Žiadna odpoveď na správnu správu")
                    else:
                        print(f"{sensor_name}: Odpoveď na správnu správu: {resp2}")
                else:
                    print(f"{sensor_name}: Neočakávaná odpoveď na chybnú správu: {resp}")
                return
            else:
                payload = sensor_func()
                data_msg = {
                    "type": "data",
                    "device_type": sensor_name,
                    "timestamp": now_unix(),
                    "low_battery": False,
                    "token": token,
                    "payload": payload
                }
                resp = send_and_wait_until_ack(sock, server_addr, data_msg, stop_event=stop_event)

            if resp is None:
                if stop_event.is_set():
                    break
            elif resp.get("type") == "checksum_error":
                print(f"{sensor_name}: Normál küldésre érkezett checksum_error: {resp}")

            total = 10.0
            step = 0.1
            slept = 0.0
            while slept < total and not stop_event.is_set():
                time.sleep(step)
                slept += step

    except Exception as e:
        print(f"Chyba background sendera ({sensor_name}):", e)
    finally:
        sock.close()

def register_device(server_addr, sensor_name):
    reg_msg = {"type": "register", "device_type": sensor_name, "timestamp": now_unix(), "low_battery": False,
               "token": ""}
    resp = send_and_wait(None, server_addr, reg_msg)
    return resp

def show_main_menu():
    print("\n--- HLAVNÉ MENU ---")
    print("1. automatické generovanie (VŠETKY 4 senzory na pozadí)")
    print("2. vlastná správa (ručné, po poliach, jednorazové odoslanie)")
    print("3. chyby do správy (simulácia chyby pri pozadí odosielaní)")
    print("4. odpojenie senzora (vypnutie senzora)")
    print("5. ukončiť")
    choice = input("Vyber (1–5): ").strip()
    return choice

def choose_sensor_menu():
    print("\nVyber senzor:")
    print(" 1) ThermoNode")
    print(" 2) WindSense")
    print(" 3) RainDetect")
    print(" 4) AirQualityBox")
    s = input("Senzor (1-4): ").strip()
    return s

def ask_battery_status():
    while True:
        response = input("Má sen nízku úroveň batérie? (a/n): ").strip().lower()
        if response in ('a', 'ano', 'y', 'yes'):
            return True
        elif response in ('n', 'nie', 'no'):
            return False
        else:
            print("Neplatná odpoveď. Prosím, odpovedz znakom 'a' (áno) alebo 'n' (nie).")

REQUIRED_FIELDS = {
    "ThermoNode": [
        ("temp", -50.0, 60.0, "°C", False),
        ("hum", 0.0, 100.0, "%", False),
        ("dew", -50.0, 60.0, "°C", False),
        ("pressure", 800.0, 1100.0, "hPa", False),
    ],
    "WindSense": [
        ("speed", 0.0, 50.0, "m/s", False),
        ("gust", 0.0, 70.0, "m/s", False),
        ("direction", 0, 359, "°", True),
        ("turbulance", 0.0, 1.0, "", False),
    ],
    "RainDetect": [
        ("rainfall", 0.0, 500.0, "mm", False),
        ("soil", 0.0, 100.0, "%", False),
        ("flood", 0, 3, "", True),
        ("duration", 0, 60, "s", True),
    ],
    "AirQualityBox": [
        ("CO2", 300, 5000, "ppm", True),
        ("ozone", 0.0, 500.0, "µg/m³", False),
        ("quality", 0, 500, "AQI", True),
    ],
}

def prompt_numeric(field_name, minv, maxv, unit, is_int):
    range_text = f"({minv} .. {maxv})"
    unit_text = f" {unit}" if unit else ""
    prompt = f"Zadaj hodnotu pre {field_name} {range_text}{unit_text}: "
    while True:
        s = input(prompt).strip()
        if s == "":
            print("Prázdny vstup — zadaj číslo")
            continue
        s_norm = s.replace(",", ".")
        try:
            if is_int:
                if "." in s_norm:
                    print("Je potrebné celé číslo (napr. 5). Skús to znova")
                    continue
                val = int(s_norm)
            else:
                val = float(s_norm)
        except Exception:
            print("Neplatný formát čísla — skús znova (napr. 23.4)")
            continue
        if val < minv or val > maxv:
            print(f"Hodnota je mimo rozsah {minv} .. {maxv}. Skús znova")
            continue
        return val

def collect_structured_payload(sensor_name):
    fields = REQUIRED_FIELDS.get(sensor_name)
    if not fields:
        print("Nie je definované pole pre tento senzor — payload bude prázdny")
        return {}
    payload = {}
    print(f"\nRučné zadávanie dát pre senzor {sensor_name}. Zadaj nasledujúce polia v predpísanom intervale")
    for fname, minv, maxv, unit, is_int in fields:
        val = prompt_numeric(fname, minv, maxv, unit, is_int)
        if fname == "pressure":
            val_str = f"{round(float(val), 2)}{unit}" if unit else f"{round(float(val), 2)}"
            payload[fname] = val_str
        elif is_int:
            if unit == "":
                payload[fname] = str(int(val))
            else:
                payload[fname] = f"{int(val)}{unit}"
        else:
            val_rounded = round(float(val), 1)
            if unit:
                payload[fname] = f"{val_rounded}{unit}"
            else:
                payload[fname] = val_rounded
    print("Vstup dokončený:", payload)
    return payload

def send_one_data(server_addr, sensor_name, token, payload, low_battery=False):
    data_msg = {
        "type": "data",
        "device_type": sensor_name,
        "timestamp": now_unix(),
        "low_battery": low_battery,
        "token": token,
        "payload": payload
    }
    print(f"\n>>> ODOSIELANIE NA SERVER: {sensor_name}")
    print(f">>> ÚDAJE: {payload}")
    if low_battery:
        print(">>> UPOZORNENIE: NÍZKA BATÉRIA!")

    resp = send_and_wait(None, server_addr, data_msg)

    if resp is None:
        print(">>> CHYBA: Žiadna odpoveď od servera")
    else:
        print(f">>> ODPOVEĎ SERVERA: {resp}")

    return resp

BACKGROUND_STATE = {
    'active': False,
    'threads': [],
    'stop_event': None,
    'pause_events': {},
    'resume_events': {},
    'sensor_data': []
}

def start_background_senders(server_addr, active_sensors):
    stop_event = threading.Event()
    pause_events = {}
    resume_events = {}
    sender_threads = []
    for sensor_name, sensor_func, token in active_sensors:
        pause_event = threading.Event()
        resume_event = threading.Event()
        pause_events[sensor_name] = pause_event
        resume_events[sensor_name] = resume_event
        thread = threading.Thread(
            target=background_sender,
            args=(server_addr, sensor_name, sensor_func, token, stop_event, '1', None, pause_event, resume_event),
            daemon=True,
            name=f"Thread-{sensor_name}"
        )
        thread.start()
        sender_threads.append(thread)
        print(f"{sensor_name} Odosielanie na pozadí spustené v samostatnom vlákne")
    print(f"\nCelkovo {len(sender_threads)} vlákno spustené:")
    for i, thread in enumerate(sender_threads):
        print(f"  {i + 1}. {thread.name} - Aktívny: {thread.is_alive()}")
    return stop_event, pause_events, resume_events, sender_threads

def main():
    global IP, PORT, TOKENS, BACKGROUND_STATE, SIMULATE_ERROR_SENSORS

    print("Enter server IP:")
    IP = input().strip()
    print("Enter server port:")
    try:
        PORT = int(input().strip())
    except:
        print("Invalid port")

    server_addr = (IP, PORT)

    while True:
        menu_choice = show_main_menu()

        if menu_choice not in ("1", "2", "3", "4","5"):
            print("Neplatná položka menu")
            continue

        if menu_choice == "5":
            print("Ukončenie")
            if BACKGROUND_STATE['active']:
                BACKGROUND_STATE['stop_event'].set()
                for thread in BACKGROUND_STATE['threads']:
                    thread.join(timeout=2.0)
            break

        if menu_choice == "4":
            have_any_token = any(bool(t) for t in TOKENS.values())
            if not have_any_token:
                print(
                    "Nie je možné použiť možnosť 4: server ešte neposkytol token. Najprv použite možnosť 1 alebo zaregistrujte senzory")
                continue
            sensor_choice = choose_sensor_menu()
            sel = choose_sensor(sensor_choice)
            if sel is None:
                print("Neplatná voľba senzora")
                continue
            sensor_name, _ = sel
            token_for_sensor = TOKENS.get(sensor_name, "")
            if not token_for_sensor:
                print(f"{sensor_name}: Žiadny token, zastavenie nie je možné (žiadne odosielanie dát)")
                continue
            if not BACKGROUND_STATE['active']:
                print(
                    "Pozadie odosielanie ešte nebeží — spúšťam automatické odosielanie pre senzory, ktoré majú token")

                active_sensors = []
                for sname, sfunc in SENSOR_FUNCS.values():
                    tok = TOKENS.get(sname, "")
                    if tok:
                        active_sensors.append((sname, sfunc, tok))
                        PAUSED_SENSORS[sname] = False
                    else:
                        print(f"Upozornenie: {sname} Nemá token, nebude odosielať dáta")

                if not active_sensors:
                    print("Žiadny senzor nemá token. Návrat do menu")
                    continue
                stop_event, pause_events, resume_events, threads = start_background_senders(server_addr, active_sensors)
                if sensor_name in pause_events:
                    pause_events[sensor_name].set()
                    PAUSED_SENSORS[sensor_name] = True
                    print(f"{sensor_name} Zastavené — ostatné senzory stále odosielajú údaje")
                else:
                    print(f"{sensor_name} Nie je nájdený medzi spustenými senzormi")

                BACKGROUND_STATE = {
                    'active': True,
                    'threads': threads,
                    'stop_event': stop_event,
                    'pause_events': pause_events,
                    'resume_events': resume_events,
                    'sensor_data': active_sensors
                }
                continue
            if sensor_name not in BACKGROUND_STATE['pause_events']:
                print(f"{sensor_name} Nie je nájdený medzi aktívnymi senzormi")
                continue

            print(f"{sensor_name} Zastavuje sa")
            BACKGROUND_STATE['pause_events'][sensor_name].set()
            PAUSED_SENSORS[sensor_name] = True
            print(f"{sensor_name} Zastavené. Ostatné senzory pokračujú v odosielaní údajov")
            continue

        if menu_choice == "2":
            sensor_choice = choose_sensor_menu()
            sel = choose_sensor(sensor_choice)
            if sel is None:
                print("Neplatná voľba senzora, návrat do menu")
                continue

            sensor_name, sensor_func = sel
            print(f"\n{sensor_name} Stav batérie:")
            low_battery = ask_battery_status()
            custom_payload = collect_structured_payload(sensor_name)

            if not custom_payload:
                print("Prázdny payload — návrat do hlavného menu")
                continue

            token = TOKENS.get(sensor_name, "")
            if not token:
                print("Nie je možné odoslať správu bez tokenu. Spusť možnosť 1 pre registráciu")
                continue
            battery_status = "nízke" if low_battery else "normalny"
            print(f"Odoslanie (jednorazové): senzor={sensor_name}, batéria={battery_status}, payload={custom_payload}")
            resp = send_one_data(server_addr, sensor_name, token, custom_payload, low_battery)

            if resp is None:
                print("Žiadna odpoveď zo servera na odoslanie")
            else:
                print("Odpoveď servera:", resp)
            continue

        if menu_choice == "1":
            if BACKGROUND_STATE['active']:
                print("Pozadie odosielanie už beží! Použi možnosť 4 na správu senzorov")
                continue

            print("\nRegistrovanie všetkých 4 senzorov")
            for key, (sensor_name, sensor_func) in SENSOR_FUNCS.items():
                resp = register_device(server_addr, sensor_name)
                token = ""
                if resp and verify_checksum_client(resp):
                    token = resp.get("token") or ""
                    if token:
                        TOKENS[sensor_name] = token
                        print(f"{sensor_name}: registrované Token: {token}")
                    else:
                        TOKENS[sensor_name] = ""
                        print(f"{sensor_name}: Registrácia zlyhala alebo sme nedostali token. Odpoveď: {resp}")
            print("Koniec registrácií. Všetky 4 senzory sa spúšťajú s automatickým odosielaním (ak dostali token)")
            active_sensors = []
            for sensor_name, sensor_func in SENSOR_FUNCS.values():
                token = TOKENS.get(sensor_name, "")
                if token:
                    active_sensors.append((sensor_name, sensor_func, token))
                    PAUSED_SENSORS[sensor_name] = False
                else:
                    print(f"Upozornenie: {sensor_name} Nezískal token, údaje neodosiela")

            if not active_sensors:
                print("Žiaden senzor nemá token. Späť do menu")
                continue
            print(f"\nSpustenie pozadia odosielania dát {len(active_sensors)} so senzorom:")
            for sensor_name, _, token in active_sensors:
                print(f" - {sensor_name}: {token}")
            print("\nPozadie odosielania sa spustilo. Môžeš sa vrátiť do menu")
            stop_event, pause_events, resume_events, sender_threads = start_background_senders(server_addr,active_sensors)

            BACKGROUND_STATE = {
                'active': True,
                'threads': sender_threads,
                'stop_event': stop_event,
                'pause_events': pause_events,
                'resume_events': resume_events,
                'sensor_data': active_sensors
            }

            continue

        if menu_choice == "3":
            sensor_choice = choose_sensor_menu()
            sel = choose_sensor(sensor_choice)
            if sel is None:
                print("Neplatná voľba senzora, návrat do menu")
                continue

            sensor_name, sensor_func = sel
            token = TOKENS.get(sensor_name, "")

            if not token:
                print(f"{sensor_name}: Nie je token. Spusti možnosť 1 na registráciu")
                continue
            else:
                print(f"{sensor_name} Token je už použitý: {token}")

            if not BACKGROUND_STATE['active']:
                print("\nPozadie odosielanie ešte nebeží — spúšťam automatické odosielanie pre senzory, ktoré majú token")

                active_sensors = []
                for sname, sfunc in SENSOR_FUNCS.values():
                    tok = TOKENS.get(sname, "")
                    if tok:
                        active_sensors.append((sname, sfunc, tok))
                        PAUSED_SENSORS[sname] = False
                    else:
                        print(f"Upozornenie: {sname} Nemá token, nebude odosielať dáta")

                if not active_sensors:
                    print("Žiadny senzor nemá token. Návrat do menu")
                    continue

                stop_event, pause_events, resume_events, threads = start_background_senders(server_addr, active_sensors)

                BACKGROUND_STATE = {
                    'active': True,
                    'threads': threads,
                    'stop_event': stop_event,
                    'pause_events': pause_events,
                    'resume_events': resume_events,
                    'sensor_data': active_sensors
                }

            SIMULATE_ERROR_SENSORS[sensor_name] = True
            print(f"{sensor_name}: Hibaszimuláció beállítva — a következő autosend körben csak a hibás üzenetet küldi; ha server checksum_error-t küld, azonnal visszaküldjük a helyes üzenetet.")
            time.sleep(0.1)
            print("Návrat do menu")
            continue

        print("Neplatná položka menu alebo zvolená možnosť nie je implementovaná")
        continue
    print("Koniec programu")

if __name__ == "__main__":
    main()

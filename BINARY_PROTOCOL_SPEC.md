# Binary Protocol Specification

## Message Types (2 bits)
- 0x0 (00): REGISTER
- 0x1 (01): REGISTER_ACK
- 0x2 (10): DATA
- 0x3 (11): CONTROL (ping/pong/ack/error)

## Device Types (2 bits)
- 0x0 (00): ThermoNode
- 0x1 (01): WindSense
- 0x2 (10): RainDetect
- 0x3 (11): AirQualityBox

## Control Subtypes (2 bits, used when msg_type=CONTROL)
- 0x0 (00): DATA_ACK
- 0x1 (01): PING
- 0x2 (10): PONG
- 0x3 (11): ERROR

## Common Header (5 bytes)
```
Byte 0: [msg_type:2 | device_type:2 | subtype/flags:4]
Bytes 1-4: timestamp (32-bit unsigned int, big-endian)
```

## Message Structures

### REGISTER (5 bytes)
- Header only

### REGISTER_ACK (9 bytes)
- Header (5 bytes)
- Token (4 bytes, unsigned int)

### DATA (variable)
- Header (5 bytes), battery_low flag in bit 0 of flags field
- Token (4 bytes)
- Device-specific payload (varies by device)
- CRC32 (4 bytes) - calculated over entire message except CRC field

### CONTROL Messages (variable)
- Header (5 bytes) with subtype in flags field
- Token (4 bytes) for pong/data_ack
- Error code (1 byte) for ERROR subtype

## Device-Specific Data Encoding

### ThermoNode (8 bytes)
- temperature: int16 (value * 10), range -500 to 600 (-50.0°C to 60.0°C)
- humidity: uint16 (value * 10), range 0 to 1000 (0.0% to 100.0%)
- dew_point: int16 (value * 10), range -500 to 600
- pressure: uint16 (value * 100 - 80000), range 0 to 30000 (800.00 to 1100.00 hPa)

### WindSense (7 bytes)
- wind_speed: uint16 (value * 10), range 0 to 500 (0.0 to 50.0 m/s)
- wind_gust: uint16 (value * 10), range 0 to 700 (0.0 to 70.0 m/s)
- wind_direction: uint16, range 0 to 359
- turbulence: uint8 (value * 10), range 0 to 10 (0.0 to 1.0)

### RainDetect (7 bytes)
- rainfall: uint16 (value * 10), range 0 to 5000 (0.0 to 500.0 mm)
- soil_moisture: uint16 (value * 10), range 0 to 1000 (0.0% to 100.0%)
- flood_risk: uint8, range 0 to 3
- rain_duration: uint16, range 0 to 60 (minutes)

### AirQualityBox (6 bytes)
- co2: uint16, range 300 to 5000 (ppm)
- ozone: uint16 (value * 10), range 0 to 5000 (0.0 to 500.0 µg/m³)
- air_quality_index: uint16, range 0 to 500

## Error Codes (1 byte)
- 0x01: INVALID_TOKEN
- 0x02: CRC_FAIL
- 0x03: INVALID_DATA

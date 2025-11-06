# FIITMeteo Binary Protocol Documentation

## Overview

The FIITMeteo Binary Protocol is an optimized UDP-based communication protocol for IoT weather sensors. It replaces the original JSON-based protocol with a compact binary format that significantly reduces message size and bandwidth usage.

## Protocol Comparison

### JSON vs Binary Protocol Size Comparison

| Message Type | JSON Size | Binary Size | Savings |
|--------------|-----------|-------------|---------|
| REGISTER | ~80 bytes | 9 bytes | 88.8% |
| REGISTER_ACK | ~95 bytes | 11 bytes | 88.4% |
| DATA (ThermoNode) | ~250 bytes | 19 bytes | 92.4% |
| DATA_ACK | ~75 bytes | 10 bytes | 86.7% |
| ERROR | ~110 bytes | 11 bytes | 90.0% |
| PING | ~80 bytes | 9 bytes | 88.8% |
| PONG | ~95 bytes | 11 bytes | 88.4% |

**Average bandwidth reduction: ~90%**

## Binary Protocol Specification

### Header Format (1 byte)

```
Bit Layout:
+---+---+---+---+---+---+---+---+
| 7 | 6 | 5 | 4 | 3 | 2 | 1 | 0 |
+---+---+---+---+---+---+---+---+
|Rsv|Rsv|Bat|DevTyp |  MsgType  |
+---+---+---+---+---+---+---+---+
```

- **Bits 0-2**: Message Type (3 bits)
  - `000` (0) = REGISTER
  - `001` (1) = REGISTER_ACK
  - `010` (2) = DATA
  - `011` (3) = DATA_ACK
  - `100` (4) = ERROR
  - `101` (5) = PING
  - `110` (6) = PONG
  - `111` (7) = Reserved

- **Bits 3-4**: Device Type (2 bits)
  - `00` (0) = ThermoNode
  - `01` (1) = WindSense
  - `10` (2) = RainDetect
  - `11` (3) = AirQualityBox

- **Bit 5**: Battery Low Flag
  - `0` = Battery OK
  - `1` = Battery Low

- **Bits 6-7**: Reserved for future use

### Common Fields

- **Timestamp**: 4 bytes (32-bit unsigned integer, Unix epoch)
- **Token**: 2 bytes (16-bit unsigned integer, 0-65535)
- **CRC32**: 4 bytes (32-bit unsigned integer, always at message end)

## Message Formats

### 1. REGISTER (9 bytes)

Sent by device to register with server.

```
+--------+------------+-------+
| Header | Timestamp  | CRC32 |
|   1B   |     4B     |   4B  |
+--------+------------+-------+
```

**Example**:
```
00 67 45 23 01 A1 B2 C3 D4
```

### 2. REGISTER_ACK (11 bytes)

Sent by server to confirm registration and provide token.

```
+--------+------------+-------+-------+
| Header | Timestamp  | Token | CRC32 |
|   1B   |     4B     |   2B  |   4B  |
+--------+------------+-------+-------+
```

**Example**:
```
01 67 45 23 01 12 34 A1 B2 C3 D4
```

### 3. DATA (Variable length)

Sent by device with sensor measurements.

```
+--------+------------+-------+---------+-------+
| Header | Timestamp  | Token | Payload | CRC32 |
|   1B   |     4B     |   2B  | varies  |   4B  |
+--------+------------+-------+---------+-------+
```

**Payload sizes**:
- ThermoNode: 8 bytes
- WindSense: 7 bytes
- RainDetect: 7 bytes
- AirQualityBox: 6 bytes

### 4. DATA_ACK (10 bytes)

Sent by server to acknowledge data receipt.

```
+--------+------------+--------+-------+
| Header | Timestamp  | Status | CRC32 |
|   1B   |     4B     |   1B   |   4B  |
+--------+------------+--------+-------+
```

**Status values**:
- `0x00` = FAIL
- `0x01` = OK

### 5. ERROR (11 bytes)

Sent by server to indicate an error condition.

```
+--------+------------+------------+--------------+-------+
| Header | Timestamp  | Error Code | Request Code | CRC32 |
|   1B   |     4B     |     1B     |      1B      |   4B  |
+--------+------------+------------+--------------+-------+
```

**Error Codes**:
- `0x00` = INVALID_TOKEN
- `0x01` = CRC_FAIL

**Request Codes**:
- `0x00` = NONE
- `0x01` = RESEND_LAST

### 6. PING (9 bytes)

Sent by server to check device connectivity.

```
+--------+------------+-------+
| Header | Timestamp  | CRC32 |
|   1B   |     4B     |   4B  |
+--------+------------+-------+
```

### 7. PONG (11 bytes)

Sent by device in response to PING.

```
+--------+------------+-------+-------+
| Header | Timestamp  | Token | CRC32 |
|   1B   |     4B     |   2B  |   4B  |
+--------+------------+-------+-------+
```

## Device-Specific Data Payloads

### ThermoNode (8 bytes)

```
+-------------+-----------+-----------+----------+
| Temperature | Humidity  | Dew Point | Pressure |
|     2B      |    2B     |     2B    |    2B    |
+-------------+-----------+-----------+----------+
```

**Field Encodings**:
- **Temperature**: signed 16-bit (value × 10)
  - Range: -50.0°C to 60.0°C
  - Precision: 0.1°C
  - Example: 25.3°C → 253 (0x00FD)

- **Humidity**: unsigned 16-bit (value × 10)
  - Range: 0.0% to 100.0%
  - Precision: 0.1%
  - Example: 65.7% → 657 (0x0291)

- **Dew Point**: signed 16-bit (value × 10)
  - Range: -50.0°C to 60.0°C
  - Precision: 0.1°C

- **Pressure**: unsigned 16-bit (value × 100)
  - Range: 800.0 hPa to 1100.0 hPa
  - Precision: 0.01 hPa
  - Example: 1013.25 hPa → 101325 → stored as offset from 800.00

### WindSense (7 bytes)

```
+------------+-----------+-----------+-----------+
| Wind Speed | Wind Gust | Direction | Turbulence|
|     2B     |    2B     |     2B    |     1B    |
+------------+-----------+-----------+-----------+
```

**Field Encodings**:
- **Wind Speed**: unsigned 16-bit (value × 10)
  - Range: 0.0 m/s to 50.0 m/s
  - Precision: 0.1 m/s

- **Wind Gust**: unsigned 16-bit (value × 10)
  - Range: 0.0 m/s to 70.0 m/s
  - Precision: 0.1 m/s

- **Wind Direction**: unsigned 16-bit
  - Range: 0° to 359°
  - Precision: 1°

- **Turbulence**: unsigned 8-bit (value × 10)
  - Range: 0.0 to 1.0
  - Precision: 0.1

### RainDetect (7 bytes)

```
+----------+---------------+------------+---------------+
| Rainfall | Soil Moisture | Flood Risk | Rain Duration |
|    2B    |      2B       |     1B     |      2B       |
+----------+---------------+------------+---------------+
```

**Field Encodings**:
- **Rainfall**: unsigned 16-bit (value × 10)
  - Range: 0.0 mm to 500.0 mm
  - Precision: 0.1 mm

- **Soil Moisture**: unsigned 16-bit (value × 10)
  - Range: 0.0% to 100.0%
  - Precision: 0.1%

- **Flood Risk**: unsigned 8-bit
  - Range: 0 to 3
  - Values: 0=None, 1=Low, 2=Medium, 3=High

- **Rain Duration**: unsigned 16-bit
  - Range: 0 to 60 minutes
  - Precision: 1 minute

### AirQualityBox (6 bytes)

```
+------+-------+-------------------+
| CO2  | Ozone | Air Quality Index |
|  2B  |  2B   |        2B         |
+------+-------+-------------------+
```

**Field Encodings**:
- **CO2**: unsigned 16-bit
  - Range: 300 ppm to 5000 ppm
  - Precision: 1 ppm

- **Ozone**: unsigned 16-bit (value × 10)
  - Range: 0.0 µg/m³ to 500.0 µg/m³
  - Precision: 0.1 µg/m³

- **Air Quality Index**: unsigned 16-bit
  - Range: 0 to 500
  - Precision: 1

## CRC32 Calculation

The protocol uses the standard IEEE 802.3 CRC32 polynomial: 0xEDB88320

**Calculation Process**:
1. Calculate CRC32 over all bytes from header to last payload byte
2. Append the 4-byte CRC32 value in network byte order (big-endian)
3. Receiver recalculates CRC32 on received data (excluding CRC field)
4. If CRC mismatch, send ERROR message with CRC_FAIL code

## Byte Order

All multi-byte fields use **network byte order (big-endian)**:
- 16-bit values: MSB first
- 32-bit values: MSB first

Example: Value 0x1234 is transmitted as `[0x12, 0x34]`

## Usage Examples

### Example 1: ThermoNode Registration

**Device sends REGISTER**:
```
Hex: 00 67 45 23 01 A1 B2 C3 D4
     ^^ Header (msg_type=0, device_type=0)
        ^^^^^^^^^^^ Timestamp
                    ^^^^^^^^^^^ CRC32
```

**Server responds with REGISTER_ACK**:
```
Hex: 01 67 45 23 05 12 34 E5 F6 A7 B8
     ^^ Header
        ^^^^^^^^^^^ Timestamp
                    ^^^^^ Token (0x1234 = 4660)
                          ^^^^^^^^^^^ CRC32
```

### Example 2: ThermoNode Sending Data

**Device sends DATA** (temp=25.3°C, humidity=65.7%, dew=15.2°C, pressure=1013.25 hPa):
```
Hex: 02 67 45 23 09 12 34 00 FD 02 91 00 98 27 65 C1 D2 E3 F4
     ^^ Header (msg_type=2, device_type=0, battery=0)
        ^^^^^^^^^^^ Timestamp
                    ^^^^^ Token
                          ^^^^^ Temperature (253 = 25.3°C)
                                ^^^^^ Humidity (657 = 65.7%)
                                      ^^^^^ Dew Point (152 = 15.2°C)
                                            ^^^^^ Pressure (10065 = 1013.25 hPa offset)
                                                  ^^^^^^^^^^^ CRC32
Total: 19 bytes (vs ~250 bytes in JSON)
```

**Server responds with DATA_ACK**:
```
Hex: 03 67 45 23 0D 01 F1 E2 D3 C4
     ^^ Header
        ^^^^^^^^^^^ Timestamp
                    ^^ Status (0x01 = OK)
                       ^^^^^^^^^^^ CRC32
```

## Wireshark Dissector Usage

### Installation

1. Copy `fiitmeteo.lua` to Wireshark plugins directory:
   - **Windows**: `%APPDATA%\Wireshark\plugins\`
   - **Linux**: `~/.local/lib/wireshark/plugins/`
   - **macOS**: `~/.config/wireshark/plugins/`

2. Restart Wireshark

### Capturing FIITMeteo Traffic

1. Start capture on loopback interface (lo or lo0)
2. Filter: `udp.port == 9999` or `fiitmeteo`
3. The dissector will automatically decode all fields

### Dissector Features

- Automatic protocol detection on UDP port 9999
- Color-coded message types
- Expandable field tree
- CRC validation with status indication
- Device-specific data field parsing
- Human-readable value display with units
- Info column shows message summary

## Implementation Files

### protocol.py

Core binary protocol implementation with encoding/decoding functions:
- `encode_register()`, `decode_register()`
- `encode_register_ack()`, `decode_register_ack()`
- `encode_data()`, `decode_data()`
- `encode_data_ack()`, `decode_data_ack()`
- `encode_error()`, `decode_error()`
- `encode_ping()`, `decode_ping()`
- `encode_pong()`, `decode_pong()`
- `decode_message()` - automatic message type detection

### server.py

UDP server implementation:
- Handles device registration
- Processes sensor data
- Sends acknowledgments
- Detects disconnections and sends pings
- Validates CRC and requests retransmission on errors

### tester.py

Device simulator for testing:
- Simulates 4 sensor types
- Automatic data generation every 10 seconds
- Manual message sending
- CRC error injection (UAT3)
- Disconnection simulation (UAT4)
- ACK timeout handling (UAT5)

### fiitmeteo.lua

Wireshark dissector:
- Parses all message types
- Displays all fields with proper formatting
- Validates CRC32
- Shows device-specific sensor data

## Testing

### Basic Test Flow

1. Start server: `python server.py`
   - Select option 2 to start server

2. Start tester: `python tester.py`
   - Select option 2 to start automatic generation

3. Verify output:
   - Server should show 4 devices registered
   - Data should be received every 10 seconds

4. Test with Wireshark:
   - Start capture on loopback interface
   - Filter: `fiitmeteo`
   - Observe decoded messages

### UAT Tests

- **UAT2**: Manual message sending (option 4)
- **UAT3**: CRC error injection and recovery (option 5)
- **UAT4**: Disconnection and reconnection (option 6)
- **UAT5**: ACK timeout and retransmission (automatic)

## Advantages of Binary Protocol

1. **Size Efficiency**: 90% reduction in message size
2. **Bandwidth Savings**: Significant reduction in network usage
3. **Parsing Speed**: Faster than JSON parsing
4. **Type Safety**: Fixed-size fields prevent parsing errors
5. **Validation**: Built-in CRC32 ensures data integrity
6. **Scalability**: Compact format suitable for IoT devices
7. **Battery Life**: Reduced transmission time saves power

## Future Enhancements

Possible protocol extensions using reserved bits:
- Message priority flags
- Compression indicators
- Security/encryption flags
- Protocol version negotiation
- Extended device types (currently limited to 4)
- Extended message types (currently using 7 of 8)

## Conclusion

The FIITMeteo Binary Protocol provides a highly optimized, reliable, and efficient communication method for IoT weather sensors. With 90% bandwidth reduction compared to JSON, built-in error detection, and comprehensive Wireshark support, it meets all requirements for a production-ready IoT protocol.

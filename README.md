# FIITMeteo - Optimized Binary UDP Protocol

**Course Assignment**: PKS-B Curse Assignment - Optimized Protocol Implementation

## Overview

FIITMeteo is an optimized binary UDP protocol for IoT weather sensors. This implementation replaces verbose JSON encoding with a compact binary format, achieving **87-92% bandwidth reduction** while maintaining full functionality.

## Key Features

- ✅ **Highly Optimized**: 87-92% smaller messages than JSON
- ✅ **Efficient Encoding**: Uses minimal bits for each parameter (2 bits for device type, 3 bits for message type)
- ✅ **Data Integrity**: Built-in CRC32 validation
- ✅ **Wireshark Support**: Full protocol dissector in Lua
- ✅ **Fixed-Point Arithmetic**: Optimal precision for each sensor parameter
- ✅ **Four Device Types**: ThermoNode, WindSense, RainDetect, AirQualityBox

## Files

| File | Description |
|------|-------------|
| `protocol.py` | Binary protocol encoder/decoder module |
| `server.py` | UDP server implementation |
| `tester.py` | Multi-device simulator and testing tool |
| `fiitmeteo.lua` | Wireshark dissector |
| `test_protocol.py` | Unit tests and protocol validation |
| `PROTOCOL_DOCUMENTATION.md` | Complete protocol specification |

## Quick Start

### 1. Run Unit Tests

```bash
python3 test_protocol.py
```

Expected output:
```
ALL TESTS PASSED! ✓

MESSAGE SIZE COMPARISON (JSON vs Binary)
REGISTER:      JSON=115 bytes  Binary= 9 bytes  Savings=92.2%
DATA:          JSON=216 bytes  Binary=19 bytes  Savings=91.2%
PING:          JSON= 69 bytes  Binary= 9 bytes  Savings=87.0%
```

### 2. Start Server

```bash
python3 server.py
```

Menu:
1. Configure IP and port (default: 127.0.0.1:9999)
2. Start server
3. Exit

### 3. Start Tester (Client Simulator)

```bash
python3 tester.py
```

Menu options:
1. Configure server IP/port
2. **Start automatic generation** (registers 4 sensors, sends data every 10s)
3. Stop automatic generation
4. Send manual message (UAT2)
5. Inject CRC error (UAT3)
6. Simulate disconnection (UAT4)
7. Exit

### 4. Monitor with Wireshark

1. Copy `fiitmeteo.lua` to Wireshark plugins directory:
   - **Linux**: `~/.local/lib/wireshark/plugins/`
   - **Windows**: `%APPDATA%\Wireshark\plugins\`
   - **macOS**: `~/.config/wireshark/plugins/`

2. Restart Wireshark

3. Capture on loopback interface (lo)

4. Filter: `fiitmeteo` or `udp.port == 9999`

## Protocol Highlights

### Message Types (3 bits)
- REGISTER (0)
- REGISTER_ACK (1)
- DATA (2)
- DATA_ACK (3)
- ERROR (4)
- PING (5)
- PONG (6)

### Device Types (2 bits)
- ThermoNode (0) - Temperature, humidity, dew point, pressure
- WindSense (1) - Wind speed, gust, direction, turbulence
- RainDetect (2) - Rainfall, soil moisture, flood risk, duration
- AirQualityBox (3) - CO2, ozone, air quality index

### Size Examples

| Message | Binary Size | JSON Size | Savings |
|---------|-------------|-----------|---------|
| REGISTER | 9 bytes | 115 bytes | 92.2% |
| REGISTER_ACK | 11 bytes | - | - |
| DATA (ThermoNode) | 19 bytes | 216 bytes | 91.2% |
| DATA_ACK | 10 bytes | 75 bytes | 86.7% |
| ERROR | 11 bytes | 110 bytes | 90.0% |
| PING | 9 bytes | 69 bytes | 87.0% |
| PONG | 11 bytes | - | - |

## Efficient Parameter Encoding

### ThermoNode Example (8 bytes payload)

```
Temperature:  -50.0 to  60.0°C  (0.1°C precision)  → signed 16-bit   (×10)
Humidity:      0.0 to 100.0%    (0.1% precision)   → unsigned 16-bit (×10)
Dew Point:   -50.0 to  60.0°C  (0.1°C precision)  → signed 16-bit   (×10)
Pressure:    800.0 to 1100.0hPa (0.01hPa precision) → unsigned 16-bit (×100, offset from 800)
```

**Example encoding**:
- Temperature: 25.3°C → 253 → `0x00FD`
- Humidity: 65.7% → 657 → `0x0291`
- Pressure: 1013.25 hPa → (1013.25 - 800.0) × 100 = 21325 → `0x534D`

## Testing Scenarios

### UAT2: Manual Message Sending
1. Start server and tester
2. Choose option 4 in tester
3. Select sensor and enter custom values
4. Observe on server console

### UAT3: CRC Error Detection & Recovery
1. Choose option 5 in tester
2. Select sensor
3. Next automatic message will have corrupted CRC
4. Server detects error and requests retransmission
5. Tester resends clean data

### UAT4: Disconnection & Reconnection
1. Choose option 6 in tester
2. Select sensor
3. Sensor stops responding to first 2 pings
4. Responds to 3rd ping with PONG
5. Server marks as reconnected

### UAT5: ACK Timeout & Retransmission
1. Server command: type `uat5` and press Enter
2. Select sensor to ignore ACKs for
3. Server ignores first 3 data messages (no ACK sent)
4. Tester retransmits data after 1 second timeout
5. After 3rd retry, server sends ACK

## Protocol Advantages

1. **Bandwidth Efficiency**: ~90% reduction vs JSON
2. **Parsing Speed**: Binary parsing faster than JSON
3. **Type Safety**: Fixed-size fields prevent errors
4. **Error Detection**: CRC32 validates every message
5. **Low Power**: Reduced transmission time saves battery
6. **Scalability**: Compact format suitable for IoT
7. **Wireshark Support**: Easy debugging and analysis

## Implementation Details

### Header (1 byte)
```
Bits 0-2: Message Type (3 bits)
Bits 3-4: Device Type (2 bits)
Bit 5:    Battery Low Flag
Bits 6-7: Reserved
```

### Common Fields
- Timestamp: 32-bit Unix epoch
- Token: 16-bit session identifier
- CRC32: 32-bit checksum (IEEE 802.3 polynomial)

### Byte Order
All multi-byte fields use **network byte order (big-endian)**.

## Requirements

- Python 3.7+
- Standard library only (no external dependencies)
- Wireshark 3.0+ (for dissector)

## Documentation

See `PROTOCOL_DOCUMENTATION.md` for complete protocol specification including:
- Detailed message formats
- Field encodings for all device types
- CRC calculation algorithm
- Wireshark dissector usage
- Binary format examples

## Test Results

```
Testing REGISTER message...        ✓ PASS
Testing REGISTER_ACK message...    ✓ PASS
Testing DATA (ThermoNode)...       ✓ PASS (19 bytes vs ~250 JSON)
Testing DATA (WindSense)...        ✓ PASS
Testing DATA (RainDetect)...       ✓ PASS
Testing DATA (AirQualityBox)...    ✓ PASS
Testing DATA_ACK message...        ✓ PASS
Testing ERROR message...           ✓ PASS
Testing PING message...            ✓ PASS
Testing PONG message...            ✓ PASS
Testing CRC error detection...     ✓ PASS
Testing battery flag...            ✓ PASS
Testing auto message detection...  ✓ PASS
```

## Author

Created for PKS-B course assignment - Binary Protocol Optimization

## License

Educational use only

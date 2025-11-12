# FIITMeteo - Binary Protocol Weather Monitoring System

## Quick Start

### Running the Binary Protocol Implementation

1. **Start the Server:**
```bash
python3 server_binary.py
```
Select option 2 to start the server on default port 9999.

2. **Start the Tester (in another terminal):**
```bash
python3 tester_binary.py
```
Select option 2 to connect and start automatic data generation.

### Testing UAT Scenarios

#### UAT1: Basic Registration and Data Flow
- Automatically tested when you start the tester (option 2)
- All 4 sensors register and begin sending data every 10 seconds

#### UAT2: Manual Data with Battery Warning
- Start tester and ensure sensors are running
- Select option 4 (Send custom message)
- Choose a sensor
- Answer 'a' (áno) when asked about low battery
- Enter sensor values
- Check server output for "WARNING: LOW BATTERY" message

#### UAT3: CRC Error Detection
- Start tester with sensors running
- Select option 5 (Introduce error)
- Choose a sensor
- Wait for automatic data send (max 10 seconds)
- Server will detect CRC error and request resend
- Client automatically resends clean data

#### UAT4: Disconnect and Reconnection
- Start tester with sensors running
- Select option 6 (Simulate disconnect)
- Choose a sensor
- Server will detect timeout after 15s and send PINGs
- Client ignores first 2 PINGs, responds to 3rd
- Server detects reconnection

#### UAT5: ACK Timeout and Retransmission
- Start server
- Type 'uat5' and press Enter
- Choose a sensor from the list
- Server will ignore first 3 ACKs
- Client will automatically retransmit
- On 4th attempt, server sends ACK

## Files

### Implementation
- `server_binary.py` - Binary protocol server
- `tester_binary.py` - Binary protocol test client
- `server.py` - Original JSON protocol server (for comparison)
- `tester.py` - Original JSON protocol tester (for comparison)

### Analysis & Documentation
- `BINARY_PROTOCOL_SPEC.md` - Binary protocol specification
- `DOCUMENTATION.md` - Complete project documentation
- `protocol_comparison.py` - Protocol efficiency comparison tool
- `fiitmeteo.lua` - Wireshark dissector

### Usage
- `README.md` - This file

## Protocol Comparison

Run the comparison tool to see efficiency metrics:
```bash
python3 protocol_comparison.py
```

Export to CSV for charting:
```bash
python3 protocol_comparison.py --export > comparison.csv
```

## Wireshark Dissector Installation

1. Copy `fiitmeteo.lua` to Wireshark plugins folder:
   - **Windows**: `%APPDATA%\Wireshark\plugins\`
   - **Linux**: `~/.local/lib/wireshark/plugins/`
   - **macOS**: `~/.config/wireshark/plugins/`

2. Restart Wireshark

3. Capture on loopback interface (lo0 or Loopback)

4. Filter: `udp.port == 9999`

## Key Features

### Binary Protocol Benefits
- **90.7% smaller** than JSON (application layer)
- **75.6% smaller** including network overhead
- **87.6% smaller** than MQTT (estimated)

### Supported Sensors
- **ThermoNode**: Temperature, Humidity, Dew Point, Pressure
- **WindSense**: Wind Speed, Gust, Direction, Turbulence
- **RainDetect**: Rainfall, Soil Moisture, Flood Risk, Duration
- **AirQualityBox**: CO2, Ozone, Air Quality Index

### Reliability Features
- CRC32 error detection
- Automatic retransmission
- Disconnect detection with PING/PONG
- ACK timeout handling

## Architecture

### Message Types (2 bits)
- 0x0: REGISTER
- 0x1: REGISTER_ACK
- 0x2: DATA
- 0x3: CONTROL (PING/PONG/ACK/ERROR)

### Device Types (2 bits)
- 0x0: ThermoNode
- 0x1: WindSense
- 0x2: RainDetect
- 0x3: AirQualityBox

### Message Sizes
- REGISTER: 5 bytes
- REGISTER_ACK: 9 bytes
- DATA: 19-21 bytes (device-dependent)
- PING/PONG/ACK: 5-9 bytes
- ERROR: 6 bytes

Compare with JSON (200-220 bytes per DATA message)!

## Technical Details

- **Language**: Python 3.7+
- **Transport**: UDP
- **Port**: 9999 (configurable)
- **Byte Order**: Big-endian (network order)
- **Error Detection**: CRC32
- **Concurrency**: asyncio

## Performance

### 10-Minute Operation (4 sensors, 10s interval)
- **JSON**: 61.00 KB total
- **Binary**: 14.91 KB total
- **Savings**: 46.09 KB (75.6%)

### 24-Hour Operation
- **JSON**: ~8.8 MB
- **Binary**: ~2.1 MB
- **Savings**: ~6.7 MB (75.7%)

### 1-Month Operation
- **JSON**: ~264 MB
- **Binary**: ~64 MB
- **Savings**: ~200 MB (75.7%)

## Troubleshooting

### Server won't start
- Check if port 9999 is already in use: `netstat -an | grep 9999`
- Change port in configuration

### Clients won't connect
- Ensure server is running
- Check firewall settings
- Verify IP address and port

### Wireshark doesn't show FIITMeteo protocol
- Verify .lua file is in plugins folder
- Restart Wireshark
- Check that traffic is on UDP port 9999

## License

Educational project for FIIT STU.

## Author

xmiklosz - 2025

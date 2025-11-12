# FIITMeteo Weather Monitoring System
## Binary Protocol Implementation - Final Documentation

**Student:** xmiklosz
**Date:** 2025-11-12
**Project:** UDP-Based Weather Monitoring System with Binary Protocol Optimization

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Protocol Design](#2-protocol-design)
3. [JSON Protocol (Initial Implementation)](#3-json-protocol-initial-implementation)
4. [Binary Protocol (Optimized Implementation)](#4-binary-protocol-optimized-implementation)
5. [Program Flowcharts](#5-program-flowcharts)
6. [Sequence Diagrams](#6-sequence-diagrams)
7. [Libraries Used](#7-libraries-used)
8. [Encapsulation Example](#8-encapsulation-example)
9. [Efficiency Measurements](#9-efficiency-measurements)
10. [Wireshark Dissector](#10-wireshark-dissector)
11. [Appendix A: Educational Evaluation](#appendix-a-educational-evaluation)

---

## 1. Introduction

The FIITMeteo system is a UDP-based weather monitoring system that collects data from multiple sensor devices and aggregates it on a central server. This project implements two versions of the communication protocol:

1. **JSON Protocol** - Human-readable text-based protocol (initial implementation)
2. **Binary Protocol** - Highly optimized binary protocol (final implementation)

### Supported Devices

- **ThermoNode**: Temperature, humidity, dew point, and pressure sensor
- **WindSense**: Wind speed, gust, direction, and turbulence sensor
- **RainDetect**: Rainfall, soil moisture, flood risk, and duration sensor
- **AirQualityBox**: CO2, ozone, and air quality index sensor

---

## 2. Protocol Design

### 2.1 Design Goals

- **Efficiency**: Minimize bandwidth usage
- **Reliability**: CRC32 error detection
- **Scalability**: Support multiple device types
- **Robustness**: Handle disconnections and packet loss

### 2.2 Communication Model

- **Transport**: UDP (connectionless)
- **Port**: 9999 (default)
- **Pattern**: Client-server with periodic updates
- **Reliability**: Application-layer acknowledgments and retransmissions

---

## 3. JSON Protocol (Initial Implementation)

### 3.1 Message Types

#### REGISTER
Device registers with server to obtain authentication token.

```json
{
  "type": "register",
  "device_type": "ThermoNode",
  "timestamp": 1699876543
}
```

#### REGISTER_ACK
Server responds with authentication token.

```json
{
  "type": "register_ack",
  "device_type": "ThermoNode",
  "timestamp": 1699876543,
  "token": "T-87654"
}
```

#### DATA
Device sends sensor measurements.

```json
{
  "type": "data",
  "device_type": "ThermoNode",
  "timestamp": 1699876543,
  "battery_low": false,
  "token": "T-87654",
  "data": {
    "temperature": 25.5,
    "humidity": 65.3,
    "dew_point": 15.2,
    "pressure": 1013.25
  },
  "crc": "A3B5C7D9"
}
```

#### DATA_ACK
Server acknowledges data receipt.

```json
{
  "type": "data_ack",
  "device_type": "ThermoNode",
  "timestamp": 1699876543,
  "status": "OK"
}
```

#### PING
Server checks if device is still alive.

```json
{
  "type": "ping",
  "device_type": "ThermoNode",
  "timestamp": 1699876543
}
```

#### PONG
Device responds to keep-alive check.

```json
{
  "type": "pong",
  "device_type": "ThermoNode",
  "timestamp": 1699876543,
  "token": "T-87654"
}
```

#### ERROR
Server reports error condition.

```json
{
  "type": "error",
  "device_type": "ThermoNode",
  "timestamp": 1699876543,
  "error": "CRC_FAIL",
  "request": "resend_last"
}
```

### 3.2 JSON Protocol Characteristics

- **Average DATA message size**: 200-220 bytes
- **Human-readable**: Easy debugging
- **Overhead**: JSON structure, field names, quotes
- **CRC**: 8-character hexadecimal string (32 bits)

---

## 4. Binary Protocol (Optimized Implementation)

### 4.1 Protocol Constants

#### Message Types (2 bits)
```
0x0 (00): REGISTER
0x1 (01): REGISTER_ACK
0x2 (10): DATA
0x3 (11): CONTROL (ping/pong/ack/error)
```

#### Device Types (2 bits)
```
0x0 (00): ThermoNode
0x1 (01): WindSense
0x2 (10): RainDetect
0x3 (11): AirQualityBox
```

#### Control Subtypes (4 bits in flags field)
```
0x0 (0000): DATA_ACK
0x1 (0001): PING
0x2 (0010): PONG
0x3 (0011): ERROR
```

#### Error Codes (8 bits)
```
0x01: INVALID_TOKEN
0x02: CRC_FAIL
0x03: INVALID_DATA
```

### 4.2 Binary Message Structures

#### Common Header (5 bytes)
```
Byte 0: [msg_type:2 | device_type:2 | flags:4]
Bytes 1-4: timestamp (32-bit unsigned, big-endian)
```

#### REGISTER (5 bytes)
```
+--------+--------+--------+--------+--------+
| Header | Timestamp (32-bit)              |
| 1 byte | 4 bytes                         |
+--------+--------+--------+--------+--------+
```

#### REGISTER_ACK (9 bytes)
```
+--------+--------+--------+--------+--------+--------+--------+--------+--------+
| Header | Timestamp (32-bit)              | Token (32-bit)                  |
+--------+--------+--------+--------+--------+--------+--------+--------+--------+
```

#### DATA (variable length)
```
+--------+--------+--------+--------+--------+--------+--------+...+--------+--------+--------+--------+
| Header | Timestamp (32-bit)              | Token  | Payload (device-specific) | CRC32           |
| 1 byte | 4 bytes                         | 4 bytes| varies                    | 4 bytes         |
+--------+--------+--------+--------+--------+--------+--------+...+--------+--------+--------+--------+

Flags field bit 0: battery_low (1=low, 0=normal)
```

#### CONTROL Messages (5-9 bytes)
```
DATA_ACK (5 bytes): Header only (flags=0x0)
PING (5 bytes):     Header only (flags=0x1)
PONG (9 bytes):     Header + Token (flags=0x2)
ERROR (6 bytes):    Header + Error Code 1 byte (flags=0x3)
```

### 4.3 Device-Specific Data Encoding

#### ThermoNode (8 bytes payload)
```
+--------+--------+--------+--------+--------+--------+--------+--------+
| Temperature     | Humidity        | Dew Point       | Pressure        |
| int16 (*10)     | uint16 (*10)    | int16 (*10)     | uint16 (*100-   |
| 2 bytes         | 2 bytes         | 2 bytes         | 80000) 2 bytes  |
+--------+--------+--------+--------+--------+--------+--------+--------+
```

**Encoding Examples:**
- Temperature 25.5°C → 255 (0x00FF)
- Humidity 65.3% → 653 (0x028D)
- Pressure 1013.25 hPa → (101325 - 80000) = 21325 (0x5345)

#### WindSense (7 bytes payload)
```
+--------+--------+--------+--------+--------+--------+--------+
| Wind Speed      | Wind Gust       | Direction       | Turb. |
| uint16 (*10)    | uint16 (*10)    | uint16          | uint8 |
| 2 bytes         | 2 bytes         | 2 bytes         | (*10) |
+--------+--------+--------+--------+--------+--------+--------+
```

#### RainDetect (7 bytes payload)
```
+--------+--------+--------+--------+--------+--------+--------+
| Rainfall        | Soil Moisture   | Risk  | Duration        |
| uint16 (*10)    | uint16 (*10)    | uint8 | uint16          |
| 2 bytes         | 2 bytes         | 1 byte| 2 bytes         |
+--------+--------+--------+--------+--------+--------+--------+
```

#### AirQualityBox (6 bytes payload)
```
+--------+--------+--------+--------+--------+--------+
| CO2             | Ozone           | AQI             |
| uint16          | uint16 (*10)    | uint16          |
| 2 bytes         | 2 bytes         | 2 bytes         |
+--------+--------+--------+--------+--------+--------+
```

### 4.4 Binary Protocol Characteristics

- **DATA message size**: 19-21 bytes (device-dependent)
- **~90% smaller** than JSON
- **Fixed-width fields**: Easy parsing
- **Network byte order**: Big-endian (as per RFC standards)

---

## 5. Program Flowcharts

### 5.1 Server Receive Cycle

```
┌─────────────────────────┐
│   Server Listening      │
│   on UDP port 9999      │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Datagram Received?     │◄──────────────┐
└───────────┬─────────────┘               │
            │ Yes                         │
            ▼                             │
┌─────────────────────────┐               │
│  Parse Header           │               │
│  (msg_type, device,     │               │
│   flags, timestamp)     │               │
└───────────┬─────────────┘               │
            │                             │
            ▼                             │
      ┌─────────┐                         │
      │msg_type?│                         │
      └────┬────┘                         │
           │                              │
    ┌──────┼──────┬────────┐             │
    ▼      ▼      ▼        ▼             │
┌────────┐┌────┐┌──────┐┌────────┐       │
│REGISTER││DATA││CTRL  ││Invalid │       │
└───┬────┘└─┬──┘└──┬───┘└────┬───┘       │
    │       │      │         │           │
    ▼       ▼      ▼         ▼           │
┌───────┐┌──────┐┌─────┐┌────────┐       │
│Gen    ││Check ││Parse││Log     │       │
│Token  ││Token ││Sub  ││Error   │       │
│       ││& CRC ││type ││        │       │
└───┬───┘└──┬───┘└──┬──┘└────────┘       │
    │       │       │                    │
    │       ▼       ▼                    │
    │   ┌───────┐┌─────┐                │
    │   │Update ││PING/│                │
    │   │State  ││PONG/│                │
    │   │       ││ACK/ │                │
    │   └───┬───┘│ERR  │                │
    │       │    └──┬──┘                │
    ▼       ▼       ▼                   │
┌─────────────────────────┐             │
│  Send Response          │             │
│  (ACK/ERROR/PING)       │             │
└───────────┬─────────────┘             │
            │                           │
            └───────────────────────────┘
```

### 5.2 Server Send Cycle (Activity Checker)

```
┌─────────────────────────┐
│  Activity Checker       │
│  (Every 5 seconds)      │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  For Each Registered    │◄──────────────┐
│  Device                 │               │
└───────────┬─────────────┘               │
            │                             │
            ▼                             │
┌─────────────────────────┐               │
│  Calculate Time Since   │               │
│  Last Message           │               │
└───────────┬─────────────┘               │
            │                             │
            ▼                             │
      ┌─────────────┐                     │
      │ > 15 sec?   │                     │
      └──┬──────┬───┘                     │
         │ No   │ Yes                     │
         │      ▼                         │
         │  ┌─────────────────┐           │
         │  │ Disconnected?   │           │
         │  └──┬──────┬───────┘           │
         │     │ Yes  │ No                │
         │     │      ▼                   │
         │     │  ┌──────────────┐        │
         │     │  │Mark as       │        │
         │     │  │Disconnected  │        │
         │     │  │ping_attempts=1        │
         │     │  │Print WARNING │        │
         │     │  └──────┬───────┘        │
         │     │         │                │
         │     ▼         ▼                │
         │  ┌──────────────────┐          │
         │  │ping_attempts<10? │          │
         │  └──┬──────┬────────┘          │
         │     │ Yes  │ No                │
         │     ▼      ▼                   │
         │  ┌────┐ ┌────────┐             │
         │  │Send│ │Give Up │             │
         │  │PING│ └────────┘             │
         │  │Inc │                        │
         │  │Cnt │                        │
         │  └──┬─┘                        │
         ▼     │                          │
         └─────┴──────────────────────────┘
```

### 5.3 Client Send Cycle

```
┌─────────────────────────┐
│  Start Client           │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Send REGISTER          │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Wait for REGISTER_ACK  │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Store Token            │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Start Data Loop        │◄──────────────┐
│  (Every 10 seconds)     │               │
└───────────┬─────────────┘               │
            │                             │
            ▼                             │
      ┌─────────┐                         │
      │Active?  │                         │
      └────┬────┘                         │
           │ Yes                          │
           ▼                              │
┌─────────────────────────┐               │
│  Generate Sensor Data   │               │
│  (Random in Range)      │               │
└───────────┬─────────────┘               │
            │                             │
            ▼                             │
┌─────────────────────────┐               │
│  Corrupt CRC?           │               │
│  (UAT3 Test)            │               │
└───────────┬─────────────┘               │
            │                             │
            ▼                             │
┌─────────────────────────┐               │
│  Encode Binary Message  │               │
│  Calculate CRC32        │               │
└───────────┬─────────────┘               │
            │                             │
            ▼                             │
┌─────────────────────────┐               │
│  Send DATA Message      │               │
└───────────┬─────────────┘               │
            │                             │
            ▼                             │
┌─────────────────────────┐               │
│  Start ACK Timer        │               │
│  (1 second)             │               │
└───────────┬─────────────┘               │
            │                             │
            ▼                             │
┌─────────────────────────┐               │
│  Sleep 10 seconds       │               │
└───────────┬─────────────┘               │
            │                             │
            └─────────────────────────────┘
```

### 5.4 Client Receive Cycle

```
┌─────────────────────────┐
│  Datagram Received      │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Parse Header           │
└───────────┬─────────────┘
            │
            ▼
      ┌─────────┐
      │msg_type?│
      └────┬────┘
           │
    ┌──────┼─────────┬────────┐
    ▼      ▼         ▼        ▼
┌────────┐┌──────┐┌────────┐┌────┐
│REG_ACK ││CTRL  ││DATA_ACK││ERR │
└───┬────┘└──┬───┘└────┬───┘└─┬──┘
    │        │         │      │
    ▼        ▼         ▼      ▼
┌────────┐┌──────┐┌────────┐┌──────┐
│Extract ││PING? ││Cancel  ││CRC   │
│Token   ││      ││ACK     ││FAIL? │
│Start   ││      ││Timer   ││      │
│Data    │└──┬───┘└────────┘└──┬───┘
│Loop    │   │                 │
└────────┘   ▼                 ▼
         ┌────────┐        ┌────────┐
         │Delay?  │        │Resend  │
         │        │        │Clean   │
         └───┬────┘        │Data    │
             │             └────────┘
             ▼
         ┌────────┐
         │Send    │
         │PONG    │
         │Resume  │
         │Active  │
         └────────┘
```

---

## 6. Sequence Diagrams

### 6.1 UAT1: Basic Registration and Data Flow

```
Client              Server
  │                   │
  │──► REGISTER ──────►│
  │                   │ Generate Token
  │                   │ Store Client Info
  │◄── REGISTER_ACK ──│
  │    (Token)        │
  │                   │
  │──► DATA ──────────►│ Validate Token
  │    (with Token)   │ Check CRC
  │                   │ Process Data
  │◄── DATA_ACK ──────│
  │                   │
```

### 6.2 UAT2: Manual Data with Battery Warning

```
Client              Server
  │                   │
  │──► DATA ──────────►│ battery_low flag = 1
  │    (battery=true) │ Validate Token
  │                   │ Check CRC
  │                   │ Print WARNING
  │◄── DATA_ACK ──────│
  │                   │
```

### 6.3 UAT3: CRC Error Detection and Recovery

```
Client              Server
  │                   │
  │──► DATA ──────────►│ Validate Token ✓
  │    (BAD CRC)      │ Check CRC ✗
  │                   │
  │◄── ERROR ─────────│ error=CRC_FAIL
  │    (CRC_FAIL)     │
  │                   │
  │──► DATA ──────────►│ Validate Token ✓
  │    (GOOD CRC)     │ Check CRC ✓
  │                   │ Process Data
  │◄── DATA_ACK ──────│
  │                   │
```

### 6.4 UAT4: Disconnect Detection and Reconnection

```
Client              Server
  │                   │
  │──► DATA ──────────►│ last_seen = now
  │◄── DATA_ACK ──────│
  │                   │
  │                   │
  │  (stopped)        │
  │                   │ (15s timeout)
  │                   │ Mark disconnected
  │                   │ ping_attempts = 1
  │                   │ Print WARNING
  │◄──── PING ────────│
  │  (ignored)        │
  │                   │ (5s later)
  │                   │ ping_attempts = 2
  │◄──── PING ────────│ Print WARNING again
  │  (ignored)        │
  │                   │ (5s later)
  │                   │ ping_attempts = 3
  │◄──── PING ────────│
  │                   │
  │──► PONG ──────────►│ last_seen = now
  │                   │ ping_attempts = 0
  │                   │ disconnected = false
  │                   │ Print RECONNECTED
```

### 6.5 UAT5: ACK Timeout and Retransmission

```
Client              Server (configured to ignore 3 ACKs)
  │                   │
  │──► DATA #1 ───────►│ Process data
  │                   │ (No ACK sent)
  │                   │
  │  (1s timeout)     │
  │──► DATA #1 ───────►│ Process data
  │    (resend)       │ (No ACK sent)
  │                   │
  │  (1s timeout)     │
  │──► DATA #1 ───────►│ Process data
  │    (resend)       │ (No ACK sent)
  │                   │
  │  (1s timeout)     │
  │──► DATA #1 ───────►│ Process data
  │    (resend)       │
  │◄── DATA_ACK ──────│ (4th attempt gets ACK)
  │                   │
```

---

## 7. Libraries Used

### 7.1 Python Standard Libraries

#### asyncio
- **Purpose**: Asynchronous I/O for concurrent operations
- **Usage**: UDP transport, event loops, background tasks
- **Key Functions**:
  - `create_datagram_endpoint()` - UDP socket creation
  - `create_task()` - Background coroutines
  - `sleep()` - Non-blocking delays

#### struct
- **Purpose**: Binary data packing/unpacking
- **Usage**: Serialize data to binary format
- **Format Strings**:
  - `!` - Network byte order (big-endian)
  - `B` - Unsigned char (1 byte)
  - `H` - Unsigned short (2 bytes)
  - `h` - Signed short (2 bytes)
  - `I` - Unsigned int (4 bytes)

#### json
- **Purpose**: JSON encoding/decoding
- **Usage**: JSON protocol implementation
- **Key Functions**:
  - `dumps()` - Serialize to JSON string
  - `loads()` - Deserialize from JSON string

#### zlib
- **Purpose**: CRC32 checksum calculation
- **Usage**: Error detection in both protocols
- **Key Function**: `crc32()` - Calculate 32-bit cyclic redundancy check

#### time
- **Purpose**: Timestamp generation
- **Usage**: Message timestamps, timing measurements
- **Key Functions**:
  - `time()` - Current Unix timestamp (float)
  - `int(time())` - Integer timestamp for messages

#### random
- **Purpose**: Test data generation
- **Usage**: Simulate sensor readings
- **Key Functions**:
  - `uniform()` - Random float in range
  - `randint()` - Random integer in range

### 7.2 Wireshark LUA Libraries

#### Proto
- **Purpose**: Protocol dissector creation
- **Usage**: Define FIITMeteo protocol dissector

#### ProtoField
- **Purpose**: Define protocol fields
- **Usage**: Define message fields for Wireshark display

#### DissectorTable
- **Purpose**: Register protocol on port
- **Usage**: Associate dissector with UDP port 9999

---

## 8. Encapsulation Example

### 8.1 ThermoNode DATA Message - Complete L2 Encapsulation

#### Application Layer (21 bytes)
```
Binary Protocol Message:
+------+----------+----------+-------------+---------+---------+
| Byte | 00       | 01-04    | 05-08       | 09-16   | 17-20   |
+------+----------+----------+-------------+---------+---------+
| Data | 82       | 49 96 02 | 00 00 30 39 | Payload | CRC32   |
+------+----------+----------+-------------+---------+---------+

Byte 0: 0x82 = 10 00 0010
        └─┘ └─┘ └──┘
         │   │    └─ flags (battery_low=0)
         │   └────── device_type (00 = ThermoNode)
         └────────── msg_type (10 = DATA)

Bytes 1-4: Timestamp = 1234567890 (0x499602D2)
Bytes 5-8: Token = 12345 (0x00003039)

Bytes 9-16: Payload (ThermoNode, 8 bytes)
  [09-10]: Temperature = 255 (25.5°C) = 0x00FF
  [11-12]: Humidity = 653 (65.3%) = 0x028D
  [13-14]: Dew Point = 152 (15.2°C) = 0x0098
  [15-16]: Pressure = 21325 (1013.25 hPa) = 0x534D

Bytes 17-20: CRC32 = 0xXXXXXXXX
```

#### Layer 4 - UDP Header (8 bytes)
```
+--------+--------+--------+--------+
| Source Port     | Dest Port       |
| 2 bytes         | 2 bytes (9999)  |
+--------+--------+--------+--------+
| Length          | Checksum        |
| 29 (8+21)       | Calculated      |
+--------+--------+--------+--------+
```

#### Layer 3 - IPv4 Header (20 bytes, no options)
```
+--------+--------+--------+--------+
| Ver/IHL| DSCP/ECN| Total Length  |
| 0x45   | 0x00   | 49 (20+8+21)   |
+--------+--------+--------+--------+
| Identification  | Flags/Fragment |
| Variable        | 0x0000         |
+--------+--------+--------+--------+
| TTL    | Protocol| Header Checksum|
| 64     | 17 (UDP)| Calculated     |
+--------+--------+--------+--------+
| Source IP Address                |
| 127.0.0.1 (0x7F000001)           |
+--------+--------+--------+--------+
| Destination IP Address           |
| 127.0.0.1 (0x7F000001)           |
+--------+--------+--------+--------+
```

#### Layer 2 - Ethernet Frame (14 bytes header + 4 bytes FCS)
```
+--------+--------+--------+--------+--------+--------+
| Destination MAC Address (6 bytes)                  |
| Example: 00:11:22:33:44:55                         |
+--------+--------+--------+--------+--------+--------+
| Source MAC Address (6 bytes)                       |
| Example: AA:BB:CC:DD:EE:FF                         |
+--------+--------+--------+--------+--------+--------+
| EtherType       | Payload (IP Packet) ...          |
| 0x0800 (IPv4)   |                                  |
+--------+--------+--------+--------+--------+--------+
| Frame Check Sequence (FCS) - 4 bytes               |
| CRC-32 over entire frame                           |
+--------+--------+--------+--------+--------+--------+
```

### 8.2 Complete Frame Size Breakdown

```
Layer           | Size (bytes) | Percentage
----------------|--------------|------------
Application     | 21           | 30.0%
UDP Header      | 8            | 11.4%
IPv4 Header     | 20           | 28.6%
Ethernet Header | 14           | 20.0%
Ethernet FCS    | 4            | 5.7%
Preamble + SFD  | 8            | 4.3%
----------------|--------------|------------
TOTAL           | 70           | 100%
```

**On-Wire Efficiency:**
- Useful data (sensor readings): 8 bytes (11.4%)
- Protocol overhead (app+transport+network+link): 62 bytes (88.6%)

**Comparison with JSON:**
- JSON application layer: ~220 bytes
- JSON total frame: ~269 bytes
- Binary saves: ~199 bytes per message (74% reduction)

---

## 9. Efficiency Measurements

### 9.1 Single Message Comparison

#### ThermoNode DATA Message
```
Protocol   | App Layer | With L2-L4 | Improvement
-----------|-----------|------------|-------------
JSON       | 220 bytes | 262 bytes  | (baseline)
Binary     | 21 bytes  | 63 bytes   | 90.5% / 76.0%
MQTT (est) | 167 bytes | 209 bytes  | (reference)
```

#### WindSense DATA Message
```
Protocol   | App Layer | With L2-L4 | Improvement
-----------|-----------|------------|-------------
JSON       | 221 bytes | 263 bytes  | (baseline)
Binary     | 20 bytes  | 62 bytes   | 91.0% / 76.4%
MQTT (est) | 168 bytes | 210 bytes  | (reference)
```

#### RainDetect DATA Message
```
Protocol   | App Layer | With L2-L4 | Improvement
-----------|-----------|------------|-------------
JSON       | 219 bytes | 261 bytes  | (baseline)
Binary     | 20 bytes  | 62 bytes   | 90.9% / 76.2%
MQTT (est) | 166 bytes | 208 bytes  | (reference)
```

#### AirQualityBox DATA Message
```
Protocol   | App Layer | With L2-L4 | Improvement
-----------|-----------|------------|-------------
JSON       | 196 bytes | 238 bytes  | (baseline)
Binary     | 19 bytes  | 61 bytes   | 90.3% / 74.4%
MQTT (est) | 143 bytes | 185 bytes  | (reference)
```

### 9.2 Control Messages Comparison

```
Message Type  | JSON  | Binary | Improvement
--------------|-------|--------|-------------
REGISTER      | 74 B  | 5 B    | 93.2%
REGISTER_ACK  | 98 B  | 9 B    | 90.8%
PING          | 70 B  | 5 B    | 92.9%
PONG          | 86 B  | 9 B    | 89.5%
DATA_ACK      | 90 B  | 5 B    | 94.4%
ERROR         | 105 B | 6 B    | 94.3%
```

### 9.3 Summary Statistics

#### All 4 Devices (one message each)
```
Metric          | JSON     | Binary  | MQTT(est)| Savings
----------------|----------|---------|----------|----------
App Layer Total | 856 B    | 80 B    | 644 B    | 776 B (90.7%)
With L2-L4      | 1024 B   | 248 B   | 812 B    | 776 B (75.8%)
```

#### 10-Minute Operation Scenario
**Conditions:**
- 4 sensors sending data every 10 seconds
- 240 data messages + 8 control messages = 248 total

```
Metric              | JSON      | Binary    | Savings
--------------------|-----------|-----------|-------------
App Layer           | 50.83 KB  | 4.74 KB   | 46.09 KB (90.7%)
With L2-L4 Overhead | 61.00 KB  | 14.91 KB  | 46.09 KB (75.6%)
```

### 9.4 Efficiency Chart Data

#### Message Size by Device Type (Application Layer)
```
Device          | JSON (B) | Binary (B) | Reduction (%)
----------------|----------|------------|---------------
ThermoNode      | 220      | 21         | 90.5%
WindSense       | 221      | 20         | 91.0%
RainDetect      | 219      | 20         | 90.9%
AirQualityBox   | 196      | 19         | 90.3%
```

#### Binary vs MQTT Comparison
```
Device          | MQTT (B) | Binary (B) | Binary vs MQTT (%)
----------------|----------|------------|-----------------
ThermoNode      | 167      | 21         | 87.4% smaller
WindSense       | 168      | 20         | 88.1% smaller
RainDetect      | 166      | 20         | 88.0% smaller
AirQualityBox   | 143      | 19         | 86.7% smaller
```

### 9.5 Bandwidth Savings Over Time

#### 1 Hour of Operation
- Messages: 1,440 data + 8 control = 1,448 messages
- JSON: ~305 KB (app layer), ~366 KB (total)
- Binary: ~28 KB (app layer), ~89 KB (total)
- **Savings: 277 KB (75.7%)**

#### 24 Hours of Operation
- Messages: 34,560 data + 8 control = 34,568 messages
- JSON: ~7.3 MB (app layer), ~8.8 MB (total)
- Binary: ~0.68 MB (app layer), ~2.1 MB (total)
- **Savings: 6.7 MB (75.7%)**

#### 1 Month of Operation (30 days)
- JSON: ~220 MB (app layer), ~264 MB (total)
- Binary: ~20 MB (app layer), ~64 MB (total)
- **Savings: 200 MB (75.7%)**

### 9.6 Key Optimization Techniques

1. **Bit-level Packing**
   - Message type (2 bits) + Device type (2 bits) + Flags (4 bits) = 1 byte
   - Replaces ~50+ bytes of JSON structure

2. **Fixed-Point Arithmetic**
   - Temperature: 2 bytes (vs ~7 bytes in JSON: "25.5")
   - Humidity: 2 bytes (vs ~7 bytes in JSON: "65.3")

3. **Binary Token**
   - 4 bytes integer vs 10+ bytes string ("T-12345")

4. **Eliminated Redundancy**
   - No field names
   - No quotes, braces, commas
   - No whitespace

5. **Optimal Data Types**
   - uint16 for bounded values (0-1000 range)
   - int16 for signed values (-50 to +60 range)
   - uint8 for small values (0-255 range)

---

## 10. Wireshark Dissector

### 10.1 Installation

The Wireshark LUA dissector (`fiitmeteo.lua`) enables protocol visualization and analysis.

**Installation Paths:**
- **Windows**: `%APPDATA%\Wireshark\plugins\`
- **Linux**: `~/.local/lib/wireshark/plugins/`
- **macOS**: `~/.config/wireshark/plugins/`

### 10.2 Features

- **Automatic Protocol Detection**: Recognizes UDP port 9999
- **Field Dissection**: Parses all message types and device-specific data
- **Human-Readable Display**: Converts binary values to readable format
- **Color Coding**: Wireshark applies filters and colors
- **Info Column**: Shows message summary

### 10.3 Display Filters

```
fiitmeteo                          # All FIITMeteo traffic
fiitmeteo.msg_type == 2            # DATA messages only
fiitmeteo.device_type == 0         # ThermoNode only
fiitmeteo.battery_low == 1         # Low battery warnings
fiitmeteo.temperature > 25         # Temperature above 25°C
fiitmeteo.ctrl_subtype == 1        # PING messages
```

### 10.4 Wireshark Output Example

```
Frame 1: 63 bytes on wire (504 bits), 63 bytes captured
Ethernet II, Src: 00:11:22:33:44:55, Dst: aa:bb:cc:dd:ee:ff
Internet Protocol Version 4, Src: 127.0.0.1, Dst: 127.0.0.1
User Datagram Protocol, Src Port: 54321, Dst Port: 9999
FIITMeteo Protocol Data
    Header
        Message Type: DATA (2)
        Device Type: ThermoNode (0)
        Battery Low: False
        Timestamp: 1234567890
    Token: 12345
    Device Data
        Temperature: 25.5 °C
        Humidity: 65.3 %
        Dew Point: 15.2 °C
        Pressure: 1013.25 hPa
    CRC32: 0xa3b5c7d9
```

---

## Appendix A: Educational Evaluation

### What I Learned Thanks to This Assignment

This project provided invaluable hands-on experience in network protocol design and implementation. I learned how to optimize data transmission through careful bit-level design, understanding the tradeoff between human readability (JSON) and efficiency (binary). Working with UDP taught me about unreliable transport protocols and how to build reliability at the application layer through acknowledgments, timeouts, and retransmissions.

The implementation of CRC32 error detection demonstrated practical error handling in network communications. I gained experience with Python's `asyncio` for concurrent programming, `struct` for binary serialization, and the importance of network byte order (big-endian) in cross-platform communication.

Creating the Wireshark dissector in LUA revealed the inner workings of packet analysis tools and deepened my understanding of protocol layering (OSI model). Measuring and comparing protocol efficiency showed the real-world impact of design decisions—achieving 90% bandwidth reduction demonstrates how thoughtful engineering can dramatically improve system performance.

### How These Skills Help Me

In further studies, this knowledge applies to courses in distributed systems, embedded systems, and IoT applications. Understanding protocol design is fundamental for any networked application, from microservices to sensor networks.

In the job market, these skills are highly valuable for roles in:
- **Embedded Systems Engineering**: IoT devices require efficient protocols for battery and bandwidth conservation
- **Network Engineering**: Protocol optimization is crucial for high-throughput systems
- **Backend Development**: Designing efficient APIs and data serialization formats
- **DevOps/SRE**: Understanding network overhead helps optimize distributed systems

The ability to analyze, measure, and optimize system performance—rather than just implementing features—distinguishes senior engineers from junior developers. This project taught me to think critically about resource usage and to validate design decisions with quantitative measurements.

---

## Conclusion

The FIITMeteo project successfully demonstrates the design and implementation of an efficient binary protocol for weather sensor data collection. The binary protocol achieves a 90.7% reduction in application-layer bandwidth compared to JSON, while maintaining reliability through CRC error detection, acknowledgments, and automatic reconnection.

All five UAT scenarios (UAT1-UAT5) are fully implemented and functional. The Wireshark dissector provides comprehensive packet analysis capabilities. The comparison with both JSON and MQTT protocols validates the efficiency gains of the custom binary protocol.

This implementation showcases best practices in protocol design: optimal bit packing, appropriate data type selection, network byte order compliance, and layered architecture with clear separation of concerns.

---

**End of Documentation**

-- FIITMeteo Binary Protocol Dissector for Wireshark
-- Author: Generated for FIITMeteo UDP Protocol
-- Version: 1.0
--
-- Installation:
-- 1. Copy this file to Wireshark's plugin directory:
--    - Windows: %APPDATA%\Wireshark\plugins\
--    - Linux: ~/.local/lib/wireshark/plugins/
--    - macOS: ~/.config/wireshark/plugins/
-- 2. Restart Wireshark
-- 3. Protocol will automatically dissect UDP traffic on port 9999
--
-- Usage:
-- - Capture UDP traffic on port 9999
-- - Filter: fiitmeteo
-- - The dissector will automatically decode all message fields

-- Declare the protocol
fiitmeteo_proto = Proto("fiitmeteo", "FIITMeteo Binary Protocol")

-- Message type definitions
local msg_types = {
    [0] = "REGISTER",
    [1] = "REGISTER_ACK",
    [2] = "DATA",
    [3] = "DATA_ACK",
    [4] = "ERROR",
    [5] = "PING",
    [6] = "PONG"
}

-- Device type definitions
local device_types = {
    [0] = "ThermoNode",
    [1] = "WindSense",
    [2] = "RainDetect",
    [3] = "AirQualityBox"
}

-- Error code definitions
local error_codes = {
    [0] = "INVALID_TOKEN",
    [1] = "CRC_FAIL"
}

-- Request code definitions
local request_codes = {
    [0] = "NONE",
    [1] = "RESEND_LAST"
}

-- Protocol fields
local f = fiitmeteo_proto.fields

-- Header fields
f.msg_type = ProtoField.uint8("fiitmeteo.msg_type", "Message Type", base.DEC, msg_types, 0x07)
f.device_type = ProtoField.uint8("fiitmeteo.device_type", "Device Type", base.DEC, device_types, 0x18)
f.battery_low = ProtoField.bool("fiitmeteo.battery_low", "Battery Low", 8, nil, 0x20)
f.flags_reserved = ProtoField.uint8("fiitmeteo.flags_reserved", "Reserved Flags", base.HEX, nil, 0xC0)

-- Common fields
f.timestamp = ProtoField.absolute_time("fiitmeteo.timestamp", "Timestamp", base.UTC)
f.token = ProtoField.uint16("fiitmeteo.token", "Token", base.DEC)
f.crc32 = ProtoField.uint32("fiitmeteo.crc32", "CRC32", base.HEX)
f.crc32_status = ProtoField.string("fiitmeteo.crc32_status", "CRC Status")

-- Error message fields
f.error_code = ProtoField.uint8("fiitmeteo.error_code", "Error Code", base.DEC, error_codes)
f.request_code = ProtoField.uint8("fiitmeteo.request_code", "Request Code", base.DEC, request_codes)

-- Status field
f.status = ProtoField.uint8("fiitmeteo.status", "Status", base.DEC, {[0] = "FAIL", [1] = "OK"})

-- ThermoNode fields
f.temperature = ProtoField.float("fiitmeteo.temperature", "Temperature (°C)")
f.humidity = ProtoField.float("fiitmeteo.humidity", "Humidity (%)")
f.dew_point = ProtoField.float("fiitmeteo.dew_point", "Dew Point (°C)")
f.pressure = ProtoField.float("fiitmeteo.pressure", "Pressure (hPa)")

-- WindSense fields
f.wind_speed = ProtoField.float("fiitmeteo.wind_speed", "Wind Speed (m/s)")
f.wind_gust = ProtoField.float("fiitmeteo.wind_gust", "Wind Gust (m/s)")
f.wind_direction = ProtoField.uint16("fiitmeteo.wind_direction", "Wind Direction (°)")
f.turbulence = ProtoField.float("fiitmeteo.turbulence", "Turbulence")

-- RainDetect fields
f.rainfall = ProtoField.float("fiitmeteo.rainfall", "Rainfall (mm)")
f.soil_moisture = ProtoField.float("fiitmeteo.soil_moisture", "Soil Moisture (%)")
f.flood_risk = ProtoField.uint8("fiitmeteo.flood_risk", "Flood Risk Level")
f.rain_duration = ProtoField.uint16("fiitmeteo.rain_duration", "Rain Duration (min)")

-- AirQualityBox fields
f.co2 = ProtoField.uint16("fiitmeteo.co2", "CO2 (ppm)")
f.ozone = ProtoField.float("fiitmeteo.ozone", "Ozone (µg/m³)")
f.air_quality_index = ProtoField.uint16("fiitmeteo.air_quality_index", "Air Quality Index")

-- Helper function to calculate CRC32
function calc_crc32(data)
    local crc = 0xFFFFFFFF

    for i = 0, data:len() - 1 do
        local byte = data:byte(i + 1)
        crc = bit32.bxor(crc, byte)

        for j = 0, 7 do
            if bit32.band(crc, 1) ~= 0 then
                crc = bit32.bxor(bit32.rshift(crc, 1), 0xEDB88320)
            else
                crc = bit32.rshift(crc, 1)
            end
        end
    end

    return bit32.bxor(crc, 0xFFFFFFFF)
end

-- Main dissector function
function fiitmeteo_proto.dissector(buffer, pinfo, tree)
    local length = buffer:len()
    if length < 9 then return end

    pinfo.cols.protocol = fiitmeteo_proto.name

    local subtree = tree:add(fiitmeteo_proto, buffer(), "FIITMeteo Binary Protocol")

    -- Parse header byte
    local header = buffer(0, 1):uint()
    local msg_type = bit32.band(header, 0x07)
    local device_type = bit32.band(bit32.rshift(header, 3), 0x03)
    local battery_low = bit32.band(bit32.rshift(header, 5), 0x01) == 1

    -- Add header fields
    local header_tree = subtree:add(buffer(0, 1), "Header")
    header_tree:add(f.msg_type, buffer(0, 1))
    header_tree:add(f.device_type, buffer(0, 1))
    header_tree:add(f.battery_low, buffer(0, 1))
    header_tree:add(f.flags_reserved, buffer(0, 1))

    -- Update info column
    local msg_type_str = msg_types[msg_type] or "UNKNOWN"
    local device_type_str = device_types[device_type] or "UNKNOWN"
    pinfo.cols.info = string.format("%s - %s", msg_type_str, device_type_str)

    if battery_low then
        pinfo.cols.info:append(" [LOW BATTERY]")
    end

    -- Parse timestamp (4 bytes)
    local timestamp = buffer(1, 4):uint()
    subtree:add(f.timestamp, buffer(1, 4), timestamp)

    -- Parse CRC from end (last 4 bytes)
    local crc_offset = length - 4
    local received_crc = buffer(crc_offset, 4):uint()

    -- Calculate expected CRC
    local data_for_crc = buffer(0, crc_offset):bytes()
    local calculated_crc = calc_crc32(data_for_crc)
    local crc_valid = (received_crc == calculated_crc)

    local crc_tree = subtree:add(f.crc32, buffer(crc_offset, 4))
    if crc_valid then
        crc_tree:add(f.crc32_status, buffer(crc_offset, 4), "VALID")
        crc_tree:append_text(" [VALID]")
    else
        crc_tree:add(f.crc32_status, buffer(crc_offset, 4), "INVALID")
        crc_tree:append_text(string.format(" [INVALID - Expected: 0x%08X]", calculated_crc))
        pinfo.cols.info:append(" [CRC ERROR]")
    end

    -- Parse message-specific fields
    local offset = 5

    if msg_type == 0 then
        -- REGISTER: just header + timestamp + CRC

    elseif msg_type == 1 then
        -- REGISTER_ACK: header + timestamp + token + CRC
        subtree:add(f.token, buffer(offset, 2))

    elseif msg_type == 2 then
        -- DATA: header + timestamp + token + payload + CRC
        local token_tree = subtree:add(f.token, buffer(offset, 2))
        offset = offset + 2

        -- Parse device-specific payload
        local payload_len = crc_offset - offset
        local payload_tree = subtree:add(buffer(offset, payload_len), "Data Payload")

        if device_type == 0 then
            -- ThermoNode (8 bytes)
            if payload_len == 8 then
                local temp = buffer(offset, 2):int() / 10.0
                local humidity = buffer(offset + 2, 2):uint() / 10.0
                local dew = buffer(offset + 4, 2):int() / 10.0
                -- Pressure: offset from 800.0 hPa
                local pressure = (buffer(offset + 6, 2):uint() / 100.0) + 800.0

                payload_tree:add(f.temperature, buffer(offset, 2), temp)
                payload_tree:add(f.humidity, buffer(offset + 2, 2), humidity)
                payload_tree:add(f.dew_point, buffer(offset + 4, 2), dew)
                payload_tree:add(f.pressure, buffer(offset + 6, 2), pressure)

                pinfo.cols.info:append(string.format(" [T:%.1f°C H:%.1f%% P:%.2fhPa]", temp, humidity, pressure))
            end

        elseif device_type == 1 then
            -- WindSense (7 bytes)
            if payload_len == 7 then
                local speed = buffer(offset, 2):uint() / 10.0
                local gust = buffer(offset + 2, 2):uint() / 10.0
                local direction = buffer(offset + 4, 2):uint()
                local turbulence = buffer(offset + 6, 1):uint() / 10.0

                payload_tree:add(f.wind_speed, buffer(offset, 2), speed)
                payload_tree:add(f.wind_gust, buffer(offset + 2, 2), gust)
                payload_tree:add(f.wind_direction, buffer(offset + 4, 2), direction)
                payload_tree:add(f.turbulence, buffer(offset + 6, 1), turbulence)

                pinfo.cols.info:append(string.format(" [Speed:%.1fm/s Dir:%d°]", speed, direction))
            end

        elseif device_type == 2 then
            -- RainDetect (7 bytes)
            if payload_len == 7 then
                local rainfall = buffer(offset, 2):uint() / 10.0
                local moisture = buffer(offset + 2, 2):uint() / 10.0
                local risk = buffer(offset + 4, 1):uint()
                local duration = buffer(offset + 5, 2):uint()

                payload_tree:add(f.rainfall, buffer(offset, 2), rainfall)
                payload_tree:add(f.soil_moisture, buffer(offset + 2, 2), moisture)
                payload_tree:add(f.flood_risk, buffer(offset + 4, 1), risk)
                payload_tree:add(f.rain_duration, buffer(offset + 5, 2), duration)

                pinfo.cols.info:append(string.format(" [Rain:%.1fmm Risk:%d]", rainfall, risk))
            end

        elseif device_type == 3 then
            -- AirQualityBox (6 bytes)
            if payload_len == 6 then
                local co2 = buffer(offset, 2):uint()
                local ozone = buffer(offset + 2, 2):uint() / 10.0
                local aqi = buffer(offset + 4, 2):uint()

                payload_tree:add(f.co2, buffer(offset, 2), co2)
                payload_tree:add(f.ozone, buffer(offset + 2, 2), ozone)
                payload_tree:add(f.air_quality_index, buffer(offset + 4, 2), aqi)

                pinfo.cols.info:append(string.format(" [CO2:%dppm AQI:%d]", co2, aqi))
            end
        end

    elseif msg_type == 3 then
        -- DATA_ACK: header + timestamp + status + CRC
        subtree:add(f.status, buffer(offset, 1))

    elseif msg_type == 4 then
        -- ERROR: header + timestamp + error_code + request_code + CRC
        local error_code = buffer(offset, 1):uint()
        local request_code = buffer(offset + 1, 1):uint()

        subtree:add(f.error_code, buffer(offset, 1))
        subtree:add(f.request_code, buffer(offset + 1, 1))

        local error_str = error_codes[error_code] or "UNKNOWN"
        pinfo.cols.info:append(string.format(" [%s]", error_str))

    elseif msg_type == 5 then
        -- PING: just header + timestamp + CRC

    elseif msg_type == 6 then
        -- PONG: header + timestamp + token + CRC
        subtree:add(f.token, buffer(offset, 2))
    end

    return length
end

-- Register the protocol on UDP port 9999
local udp_port = DissectorTable.get("udp.port")
udp_port:add(9999, fiitmeteo_proto)

-- Also register for manual "Decode As..."
DissectorTable.get("udp.port"):add(0, fiitmeteo_proto)

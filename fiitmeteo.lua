-- FIITMeteo Binary Protocol Dissector for Wireshark
-- Supports all device types: ThermoNode, WindSense, RainDetect, AirQualityBox
-- Save this file as fiitmeteo.lua in Wireshark plugins folder
-- Windows: %APPDATA%\Wireshark\plugins\
-- Linux: ~/.local/lib/wireshark/plugins/
-- macOS: ~/.config/wireshark/plugins/

local fiitmeteo_proto = Proto("FIITMeteo", "FIITMeteo Binary Protocol")

-- Compatibility: Support both bit32 (new) and bit (old) libraries
local bit_lib = bit32 or bit

-- Protocol fields
local f_byte0 = ProtoField.uint8("fiitmeteo.byte0", "Byte 0", base.HEX)
local f_msg_type = ProtoField.uint8("fiitmeteo.msg_type", "Message Type", base.DEC, {
    [0] = "REGISTER",
    [1] = "REGISTER_ACK",
    [2] = "DATA",
    [3] = "CONTROL"
}, 0xC0)
local f_device_type = ProtoField.uint8("fiitmeteo.device_type", "Device Type", base.DEC, {
    [0] = "ThermoNode",
    [1] = "WindSense",
    [2] = "RainDetect",
    [3] = "AirQualityBox"
}, 0x30)
local f_flags = ProtoField.uint8("fiitmeteo.flags", "Flags", base.HEX, nil, 0x0F)
local f_battery_low = ProtoField.bool("fiitmeteo.battery_low", "Battery Low", 8, nil, 0x01)
local f_timestamp = ProtoField.uint32("fiitmeteo.timestamp", "Timestamp", base.DEC)
local f_token = ProtoField.uint32("fiitmeteo.token", "Token", base.DEC)
local f_crc = ProtoField.uint32("fiitmeteo.crc", "CRC32", base.HEX)
local f_crc_status = ProtoField.string("fiitmeteo.crc_status", "CRC Status")

-- Control message fields
local f_ctrl_type = ProtoField.uint8("fiitmeteo.ctrl_type", "Control Type", base.DEC, {
    [0] = "DATA_ACK",
    [1] = "PING",
    [2] = "PONG",
    [3] = "ERROR"
}, 0x0F)
local f_error_code = ProtoField.uint8("fiitmeteo.error_code", "Error Code", base.HEX, {
    [0x01] = "INVALID_TOKEN",
    [0x02] = "CRC_FAIL",
    [0x03] = "INVALID_DATA"
})

-- ThermoNode data fields
local f_temperature = ProtoField.float("fiitmeteo.temperature", "Temperature (°C)")
local f_humidity = ProtoField.float("fiitmeteo.humidity", "Humidity (%)")
local f_dew_point = ProtoField.float("fiitmeteo.dew_point", "Dew Point (°C)")
local f_pressure = ProtoField.float("fiitmeteo.pressure", "Pressure (hPa)")

-- WindSense data fields
local f_wind_speed = ProtoField.float("fiitmeteo.wind_speed", "Wind Speed (m/s)")
local f_wind_gust = ProtoField.float("fiitmeteo.wind_gust", "Wind Gust (m/s)")
local f_wind_direction = ProtoField.uint16("fiitmeteo.wind_direction", "Wind Direction (°)")
local f_turbulence = ProtoField.float("fiitmeteo.turbulence", "Turbulence")

-- RainDetect data fields
local f_rainfall = ProtoField.float("fiitmeteo.rainfall", "Rainfall (mm)")
local f_soil_moisture = ProtoField.float("fiitmeteo.soil_moisture", "Soil Moisture (%)")
local f_flood_risk = ProtoField.uint8("fiitmeteo.flood_risk", "Flood Risk Level")
local f_rain_duration = ProtoField.uint16("fiitmeteo.rain_duration", "Rain Duration (min)")

-- AirQualityBox data fields
local f_co2 = ProtoField.uint16("fiitmeteo.co2", "CO2 (ppm)")
local f_ozone = ProtoField.float("fiitmeteo.ozone", "Ozone (ppb)")
local f_aqi = ProtoField.uint16("fiitmeteo.aqi", "Air Quality Index")

fiitmeteo_proto.fields = {
    f_byte0, f_msg_type, f_device_type, f_flags, f_battery_low, f_timestamp, f_token, f_crc, f_crc_status,
    f_ctrl_type, f_error_code,
    f_temperature, f_humidity, f_dew_point, f_pressure,
    f_wind_speed, f_wind_gust, f_wind_direction, f_turbulence,
    f_rainfall, f_soil_moisture, f_flood_risk, f_rain_duration,
    f_co2, f_ozone, f_aqi
}

-- Device type names
local device_names = {
    [0] = "ThermoNode",
    [1] = "WindSense",
    [2] = "RainDetect",
    [3] = "AirQualityBox"
}

-- Message type names
local msg_names = {
    [0] = "REGISTER",
    [1] = "REGISTER_ACK",
    [2] = "DATA",
    [3] = "CONTROL"
}

-- Control type names
local ctrl_names = {
    [0] = "DATA_ACK",
    [1] = "PING",
    [2] = "PONG",
    [3] = "ERROR"
}

-- Helper function to read signed 16-bit integer (big-endian)
local function read_int16_be(buffer, offset)
    local value = buffer(offset, 2):uint()
    if value >= 0x8000 then
        value = value - 0x10000
    end
    return value
end

-- CRC32 calculation (same algorithm as Python's zlib.crc32)
local function crc32(data)
    local crc = 0xFFFFFFFF
    local bytes = data:bytes()

    for i = 0, bytes:len() - 1 do
        local byte = bytes:get_index(i)
        crc = bit_lib.bxor(crc, byte)
        for j = 0, 7 do
            if bit_lib.band(crc, 1) == 1 then
                crc = bit_lib.bxor(bit_lib.rshift(crc, 1), 0xEDB88320)
            else
                crc = bit_lib.rshift(crc, 1)
            end
        end
    end

    return bit_lib.bxor(crc, 0xFFFFFFFF)
end

function fiitmeteo_proto.dissector(buffer, pinfo, tree)
    local length = buffer:len()
    if length < 5 then return end

    pinfo.cols.protocol = fiitmeteo_proto.name

    local subtree = tree:add(fiitmeteo_proto, buffer(), "FIITMeteo Protocol Data")

    -- Parse header
    local byte0 = buffer(0, 1):uint()
    local msg_type = bit_lib.rshift(bit_lib.band(byte0, 0xC0), 6)
    local device_type = bit_lib.rshift(bit_lib.band(byte0, 0x30), 4)
    local flags = bit_lib.band(byte0, 0x0F)
    local timestamp = buffer(1, 4):uint()

    local device_name = device_names[device_type] or "Unknown"
    local msg_name = msg_names[msg_type] or "Unknown"

    -- Set info column
    pinfo.cols.info = string.format("%s - %s", device_name, msg_name)

    -- Add header fields
    local header_tree = subtree:add(buffer(0, 5), "Header")
    header_tree:add(f_byte0, buffer(0, 1))
    header_tree:add(f_msg_type, buffer(0, 1)):append_text(string.format(" (%s)", msg_name))
    header_tree:add(f_device_type, buffer(0, 1)):append_text(string.format(" (%s)", device_name))
    header_tree:add(f_flags, buffer(0, 1))

    local ts_item = header_tree:add(f_timestamp, buffer(1, 4))
    ts_item:append_text(string.format(" (%s)", os.date("%Y-%m-%d %H:%M:%S", timestamp)))

    -- Parse message body based on type
    if msg_type == 0 then
        -- REGISTER (5 bytes total)
        pinfo.cols.info = string.format("%s - REGISTER", device_name)

    elseif msg_type == 1 then
        -- REGISTER_ACK (9 bytes total)
        if length >= 9 then
            local token = buffer(5, 4):uint()
            subtree:add(f_token, buffer(5, 4))
            pinfo.cols.info = string.format("%s - REGISTER_ACK (Token: %d)", device_name, token)
        end

    elseif msg_type == 2 then
        -- DATA message
        if length >= 14 then
            local token = buffer(5, 4):uint()
            subtree:add(f_token, buffer(5, 4))

            -- Battery low flag
            local battery_low = bit_lib.band(flags, 0x01) == 1
            header_tree:add(f_battery_low, buffer(0, 1))

            -- Parse device-specific payload
            local payload_start = 9
            local payload_end = length - 4
            local payload_length = payload_end - payload_start

            local data_tree = subtree:add(buffer(payload_start, payload_length), "Sensor Data")

            if device_type == 0 and payload_length == 8 then
                -- ThermoNode
                local temp = read_int16_be(buffer, payload_start) / 10.0
                local hum = buffer(payload_start + 2, 2):uint() / 10.0
                local dew = read_int16_be(buffer, payload_start + 4) / 10.0
                local press = (buffer(payload_start + 6, 2):uint() + 80000) / 100.0

                data_tree:add(f_temperature, buffer(payload_start, 2), temp)
                data_tree:add(f_humidity, buffer(payload_start + 2, 2), hum)
                data_tree:add(f_dew_point, buffer(payload_start + 4, 2), dew)
                data_tree:add(f_pressure, buffer(payload_start + 6, 2), press)

                pinfo.cols.info = string.format("%s - DATA: %.1f°C, %.1f%% RH, %.1f hPa%s",
                    device_name, temp, hum, press, battery_low and " [LOW BATTERY]" or "")

            elseif device_type == 1 and payload_length == 7 then
                -- WindSense
                local speed = buffer(payload_start, 2):uint() / 10.0
                local gust = buffer(payload_start + 2, 2):uint() / 10.0
                local direction = buffer(payload_start + 4, 2):uint()
                local turb = buffer(payload_start + 6, 1):uint() / 10.0

                data_tree:add(f_wind_speed, buffer(payload_start, 2), speed)
                data_tree:add(f_wind_gust, buffer(payload_start + 2, 2), gust)
                data_tree:add(f_wind_direction, buffer(payload_start + 4, 2), direction)
                data_tree:add(f_turbulence, buffer(payload_start + 6, 1), turb)

                pinfo.cols.info = string.format("%s - DATA: %.1f m/s, gust %.1f m/s, %d°%s",
                    device_name, speed, gust, direction, battery_low and " [LOW BATTERY]" or "")

            elseif device_type == 2 and payload_length == 7 then
                -- RainDetect
                local rain = buffer(payload_start, 2):uint() / 10.0
                local moist = buffer(payload_start + 2, 2):uint() / 10.0
                local risk = buffer(payload_start + 4, 1):uint()
                local duration = buffer(payload_start + 5, 2):uint()

                data_tree:add(f_rainfall, buffer(payload_start, 2), rain)
                data_tree:add(f_soil_moisture, buffer(payload_start + 2, 2), moist)
                data_tree:add(f_flood_risk, buffer(payload_start + 4, 1), risk)
                data_tree:add(f_rain_duration, buffer(payload_start + 5, 2), duration)

                pinfo.cols.info = string.format("%s - DATA: %.1f mm, soil %.1f%%, risk %d%s",
                    device_name, rain, moist, risk, battery_low and " [LOW BATTERY]" or "")

            elseif device_type == 3 and payload_length == 6 then
                -- AirQualityBox
                local co2 = buffer(payload_start, 2):uint()
                local ozone = buffer(payload_start + 2, 2):uint() / 10.0
                local aqi = buffer(payload_start + 4, 2):uint()

                data_tree:add(f_co2, buffer(payload_start, 2), co2)
                data_tree:add(f_ozone, buffer(payload_start + 2, 2), ozone)
                data_tree:add(f_aqi, buffer(payload_start + 4, 2), aqi)

                pinfo.cols.info = string.format("%s - DATA: CO2 %d ppm, O3 %.1f ppb, AQI %d%s",
                    device_name, co2, ozone, aqi, battery_low and " [LOW BATTERY]" or "")
            end

            -- CRC validation
            local received_crc = buffer(length - 4, 4):uint()
            local calculated_crc = crc32(buffer(0, length - 4))
            local crc_valid = (received_crc == calculated_crc)

            local crc_tree = subtree:add(buffer(length - 4, 4), "CRC")
            crc_tree:add(f_crc, buffer(length - 4, 4))

            if crc_valid then
                crc_tree:add(f_crc_status, buffer(length - 4, 4), "Valid")
            else
                crc_tree:add(f_crc_status, buffer(length - 4, 4),
                    string.format("INVALID (Expected: 0x%08X)", calculated_crc))
                crc_tree:add_expert_info(PI_CHECKSUM, PI_ERROR, "CRC validation failed")
                pinfo.cols.info = pinfo.cols.info .. " [CRC ERROR]"
            end
        end

    elseif msg_type == 3 then
        -- CONTROL message
        local ctrl_type = bit_lib.band(flags, 0x0F)
        local ctrl_name = ctrl_names[ctrl_type] or "Unknown"

        header_tree:add(f_ctrl_type, buffer(0, 1)):append_text(string.format(" (%s)", ctrl_name))

        if ctrl_type == 3 and length >= 6 then
            -- ERROR message
            local error_code = buffer(5, 1):uint()
            subtree:add(f_error_code, buffer(5, 1))

            local error_names = {
                [0x01] = "INVALID_TOKEN",
                [0x02] = "CRC_FAIL",
                [0x03] = "INVALID_DATA"
            }
            local error_name = error_names[error_code] or string.format("0x%02X", error_code)

            pinfo.cols.info = string.format("%s - ERROR (%s)", device_name, error_name)

        elseif ctrl_type == 2 and length >= 9 then
            -- PONG message (has token)
            local token = buffer(5, 4):uint()
            subtree:add(f_token, buffer(5, 4))
            pinfo.cols.info = string.format("%s - PONG (Token: %d)", device_name, token)

        else
            pinfo.cols.info = string.format("%s - %s", device_name, ctrl_name)
        end
    end

    return length
end

-- Register the protocol on UDP port 9999
local udp_port = DissectorTable.get("udp.port")
udp_port:add(9999, fiitmeteo_proto)

print("FIITMeteo protocol dissector loaded successfully!")

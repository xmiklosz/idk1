-- FIITMeteo Binary Protocol Dissector
-- Save this file as fiitmeteo.lua in Wireshark plugins folder
-- Windows: %APPDATA%\Wireshark\plugins\
-- Linux: ~/.local/lib/wireshark/plugins/
-- macOS: ~/.config/wireshark/plugins/

fiitmeteo_protocol = Proto("FIITMeteo", "FIITMeteo Weather Protocol")

-- Protocol fields
local pf_msg_type = ProtoField.uint8("fiitmeteo.msg_type", "Message Type", base.DEC, {
    [0] = "REGISTER",
    [1] = "REGISTER_ACK",
    [2] = "DATA",
    [3] = "CONTROL"
}, 0xC0)

local pf_device_type = ProtoField.uint8("fiitmeteo.device_type", "Device Type", base.DEC, {
    [0] = "ThermoNode",
    [1] = "WindSense",
    [2] = "RainDetect",
    [3] = "AirQualityBox"
}, 0x30)

local pf_flags = ProtoField.uint8("fiitmeteo.flags", "Flags", base.HEX, nil, 0x0F)
local pf_battery_low = ProtoField.bool("fiitmeteo.battery_low", "Battery Low", 8, nil, 0x01)
local pf_ctrl_subtype = ProtoField.uint8("fiitmeteo.ctrl_subtype", "Control Subtype", base.DEC, {
    [0] = "DATA_ACK",
    [1] = "PING",
    [2] = "PONG",
    [3] = "ERROR"
}, 0x0F)

local pf_timestamp = ProtoField.uint32("fiitmeteo.timestamp", "Timestamp", base.DEC)
local pf_token = ProtoField.uint32("fiitmeteo.token", "Token", base.DEC)
local pf_crc = ProtoField.uint32("fiitmeteo.crc", "CRC32", base.HEX)
local pf_error_code = ProtoField.uint8("fiitmeteo.error_code", "Error Code", base.HEX, {
    [0x01] = "INVALID_TOKEN",
    [0x02] = "CRC_FAIL",
    [0x03] = "INVALID_DATA"
})

-- ThermoNode fields
local pf_temperature = ProtoField.float("fiitmeteo.temperature", "Temperature (°C)")
local pf_humidity = ProtoField.float("fiitmeteo.humidity", "Humidity (%)")
local pf_dew_point = ProtoField.float("fiitmeteo.dew_point", "Dew Point (°C)")
local pf_pressure = ProtoField.float("fiitmeteo.pressure", "Pressure (hPa)")

-- WindSense fields
local pf_wind_speed = ProtoField.float("fiitmeteo.wind_speed", "Wind Speed (m/s)")
local pf_wind_gust = ProtoField.float("fiitmeteo.wind_gust", "Wind Gust (m/s)")
local pf_wind_direction = ProtoField.uint16("fiitmeteo.wind_direction", "Wind Direction (°)")
local pf_turbulence = ProtoField.float("fiitmeteo.turbulence", "Turbulence")

-- RainDetect fields
local pf_rainfall = ProtoField.float("fiitmeteo.rainfall", "Rainfall (mm)")
local pf_soil_moisture = ProtoField.float("fiitmeteo.soil_moisture", "Soil Moisture (%)")
local pf_flood_risk = ProtoField.uint8("fiitmeteo.flood_risk", "Flood Risk Level")
local pf_rain_duration = ProtoField.uint16("fiitmeteo.rain_duration", "Rain Duration (min)")

-- AirQualityBox fields
local pf_co2 = ProtoField.uint16("fiitmeteo.co2", "CO2 (ppm)")
local pf_ozone = ProtoField.float("fiitmeteo.ozone", "Ozone (µg/m³)")
local pf_aqi = ProtoField.uint16("fiitmeteo.aqi", "Air Quality Index")

-- Register all fields
fiitmeteo_protocol.fields = {
    pf_msg_type, pf_device_type, pf_flags, pf_battery_low, pf_ctrl_subtype,
    pf_timestamp, pf_token, pf_crc, pf_error_code,
    pf_temperature, pf_humidity, pf_dew_point, pf_pressure,
    pf_wind_speed, pf_wind_gust, pf_wind_direction, pf_turbulence,
    pf_rainfall, pf_soil_moisture, pf_flood_risk, pf_rain_duration,
    pf_co2, pf_ozone, pf_aqi
}

-- Helper function to read signed 16-bit big-endian
local function read_int16_be(buffer, offset)
    local value = buffer(offset, 2):uint()
    if value >= 0x8000 then
        value = value - 0x10000
    end
    return value
end

-- Dissector function
function fiitmeteo_protocol.dissector(buffer, pinfo, tree)
    local length = buffer:len()
    if length < 5 then return end

    pinfo.cols.protocol = fiitmeteo_protocol.name

    local subtree = tree:add(fiitmeteo_protocol, buffer(), "FIITMeteo Protocol Data")

    -- Parse header
    local byte0 = buffer(0, 1):uint()
    local msg_type = bit.rshift(bit.band(byte0, 0xC0), 6)
    local device_type = bit.rshift(bit.band(byte0, 0x30), 4)
    local flags = bit.band(byte0, 0x0F)

    local header_tree = subtree:add(buffer(0, 5), "Header")
    header_tree:add(pf_msg_type, buffer(0, 1))
    header_tree:add(pf_device_type, buffer(0, 1))

    local timestamp = buffer(1, 4):uint()
    header_tree:add(pf_timestamp, buffer(1, 4))

    -- Device name mapping
    local device_names = {"ThermoNode", "WindSense", "RainDetect", "AirQualityBox"}
    local device_name = device_names[device_type + 1] or "Unknown"

    -- Message type processing
    if msg_type == 0 then
        -- REGISTER
        pinfo.cols.info = "REGISTER from " .. device_name
        header_tree:add(pf_flags, buffer(0, 1))

    elseif msg_type == 1 then
        -- REGISTER_ACK
        if length >= 9 then
            local token = buffer(5, 4):uint()
            subtree:add(pf_token, buffer(5, 4))
            pinfo.cols.info = "REGISTER_ACK for " .. device_name .. " (Token: " .. token .. ")"
        end

    elseif msg_type == 2 then
        -- DATA
        if length >= 14 then
            local battery_low = bit.band(flags, 0x01) == 1
            header_tree:add(pf_battery_low, buffer(0, 1))

            local token = buffer(5, 4):uint()
            subtree:add(pf_token, buffer(5, 4))

            local data_tree = subtree:add(buffer(9, length - 13), "Device Data")

            -- Parse device-specific data
            if device_type == 0 and length >= 22 then
                -- ThermoNode (8 bytes payload)
                local temp = read_int16_be(buffer, 9) / 10.0
                local hum = buffer(11, 2):uint() / 10.0
                local dew = read_int16_be(buffer, 13) / 10.0
                local press = (buffer(15, 2):uint() + 80000) / 100.0

                data_tree:add(pf_temperature, buffer(9, 2), temp)
                data_tree:add(pf_humidity, buffer(11, 2), hum)
                data_tree:add(pf_dew_point, buffer(13, 2), dew)
                data_tree:add(pf_pressure, buffer(15, 2), press)

                pinfo.cols.info = string.format("DATA from %s (T:%.1f°C H:%.1f%% P:%.2fhPa)%s",
                    device_name, temp, hum, press, battery_low and " [LOW BAT]" or "")

            elseif device_type == 1 and length >= 21 then
                -- WindSense (7 bytes payload)
                local speed = buffer(9, 2):uint() / 10.0
                local gust = buffer(11, 2):uint() / 10.0
                local direction = buffer(13, 2):uint()
                local turb = buffer(15, 1):uint() / 10.0

                data_tree:add(pf_wind_speed, buffer(9, 2), speed)
                data_tree:add(pf_wind_gust, buffer(11, 2), gust)
                data_tree:add(pf_wind_direction, buffer(13, 2))
                data_tree:add(pf_turbulence, buffer(15, 1), turb)

                pinfo.cols.info = string.format("DATA from %s (Speed:%.1fm/s Dir:%d° Gust:%.1fm/s)%s",
                    device_name, speed, direction, gust, battery_low and " [LOW BAT]" or "")

            elseif device_type == 2 and length >= 21 then
                -- RainDetect (7 bytes payload)
                local rain = buffer(9, 2):uint() / 10.0
                local moist = buffer(11, 2):uint() / 10.0
                local risk = buffer(13, 1):uint()
                local duration = buffer(14, 2):uint()

                data_tree:add(pf_rainfall, buffer(9, 2), rain)
                data_tree:add(pf_soil_moisture, buffer(11, 2), moist)
                data_tree:add(pf_flood_risk, buffer(13, 1))
                data_tree:add(pf_rain_duration, buffer(14, 2))

                pinfo.cols.info = string.format("DATA from %s (Rain:%.1fmm Moisture:%.1f%% Risk:%d)%s",
                    device_name, rain, moist, risk, battery_low and " [LOW BAT]" or "")

            elseif device_type == 3 and length >= 20 then
                -- AirQualityBox (6 bytes payload)
                local co2 = buffer(9, 2):uint()
                local ozone = buffer(11, 2):uint() / 10.0
                local aqi = buffer(13, 2):uint()

                data_tree:add(pf_co2, buffer(9, 2))
                data_tree:add(pf_ozone, buffer(11, 2), ozone)
                data_tree:add(pf_aqi, buffer(13, 2))

                pinfo.cols.info = string.format("DATA from %s (CO2:%dppm O3:%.1fµg/m³ AQI:%d)%s",
                    device_name, co2, ozone, aqi, battery_low and " [LOW BAT]" or "")
            end

            -- CRC
            subtree:add(pf_crc, buffer(length - 4, 4))
        end

    elseif msg_type == 3 then
        -- CONTROL
        local ctrl_subtype = flags
        header_tree:add(pf_ctrl_subtype, buffer(0, 1))

        if ctrl_subtype == 0 then
            pinfo.cols.info = "DATA_ACK to " .. device_name
        elseif ctrl_subtype == 1 then
            pinfo.cols.info = "PING to " .. device_name
        elseif ctrl_subtype == 2 then
            if length >= 9 then
                local token = buffer(5, 4):uint()
                subtree:add(pf_token, buffer(5, 4))
            end
            pinfo.cols.info = "PONG from " .. device_name
        elseif ctrl_subtype == 3 then
            if length >= 6 then
                subtree:add(pf_error_code, buffer(5, 1))
                local err_code = buffer(5, 1):uint()
                local err_names = {[0x01] = "INVALID_TOKEN", [0x02] = "CRC_FAIL", [0x03] = "INVALID_DATA"}
                pinfo.cols.info = "ERROR to " .. device_name .. " (" .. (err_names[err_code] or "Unknown") .. ")"
            end
        end
    end

    return length
end

-- Register the protocol on UDP port 9999
local udp_port = DissectorTable.get("udp.port")
udp_port:add(9999, fiitmeteo_protocol)

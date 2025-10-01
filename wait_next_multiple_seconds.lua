-- Copyright (c) 2025 Bundesanstalt für Materialforschung und -prüfung, see LICENSE file
-- based on example script by Yuri_Rage https://discuss.ardupilot.org/t/let-the-boat-drift-until-script-time-continues/108192/8
-- waits for the next multiple of seconds passed in as arg1 parameter and provides feedback to GCS as MAV_WAIT_REMAINING
local WAIT_CMD = 42
local DEFAULT_WAIT_S = 10  -- (s) wait until next X seconds (based on mod of unix timestamp)
local WAIT_MAV_NAME = 'WAIT_REMAINING'
local MAV_SEVERITY_NOTICE = 5
local MAV_SEVERITY_INFO = 6
local ROVER_MODE_AUTO = 10
local RUN_INTERVAL_IDLE_MS = 200
local RUN_INTERVAL_WAITING_MS = 10

local last_id = -1
local script_time_msn_index
local desired_wait_time_s = DEFAULT_WAIT_S
local target_millis = 0

function do_script_time()
    -- exit script time on waypoint change, mode change, or disarm
    if not arming:is_armed() or
       vehicle:get_mode() ~= ROVER_MODE_AUTO or
       mission:get_current_nav_index() ~= script_time_msn_index then

        vehicle:nav_script_time_done(last_id)
        desired_wait_time_s = DEFAULT_WAIT_S
        target_millis = 0
        gcs:send_text(MAV_SEVERITY_NOTICE, 'Wait script canceled!')
        return await_script_time, RUN_INTERVAL_IDLE_MS
    end

    -- compute remaining time and send to GCS
    local now = millis():tofloat()
    local wait_remaining_s = (target_millis - now) / 1000
    gcs:send_named_float(WAIT_MAV_NAME, wait_remaining_s)

    -- resume mission if wait time reaches zero
    if wait_remaining_s <= 0 then
        vehicle:nav_script_time_done(last_id)
        desired_wait_time_s = DEFAULT_WAIT_S
        target_millis = 0
        gcs:send_text(MAV_SEVERITY_NOTICE, 'Wait time reached. Resuming nav!')
        return await_script_time, RUN_INTERVAL_IDLE_MS -- go back to await routine
    end

    return do_script_time, RUN_INTERVAL_WAITING_MS -- queue next run of timer routine
end

function await_script_time()
    -- enter script time routine if WAIT_CMD is received
    -- first argument is modulo of unix timestamp to wait for in seconds
    local id, cmd, arg1, arg2, arg3, arg4 = vehicle:nav_script_time()
    if id and cmd == WAIT_CMD then
        if arg1 and arg1 > 0 then desired_wait_time_s = arg1 end
        last_id = id
        script_time_msn_index = mission:get_current_nav_index()

        -- calculate target timestamp (next multiple of desired_wait_time_s of millis())
        local now = millis():tofloat()
        local gps_time = gps:time_week_ms(0):tofloat() -- to have a common reference
        target_millis =  now + (desired_wait_time_s*1000 - (gps_time % (desired_wait_time_s*1000)))

        gcs:send_text(MAV_SEVERITY_NOTICE, ('Waiting for next multiple of %d seconds...'):format(desired_wait_time_s))
        return do_script_time, RUN_INTERVAL_WAITING_MS
    end

    -- report -1 for wait time if script time is inactive
    gcs:send_named_float(WAIT_MAV_NAME, -1)
    return await_script_time, RUN_INTERVAL_IDLE_MS
end

gcs:send_text(MAV_SEVERITY_INFO, 'Wait time script loaded')

return await_script_time()

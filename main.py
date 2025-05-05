# main.py
# Pulse Oximeter Main Routine for Raspberry Pi Pico W
# Reads SpO2 data using the MAX30101 sensor and sends average readings over BLE.
# Author: Parikshit Sah
# Date: May 5, 2025
#
# This script collects SpO2 readings, processes them, and sends the average value
# over BLE using the BLEHealthService. The average is sent after every 4 readings.

import time
from oximeter import (
    setup_max30101, get_ir_red_values, moving_average, calculate_variance,
    find_peaks, average_peak_difference, validate_peak_amplitudes
)
from lib.ble_health import BLEHealthService

if __name__ == "__main__":
    # Configuration parameters
    sample_time_s = 5  # Duration (seconds) for each sample window
    sample_len = 100 * sample_time_s  # Number of samples per window
    filter_window = 35  # Moving average window size
    peak_distance_threshold = 40  # Minimum distance between peaks
    spo2_reading = []  # List to store SpO2 readings

    # Initialize BLE health service
    ble = BLEHealthService()
    ble.setup(device_name="PicoW_Oximeter", interval_ms=500)

    if setup_max30101():
        time.sleep_ms(200)  # Wait for sensor to stabilize
        print("Sensor is ready.")
        while True:
            red_samples = []
            ir_samples = []
            # Collect samples for the defined window
            for i in range(0, sample_len):
                red_val, ir_val = get_ir_red_values()
                red_samples.append(red_val)
                ir_samples.append(ir_val)
                time.sleep_ms(10)  # Sampling interval
            # Calculate DC components
            ir_dc = sum(ir_samples) // len(ir_samples)
            red_dc = sum(red_samples) // len(red_samples)
            # Remove DC components
            processed_ir_samples = [num - ir_dc for num in ir_samples]
            processed_red_samples = [num - red_dc for num in red_samples]
            # Apply moving average filter
            moving_average_ir = moving_average(processed_ir_samples, sample_len, filter_window)
            moving_average_red = moving_average(processed_red_samples, sample_len, filter_window)
            # Check signal variance for validity
            ir_mavg_variance = calculate_variance(moving_average_ir)
            if not ir_mavg_variance <= 35000:
                print("IR moving average variance too high. Signal not valid.")
                continue
            if not 100 < ir_mavg_variance:
                print("IR moving average variance too low. Signal not valid.")
                continue
            # Find peaks in the filtered signals
            mavg_ir_len = len(moving_average_ir)
            mavg_red_len = len(moving_average_red)
            ir_peaks = find_peaks(moving_average_ir, mavg_ir_len, peak_distance_threshold)
            red_peaks = find_peaks(moving_average_red, mavg_red_len, peak_distance_threshold)
            # Validate peak amplitudes
            ir_peaks_valid_flag, valid_ir_peaks = validate_peak_amplitudes(moving_average_ir, ir_peaks)
            red_peaks_valid_flag, valid_red_peaks = validate_peak_amplitudes(moving_average_red, red_peaks)
            if not ir_peaks_valid_flag or not red_peaks_valid_flag:
                print("Peak amplitude variation too high. Signal not valid.")
                continue
            # Calculate average peak differences
            valid_red_peaks_len = len(valid_red_peaks)
            valid_ir_peaks_len = len(valid_ir_peaks)
            avg_ir_peak_diff = average_peak_difference(valid_ir_peaks, valid_ir_peaks_len)
            avg_red_peak_diff = average_peak_difference(valid_red_peaks, valid_red_peaks_len)
            # Calculate AC components
            ir_ac = float(avg_ir_peak_diff * (sample_time_s / sample_len))
            red_ac = float(avg_red_peak_diff * (sample_time_s / sample_len))
            # Calculate ratios
            ir_ratio = ir_ac / ir_dc
            red_ratio = red_ac / red_dc
            ratio_of_ratio = red_ratio / ir_ratio
            # Calculate SpO2
            spo2 = 110 - 25 * ratio_of_ratio
            print(f"calculated spo2: {spo2:.2f}")
            spo2_reading.append(spo2)
            avg_spo2 = sum(spo2_reading) / len(spo2_reading)
            print(f"average spo2 from this session: {avg_spo2:.2f}")
            # Send average SpO2 over BLE after every 4 readings
            if len(spo2_reading) % 4 == 0:
                ble.send_values(int(round(avg_spo2)), 0)  # BPM is 0 for now
            print(f"--" * 20)
    else:
        print("Failed to initialize MAX30101. Check wiring and power.")

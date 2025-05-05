# Pulse Oximeter with BLE for Raspberry Pi Pico W

**Author:** Parikshit Sah
**Date:** May 5th, 2025

---

## Overview

This project implements a wireless pulse oximeter using the MAX30101 sensor and a Raspberry Pi Pico W. It reads SpO2 (blood oxygen saturation) and pulse data, processes the signals, and transmits the results over Bluetooth Low Energy (BLE) to a mobile device or computer.

- **SpO2 and BPM Calculation:** Signal processing and peak detection are used to compute SpO2 and heart rate (BPM).
- **BLE Transmission:** Results are sent wirelessly using a custom BLE health service.
- **MicroPython:** All code is written for MicroPython running on the Pico W.

---

## Directory Structure

```
├── ble_test.py
├── lib
│   ├── ble_advertising.py
│   ├── ble_health.py
│   └── oximeter.py
├── main.py
├── README.md
├── Steph finger white.png
└── steph white finger.png
```

---

## File Descriptions

### main.py

- Runs the main oximeter routine.
- Reads data from the MAX30101 sensor, processes it, and calculates SpO2 and BPM.
- Sends average SpO2 and BPM over BLE after every 4 readings using the BLEHealthService.

> **Note: The program currently uses custom (non-standard) BLE Service and Characteristic UUIDs, not the official Bluetooth SIG Pulse Oximeter UUIDs.**

### ble_test.py

- Example script to demonstrate the BLE health service.
- Sends random SpO2 and BPM values over BLE for testing.

### lib/oximeter.py

- Handles I2C communication with the MAX30101 sensor.
- Implements signal processing: DC removal, moving average, peak detection, SpO2 and BPM calculation.

### lib/ble_health.py

- Implements a BLE service with custom characteristics for SpO2 and BPM.
- Handles BLE advertising, connections, and notifications.

### lib/ble_advertising.py

- Helper functions for building BLE advertising payloads.

---

## Hardware Requirements

- Raspberry Pi Pico W
- MAX30101 Pulse Oximeter Sensor

---

## Usage

1. **Flash MicroPython** onto your Pico W if not already done.
2. **Copy the repository files** to your Pico W (using Thonny, rshell, or similar).
3. **Connect the MAX30101 sensor** to the Pico W via I2C (default: SDA=16, SCL=17).
4. **Run `main.py`** to start reading and broadcasting SpO2/BPM.
5. **Use a BLE app** (e.g., nRF Connect) to scan and connect to the device. Look for `PicoW_Oximeter`.
6. **Optionally, run `ble_test.py`** to test BLE functionality with random data.

---

## Signal Processing & Calculation

- **Moving Average Filter:** Smooths the raw IR/RED signals.
- **Peak Detection:** Identifies heartbeats in the filtered signal.
- **SpO2 Calculation:** Uses the ratio of ratios method from [DOI 10.1088/0967-3334/27/1/R01](https://iopscience.iop.org/article/10.1088/0967-3334/27/1/R01)
- **BPM Calculation:** Based on the average interval between detected peaks.

---

## Customization

- Adjust sample window, filter size, and thresholds in `main.py` and `oximeter.py` for your use case.
- BLE device name and advertising interval can be set in `main.py` and `ble_health.py`.

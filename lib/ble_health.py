# ble_health.py
# MicroPython module for Raspberry Pi Pico W
# Provides a BLE service with two characteristics (PulseOx and BPM) for sending integer values via notifications.
# Designed to be imported and used in other programs.

import bluetooth
import time
import struct
from micropython import const

# BLE UUIDs and constants
_SERVICE_UUID = bluetooth.UUID("12345678-1234-5678-1234-56789abcdef0")
_PULSEOX_UUID = bluetooth.UUID("12345678-1234-5678-1234-56789abcdef1")  # For Pulse Oximetry (SpO2)
_BPM_UUID = bluetooth.UUID("12345678-1234-5678-1234-56789abcdef2")      # For Beats Per Minute (Heart Rate)

# Advertising payload constants
_ADV_TYPE_FLAGS = const(0x01)
_ADV_TYPE_NAME = const(0x09)

# BLE flags for advertising payload
_FLAG_GENERAL_DISCOVERABLE = const(0x02)
_FLAG_BR_EDR_NOT_SUPPORTED = const(0x04)

# --- Helper function to build advertising payload ---
def _advertising_payload(limited_discoverable=False, br_edr_not_supported=True, name=None):
    """
    Internal function to generate a BLE advertising payload.
    """
    payload = bytearray()

    def _append(adv_type, value):
        nonlocal payload
        payload += struct.pack("BB", len(value) + 1, adv_type) + value

    # Append Flags
    flags = 0
    if limited_discoverable:
        flags |= 0x01
    else:
        flags |= _FLAG_GENERAL_DISCOVERABLE
    if br_edr_not_supported:
        flags |= _FLAG_BR_EDR_NOT_SUPPORTED
    _append(_ADV_TYPE_FLAGS, struct.pack("B", flags))

    # Append Name
    if name:
        _append(_ADV_TYPE_NAME, name.encode())

    return payload

# --- BLE Health Service Class ---
class BLEHealthService:
    def __init__(self):
        self._ble = bluetooth.BLE()
        self._connections = set()
        self._is_setup = False
        self._pulseox_handle = None
        self._bpm_handle = None

    def setup(self, device_name="PicoW_BLE_Health", interval_ms=500):
        """
        Set up the BLE service with the specified device name and advertising interval.
        
        Args:
            device_name (str): Name of the device for advertising. Defaults to "PicoW_BLE_Health".
            interval_ms (int): Advertising interval in milliseconds. Defaults to 500ms.
        Returns:
            bool: True if setup is successful, False otherwise.
        """
        if self._is_setup:
            print("BLE service already set up.")
            return True

        try:
            # Activate BLE if not already active
            if not self._ble.active():
                print("Activating BLE...")
                self._ble.active(True)
            print("BLE Active.")

            # Register the GATT service with two characteristics
            services = (
                (_SERVICE_UUID, (
                    (_PULSEOX_UUID, bluetooth.FLAG_READ | bluetooth.FLAG_WRITE | bluetooth.FLAG_NOTIFY),
                    (_BPM_UUID, bluetooth.FLAG_READ | bluetooth.FLAG_WRITE | bluetooth.FLAG_NOTIFY),
                )),
            )
            handles = self._ble.gatts_register_services(services)
            self._pulseox_handle = handles[0][0]  # Handle for PulseOx characteristic
            self._bpm_handle = handles[0][1]      # Handle for BPM characteristic
            print(f"PulseOx characteristic handle: {self._pulseox_handle}")
            print(f"BPM characteristic handle: {self._bpm_handle}")

            # Set up IRQ handler for BLE events
            self._ble.irq(self._bt_irq)

            # Construct and start advertising
            interval_us = interval_ms * 1000  # Convert ms to microseconds
            payload = _advertising_payload(name=device_name)
            print(f"Starting advertising every {interval_ms} ms...")
            self._ble.gap_advertise(interval_us, adv_data=payload, connectable=True) #type: ignore

            self._is_setup = True
            return True
        except Exception as e:
            print(f"Error during BLE setup: {e}")
            self._is_setup = False
            return False

    def send_values(self, pulseox_value, bpm_value):
        """
        Send values for PulseOx and BPM characteristics via notifications.
        
        Args:
            pulseox_value (int): Value for PulseOx (SpO2), will be packed as a single byte.
            bpm_value (int): Value for BPM (Heart Rate), will be packed as a single byte.
        Returns:
            bool: True if values are sent successfully, False otherwise.
        """
        if not self._is_setup:
            print("BLE service not set up. Call setup() first.")
            return False

        try:
            # Convert integers to single bytes
            pulseox_data = struct.pack("B", pulseox_value)
            bpm_data = struct.pack("B", bpm_value)

            # Update characteristic values
            self._ble.gatts_write(self._pulseox_handle, pulseox_data) #type: ignore
            self._ble.gatts_write(self._bpm_handle, bpm_data) #type: ignore
            print(f"Updated PulseOx value: {pulseox_value}")
            print(f"Updated BPM value: {bpm_value}")

            # Send notifications to connected clients
            for conn_handle in self._connections:
                try:
                    self._ble.gatts_notify(conn_handle, self._pulseox_handle, pulseox_data) #type: ignore
                    self._ble.gatts_notify(conn_handle, self._bpm_handle, bpm_data) #type: ignore
                    print(f"Sent notifications to {conn_handle} - PulseOx: {pulseox_value}, BPM: {bpm_value}")
                except Exception as e:
                    print(f"Error sending notifications to {conn_handle}: {e}")

            return True
        except Exception as e:
            print(f"Error sending values: {e}")
            return False

    def _bt_irq(self, event, data):
        """
        Internal IRQ handler for BLE events.
        """
        if event == 1:  # _IRQ_CENTRAL_CONNECT
            conn_handle, _, _ = data
            self._connections.add(conn_handle)
            print(f"Device connected: {conn_handle}")
        elif event == 2:  # _IRQ_CENTRAL_DISCONNECT
            conn_handle, _, reason = data
            self._connections.remove(conn_handle)
            print(f"Device disconnected: {conn_handle}, Reason: {reason}")
        elif event == 5:  # _IRQ_GATTS_WRITE
            value_handle = data[2]
            if value_handle == self._pulseox_handle:
                value = self._ble.gatts_read(value_handle)
                print(f"Received write on PulseOx characteristic: {value}")
            elif value_handle == self._bpm_handle:
                value = self._ble.gatts_read(value_handle)
                print(f"Received write on BPM characteristic: {value}")

    def is_setup(self):
        """
        Check if the BLE service is set up.
        
        Returns:
            bool: True if set up, False otherwise.
        """
        return self._is_setup

    def stop(self):
        """
        Stop advertising and deactivate BLE.
        
        Returns:
            bool: True if stopped successfully, False otherwise.
        """
        try:
            self._ble.gap_advertise(None) #type: ignore
            self._ble.active(False)
            self._is_setup = False
            self._connections.clear()
            print("BLE stopped and deactivated.")
            return True
        except Exception as e:
            print(f"Error stopping BLE: {e}")
            return False

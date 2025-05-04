"""
BLE Advertising Helper Module for Pulse Oximetry

This module implements Bluetooth Low Energy (BLE) advertising and data transmission
for a pulse oximeter sensor. It provides classes and functions to:
- Generate and decode BLE advertising payloads
- Handle BLE connections and notifications
- Transmit pulse oximetry data (SpO2 and pulse rate) over BLE

Follows Bluetooth SIG Pulse Oximeter Service (0x1822) specification.

Modified By: Parikshit Sah
Date Modified: 11/4/2024
"""

from micropython import const
import struct
import bluetooth
import ubinascii

# BLE Advertisement Type Constants
_ADV_TYPE_FLAGS = const(0x01)
_ADV_TYPE_NAME = const(0x09)
_ADV_TYPE_UUID16_COMPLETE = const(0x3)
_ADV_TYPE_UUID32_COMPLETE = const(0x5)
_ADV_TYPE_UUID128_COMPLETE = const(0x7)
_ADV_TYPE_UUID16_MORE = const(0x2)
_ADV_TYPE_UUID32_MORE = const(0x4)
_ADV_TYPE_UUID128_MORE = const(0x6)
_ADV_TYPE_APPEARANCE = const(0x19)

# BLE Event Constants
_IRQ_CENTRAL_CONNECT = const(1)
_IRQ_CENTRAL_DISCONNECT = const(2)
_IRQ_GATTS_INDICATE_DONE = const(20)

# GATT Characteristic Flags
_FLAG_READ = const(0x0002)
_FLAG_NOTIFY = const(0x0010)
_FLAG_INDICATE = const(0x0020)

# Pulse Oximeter Service and Characteristics (official UUIDs)
_PULSE_OXIMETER_SERVICE_UUID = bluetooth.UUID(0x1822)
_PLX_SPOT_CHECK_CHAR_UUID = bluetooth.UUID(0x2A5E)
_PLX_CONTINUOUS_CHAR_UUID = bluetooth.UUID(0x2A5F)
_PLX_FEATURES_CHAR_UUID = bluetooth.UUID(0x2A60)

_PLX_SPOT_CHECK_CHAR = (_PLX_SPOT_CHECK_CHAR_UUID, _FLAG_INDICATE)
_PLX_CONTINUOUS_CHAR = (_PLX_CONTINUOUS_CHAR_UUID, _FLAG_NOTIFY)
_PLX_FEATURES_CHAR = (_PLX_FEATURES_CHAR_UUID, _FLAG_READ)

_PULSE_OXIMETER_SERVICE = (
    _PULSE_OXIMETER_SERVICE_UUID,
    (_PLX_SPOT_CHECK_CHAR, _PLX_CONTINUOUS_CHAR, _PLX_FEATURES_CHAR),
)

# Appearance value for generic pulse oximeter (using generic pulse oximeter if available, else thermometer)
_ADV_APPEARANCE_GENERIC_PULSE_OXIMETER = const(768)

class BLEPulseOximeter:
    """Class to handle BLE operations for pulse oximeter sensor"""

    def __init__(self, ble, name=""):
        """Initialize BLE with optional custom name"""
        self._ble = ble
        self._ble.active(True)
        self._ble.irq(self._irq)

        # Register only the pulse oximetry service
        ((self._handle_spot_check, self._handle_continuous, self._handle_features),) = \
            self._ble.gatts_register_services((_PULSE_OXIMETER_SERVICE,))

        self._connections = set()
        if len(name) == 0:
            name = 'Oximeter %s' % ubinascii.hexlify(self._ble.config('mac')[1],':').decode().upper()
        print('Sensor name %s' % name)

        self._payload = advertising_payload(name=name, services=[_PULSE_OXIMETER_SERVICE_UUID])
        self._advertise()

    def _irq(self, event, data):
        """Handle BLE events (connections, disconnections, etc)"""
        if event == _IRQ_CENTRAL_CONNECT:
            conn_handle, _, _ = data
            self._connections.add(conn_handle)
        elif event == _IRQ_CENTRAL_DISCONNECT:
            conn_handle, _, _ = data
            self._connections.remove(conn_handle)
            self._advertise()  # Restart advertising
        elif event == _IRQ_GATTS_INDICATE_DONE:
            conn_handle, value_handle, status = data

    def update_spot_check(self, spo2, pulse_rate, notify=False, indicate=True):
        """Update Spot-Check characteristic and indicate if requested"""
        # Format: [flags (1 byte), SpO2 (2 bytes), Pulse Rate (2 bytes)]
        # For simplicity, flags=0, SpO2 and pulse_rate as uint16 (x100 for 2 decimals)
        print("Indicate Spot-Check: SpO2 %.2f%%, Pulse %.2f bpm" % (spo2, pulse_rate))
        data = struct.pack("<BHH", 0, int(spo2 * 100), int(pulse_rate * 100))
        self._ble.gatts_write(self._handle_spot_check, data)
        if indicate:
            for conn_handle in self._connections:
                self._ble.gatts_indicate(conn_handle, self._handle_spot_check)

    def update_continuous(self, spo2, pulse_rate, notify=True):
        """Update Continuous characteristic and notify if requested"""
        # Format: [flags (1 byte), SpO2 (2 bytes), Pulse Rate (2 bytes)]
        print("Notify Continuous: SpO2 %.2f%%, Pulse %.2f bpm" % (spo2, pulse_rate))
        data = struct.pack("<BHH", 0, int(spo2 * 100), int(pulse_rate * 100))
        if notify:
            for conn_handle in self._connections:
                self._ble.gatts_notify(conn_handle, self._handle_continuous, data)

    def update_features(self, features_value):
        """Update Features characteristic (read-only, set once)"""
        # Features is a bitfield, for now just write as uint32
        print("Set Features: 0x%08X" % features_value)
        self._ble.gatts_write(self._handle_features, struct.pack("<I", features_value))

    def _advertise(self, interval_us=500000):
        """Start BLE advertising with specified interval"""
        self._ble.gap_advertise(interval_us, adv_data=self._payload)

# Generate a payload to be passed to gap_advertise(adv_data=...).
def advertising_payload(limited_disc=False, br_edr=False, name=None, services=None, appearance=0):
    payload = bytearray()

    def _append(adv_type, value):
        nonlocal payload
        payload += struct.pack("BB", len(value) + 1, adv_type) + value

    _append(
        _ADV_TYPE_FLAGS,
        struct.pack("B", (0x01 if limited_disc else 0x02) + (0x18 if br_edr else 0x04)),
    )

    if name:
        _append(_ADV_TYPE_NAME, name)

    if services:
        for uuid in services:
            b = bytes(uuid)
            if len(b) == 2:
                _append(_ADV_TYPE_UUID16_COMPLETE, b)
            elif len(b) == 4:
                _append(_ADV_TYPE_UUID32_COMPLETE, b)
            elif len(b) == 16:
                _append(_ADV_TYPE_UUID128_COMPLETE, b)

    # See org.bluetooth.characteristic.gap.appearance.xml
    if appearance:
        _append(_ADV_TYPE_APPEARANCE, struct.pack("<h", appearance))

    return payload


def decode_field(payload, adv_type):
    i = 0
    result = []
    while i + 1 < len(payload):
        if payload[i + 1] == adv_type:
            result.append(payload[i + 2 : i + payload[i] + 1])
        i += 1 + payload[i]
    return result


def decode_name(payload):
    n = decode_field(payload, _ADV_TYPE_NAME)
    return str(n[0], "utf-8") if n else ""


def decode_services(payload):
    services = []
    for u in decode_field(payload, _ADV_TYPE_UUID16_COMPLETE):
        services.append(bluetooth.UUID(struct.unpack("<h", u)[0]))
    for u in decode_field(payload, _ADV_TYPE_UUID32_COMPLETE):
        services.append(bluetooth.UUID(struct.unpack("<d", u)[0]))
    for u in decode_field(payload, _ADV_TYPE_UUID128_COMPLETE):
        services.append(bluetooth.UUID(u))
    return services


def run():
    payload = advertising_payload(
        name="PulseOx",
        services=[bluetooth.UUID(0x1822)],
    )
    print(payload)
    print(decode_name(payload))
    print(decode_services(payload))


if __name__ == "__main__":
    run()
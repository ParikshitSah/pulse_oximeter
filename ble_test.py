# main.py
# Example script demonstrating usage of ble_health module

import time
import random

# micropython looks in the lib directory for modules by default
from ble_health import BLEHealthService #type: ignore

# Create an instance of the BLE health service
ble_service = BLEHealthService()

# Set up the BLE service with a custom device name
if ble_service.setup(device_name="MyHealthDevice", interval_ms=500):
    print("BLE setup successful. Starting data transmission...")
    
    # Loop to send random values for PulseOx and BPM
    while True:
        try:
            # Generate random values for PulseOx (90-100) and BPM (50-120)
            pulseox = random.randint(90, 100)
            bpm = random.randint(50, 120)
            
            # Send the values via BLE notifications
            ble_service.send_values(pulseox, bpm)
            
            # Wait before sending the next set of values
            time.sleep(2)
        except Exception as e:
            print(f"Error in main loop: {e}")
            ble_service.stop()
            break
else:
    print("BLE setup failed. Check hardware or configuration.")

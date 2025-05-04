# main.py
import sys
import random
import struct
import uasyncio as asyncio
import aioble
import bluetooth
from machine import Pin

# Optional: Onboard LED to show status
led = Pin("LED", Pin.OUT)

# Define UUIDs for the Pulse Oximeter Service and Characteristics
# Standard UUID for Pulse Oximeter Service
_PLX_SERVICE_UUID = bluetooth.UUID(0x1822) 
# Standard UUID for PLX Continuous Measurement Characteristic
_PLX_CONTINUOUS_MEAS_CHAR_UUID = bluetooth.UUID(0x2A5F) 
# Standard UUID for PLX Spot-Check Measurement Characteristic
_PLX_SPOT_CHECK_MEAS_CHAR_UUID = bluetooth.UUID(0x2A5E) 

# Dummy data generation parameters
SPO2_RANGE = (95, 99) # Realistic SpO2 (%)
PR_RANGE = (60, 110)  # Realistic Pulse Rate (bpm)
CONTINUOUS_INTERVAL_MS = 2000 # Send continuous data every 2 seconds
SPOT_CHECK_INTERVAL_MS = 10000 # Simulate a spot check every 10 seconds

# Create the BLE service and characteristics
plx_service = aioble.Service(_PLX_SERVICE_UUID)

# Continuous Measurement Characteristic (Supports Notification)
continuous_char = aioble.Characteristic(
    plx_service, _PLX_CONTINUOUS_MEAS_CHAR_UUID, read=True, notify=True
)

# Spot-Check Measurement Characteristic (Supports Indication)
spot_check_char = aioble.Characteristic(
    plx_service, _PLX_SPOT_CHECK_MEAS_CHAR_UUID, read=True, indicate=True
)

# --- Simulation Tasks ---

async def simulate_continuous_data(connection):
    """Task to simulate and send continuous pulse oximeter data."""
    print("Starting continuous data simulation")
    while connection.is_connected():
        try:
            # Generate dummy data
            spo2 = random.randint(SPO2_RANGE[0], SPO2_RANGE[1])
            pulse_rate = random.randint(PR_RANGE[0], PR_RANGE[1])

            # Pack data (simple format: SpO2 as 1 byte, Pulse Rate as 1 byte)
            # Note: The official spec uses a more complex format (flags, floats, etc.)
            # This is a simplified version for demonstration.
            data = struct.pack("<BB", spo2, pulse_rate) 
            
            continuous_char.write(data, send_update=False) # Write locally first
            continuous_char.notify(connection) # Send notification to connected client
            print(f"Sent Continuous: SpO2={spo2}%, PR={pulse_rate} bpm")
            
            await asyncio.sleep_ms(CONTINUOUS_INTERVAL_MS)
        except Exception as e:
            print(f"Continuous data error: {e}")
            return # Exit task on error

async def simulate_spot_check_data(connection):
    """Task to simulate and send spot-check pulse oximeter data."""
    print("Starting spot-check data simulation")
    while connection.is_connected():
        try:
            await asyncio.sleep_ms(SPOT_CHECK_INTERVAL_MS) # Wait for interval

            # Generate dummy data
            spo2 = random.randint(SPO2_RANGE[0], SPO2_RANGE[1])
            pulse_rate = random.randint(PR_RANGE[0], PR_RANGE[1])

            # Pack data (simple format: SpO2 as 1 byte, Pulse Rate as 1 byte)
            data = struct.pack("<BB", spo2, pulse_rate)

            spot_check_char.write(data, send_update=False) # Write locally
            
            # Send indication (requires confirmation from client)
            # This will block until confirmation or timeout
            try:
                 await spot_check_char.indicate(connection)
                 print(f"Sent Spot-Check: SpO2={spo2}%, PR={pulse_rate} bpm")
            except asyncio.TimeoutError:
                 print("Spot-Check indication timeout")
            except Exception as e:
                 print(f"Spot-Check indication error: {e}")

        except Exception as e:
            print(f"Spot-check data error: {e}")
            return # Exit task on error


# --- Main Peripheral Task ---

async def peripheral_task():
    """Main task to handle BLE advertising and connections."""
    print("Registering PLX service...")
    aioble.register_services(plx_service)
    print("Service registered.")

    while True:
        led.off()
        print("Advertising...")
        try:
            async with await aioble.advertise(
                500000, # Advertising interval (ms)
                name="PicoW-PLX-Sim",
                services=[_PLX_SERVICE_UUID],
                appearance=833 # Pulse Oximeter Fingertip appearance code
            ) as connection:
                print(f"Connection from: {connection.device}")
                led.on() # Turn LED on when connected
                
                # Start simulation tasks concurrently
                continuous_task = asyncio.create_task(simulate_continuous_data(connection))
                spot_check_task = asyncio.create_task(simulate_spot_check_data(connection))

                # Keep running until disconnected
                await connection.disconnected() 

                # Cancel simulation tasks on disconnect
                continuous_task.cancel()
                spot_check_task.cancel()
                print("Disconnected.")

        except asyncio.CancelledError:
            print("Advertising cancelled.")
            return
        except Exception as e:
            print(f"Advertising error: {e}")
            await asyncio.sleep_ms(2000) # Wait before retrying


# Run the main peripheral task
try:
    print("Starting BLE Peripheral Task...")
    asyncio.run(peripheral_task())
except KeyboardInterrupt:
    print("Keyboard interrupt, stopping.")
except Exception as e:
    print(f"Main loop error: {e}")


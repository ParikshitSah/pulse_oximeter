# A quick way to plot reading: https://g.co/gemini/share/0f928ea2f9cd

import machine
import time

# --- Configuration ---
# I2C settings
I2C_ID = 0  # Pico W has I2C0 and I2C1
SCL_PIN = 17
SDA_PIN = 16
I2C_FREQ = 400000 # 400kHz, max for MAX30101

# MAX30101 I2C Address
# From datasheet page 5: Write Address AEh, Read Address AFh
# 7-bit address is AEh >> 1 = 57h
MAX30101_ADDR = 87

# MAX30101 Register Addresses (selected)
REG_INTR_STATUS_1 = 0x00
REG_INTR_ENABLE_1 = 0x02
REG_INTR_ENABLE_2 = 0x03
REG_FIFO_WR_PTR   = 0x04
REG_OVF_COUNTER   = 0x05
REG_FIFO_RD_PTR   = 0x06
REG_FIFO_DATA     = 0x07
REG_FIFO_CONFIG   = 0x08
REG_MODE_CONFIG   = 0x09
REG_SPO2_CONFIG   = 0x0A
REG_LED1_PA       = 0x0C # RED LED Pulse Amplitude
REG_LED2_PA       = 0x0D # IR LED Pulse Amplitude
REG_PART_ID       = 0xFF # Should read 0x15

# --- I2C Initialization ---
i2c = machine.I2C(I2C_ID, scl=machine.Pin(SCL_PIN), sda=machine.Pin(SDA_PIN), freq=I2C_FREQ)
print(i2c.scan()) # Scan for devices on the bus

# --- Helper Functions ---
def write_reg(reg_addr, value):
    """Write a byte to a specific register."""
    try:
        i2c.writeto_mem(MAX30101_ADDR, reg_addr, bytes([value]))
    except OSError as e:
        print(f"Error writing to I2C Addr {MAX30101_ADDR} Reg {reg_addr}: {e}")

def read_reg(reg_addr, n_bytes=1):
    """Read one or more bytes from a specific register."""
    try:
        return i2c.readfrom_mem(MAX30101_ADDR, reg_addr, n_bytes)
    except OSError as e:
        print(f"Error reading from I2C Addr {MAX30101_ADDR} Reg {reg_addr}: {e}")
        return None

# --- MAX30101 Initialization ---
def setup_max30101():
    print("Initializing MAX30101...")

    # Check if the device is present by reading Part ID
    part_id = read_reg(REG_PART_ID)
    if part_id is None or part_id[0] != 0x15:
        print(f"Error: MAX30101 not found or wrong Part ID (read: {part_id})")
        return False

    # Reset the sensor (Bit 6 of Mode Config)
    print("Resetting Sensor...")
    write_reg(REG_MODE_CONFIG, 0x40)
    time.sleep_ms(100) # Wait for reset

    # Clear FIFO pointers
    print("Clearing FIFO...")
    write_reg(REG_FIFO_WR_PTR, 0x00)
    write_reg(REG_OVF_COUNTER, 0x00)
    write_reg(REG_FIFO_RD_PTR, 0x00)

    # Configure FIFO: Sample Averaging=4, FIFO Rollover=On, FIFO Almost Full=17 samples
    # SMP_AVE[2:0] = 010 (4 samples) -> 0x40
    # FIFO_ROLLOVER_EN = 1 -> 0x10
    # FIFO_A_FULL[3:0] = 0 (trigger interrupt when 32-0=32 samples are in FIFO, we read before this)
    # 15 (trigger when 32-15 = 17 samples are waiting) -> 0x0F
    # Total = 0x40 | 0x10 | 0x0F = 0x5F
    # Using averaging = 1 (no average) for simplicity: 000 -> 0x00
    # Total = 0x00 | 0x10 | 0x0F = 0x1F
    print("Configuring FIFO...")
    write_reg(REG_FIFO_CONFIG, 0x1F) # No averaging, rollover enabled, Almost Full = 15

    # Configure Mode: SpO2 mode (Red + IR)
    # MODE[2:0] = 011 -> 0x03
    print("Setting SpO2 Mode...")
    write_reg(REG_MODE_CONFIG, 0x03)

    # Configure SpO2: ADC Range=4096nA, Sample Rate=100Hz, Pulse Width=411us (18-bit)
    # SPO2_ADC_RGE[1:0] = 01 (4096nA) -> 0x20
    # SPO2_SR[2:0] = 001 (100 samples per second) -> 0x04
    # LED_PW[1:0] = 11 (411us, 18-bit resolution) -> 0x03
    # Total = 0x20 | 0x04 | 0x03 = 0x27
    print("Configuring SpO2 ADC/Sample Rate/Pulse Width...")
    write_reg(REG_SPO2_CONFIG, 0x27)

    # Configure LED Pulse Amplitude (Current)
    # Set RED (LED1) and IR (LED2) to a moderate level (e.g., ~7.6mA = 0x24)
    # Refer to Table 8 in the datasheet for typical current values
    led_current = 0x24 # ~7.6mA 
    print(f"Setting LED currents (RED & IR) to register value: {hex(led_current)}")
    write_reg(REG_LED1_PA, led_current) # RED
    write_reg(REG_LED2_PA, led_current) # IR

    # Disable all interrupts (we will poll the FIFO)
    print("Disabling interrupts...")
    write_reg(REG_INTR_ENABLE_1, 0x00)
    write_reg(REG_INTR_ENABLE_2, 0x00)

    print("MAX30101 Initialization Complete.")
    return True



def find_peaks(arr, n, threshold):
  """
  Finds the indices of peaks in an array, ensuring a minimum distance between them.

  Args:
    arr: The input array (list or numpy array).
    n: The length of the input array.
    threshold: The minimum distance allowed between consecutive peaks.

  Returns:
    A list containing the indices of the peaks found in the array.
  """
  peaks = []
  # Iterate through the array elements, excluding the first and last
  for i in range(1, n - 1):
    # Check if the current element is greater than its neighbors
    if (arr[i] > arr[i - 1]) and (arr[i] > arr[i + 1]):
      # Check if this is the first peak found or if the distance
      # from the last found peak meets the threshold
      if len(peaks) == 0 or i - peaks[-1] >= threshold:
        peaks.append(i)
  return peaks
        

def moving_average(arr, n, k):
    """
    Applies a moving average filter to an array.

    Args:
      arr: The input array (list or numpy array).
      n: The length of the input array.
      k: The window size for the moving average.

    Returns:
      A new array containing the moving average of the input array.
    """
    if k <= 0:
        raise ValueError("Window size k must be positive")

    if k > n:
        raise ValueError("Window size k cannot be larger than the array length n")

    # Create an array to store the moving average values
    moving_averages = []

    # Calculate the moving average for each window
    for i in range(n - k + 1):
        # Calculate the sum of the current window
        values = [num//k for num in arr[i:i+k]]
        window_average = sum(values)

        # Calculate the average of the current window
        # window_average = window_sum / k

        # Append the average to the list of moving averages
        moving_averages.append(window_average)

    return moving_averages

def get_ir_red_values():
    # Read 6 bytes from FIFO (3 bytes for Red, 3 bytes for IR)

    fifo_data = read_reg(REG_FIFO_DATA, 6)

    if fifo_data is not None and len(fifo_data) == 6:
        # Combine bytes to get 18-bit Red value
        # Data is left-justified (MSB is always at bit 17)
        # Mask the first byte's upper 6 bits as they are unused (datasheet Table 1)
        red_val = ((fifo_data[0] & 0x03) << 16) | (fifo_data[1] << 8) | fifo_data[2]

        # Combine bytes to get 18-bit IR value
        ir_val = ((fifo_data[3] & 0x03) << 16) | (fifo_data[4] << 8) | fifo_data[5]

        return (ir_val, red_val)
    else:
        raise ValueError("Failed to read FIFO data.")

def average_peak_difference(arr, n) :
    """
    Calculates the average difference between consecutive elements in an array.
    Args:
        arr (list or sequence of int/float): The input array containing numerical values.
        n (int): The number of elements in the array to consider.
    Returns:
        int: The integer average of the differences between consecutive elements.
             Returns 0 if n is less than 2.
    Example:
        >>> average_peak_difference([1, 3, 6, 10], 4)
        3
    """
    diff = 0
    if n < 2 : return 0

    for i in range(1, n):
        diff = diff +  (arr[i] - arr[i-1])
    
    return diff // (n - 1)

def validate_peak_amplitudes(moving_average_signal, peak_indices, amplitude_variation_threshold=0.5):
    """
    Checks if each peak amplitude is within a threshold difference from the last peak.
    Returns True if valid, False otherwise.
    """
    if len(peak_indices) < 2:
        return False  # Not enough peaks to validate

    for i in range(1, len(peak_indices)):
        last_amp = moving_average_signal[peak_indices[i-1]]
        curr_amp = moving_average_signal[peak_indices[i]]
        if last_amp == 0:
            return False
        variation = abs(curr_amp - last_amp) / abs(last_amp)
        if variation > amplitude_variation_threshold:
            return False
    return True

# --- Main Loop ---

sample_time_s = 5
sample_len = 100 * sample_time_s
filter_window = 10
peak_distance_threshold = 40

if setup_max30101():
    # wait for sensor to reach equibrilium 
    time.sleep_ms(200)
    while True:
        red_samples = []
        ir_samples = []


        # Read samples for 5 seconds
        for i in range(0, sample_len):
            red_val, ir_val = get_ir_red_values()
            red_samples.append(red_val)
            ir_samples.append(ir_val)

            # we are reading 10 samples every 100ms which means we have 100 samples for each second
            time.sleep_ms(10)
        

        # calculate dc elements
        ir_dc = sum(ir_samples) // len(ir_samples)
        red_dc = sum(red_samples) // len(red_samples)

        print(f"ir dc: {ir_dc}")
        print(f"red dc: {red_dc}")

        # --- calculate AC component ---

        #remove dc components from the values
        processed_ir_samples = [num - ir_dc for num in ir_samples]
        processed_red_samples = [num - red_dc for num in red_samples]


        # calculate moving average
        moving_average_ir = moving_average(processed_ir_samples, sample_len, filter_window)
        moving_average_red = moving_average(processed_red_samples, sample_len, filter_window)

        processed_sample_len = len(moving_average_ir)

        print(f"moving average ir: {moving_average_ir}")
        print(f"processed ir samples: {processed_ir_samples}")
        print(f"actual ir samples: {ir_samples}")

        # find peaks
        ir_peaks = find_peaks(moving_average_ir, processed_sample_len, peak_distance_threshold)
        red_peaks = find_peaks(moving_average_red, processed_sample_len, peak_distance_threshold)
        print(f"ir peaks: {ir_peaks}")
        print(f"red peaks: {red_peaks}")
        # count peaks
        ir_peak_count =  len(ir_peaks)
        red_peak_count = len(red_peaks)
        print(f"ir peak count: {ir_peak_count}")

        # --- validate peaks before continuing ---
        if not validate_peak_amplitudes(moving_average_ir, ir_peaks):
            print("IR peak amplitude variation too high between consecutive peaks. Signal not valid.")
            continue
        if not validate_peak_amplitudes(moving_average_red, red_peaks):
            print("RED peak amplitude variation too high between consecutive peaks. Signal not valid.")
            continue

        # find the average peak difference 
        avg_ir_peak_diff = average_peak_difference(ir_peaks, ir_peak_count)
        avg_red_peak_diff = average_peak_difference(red_peaks, red_peak_count)

        print(f"avg ir peak diff: {avg_ir_peak_diff}")
        print(f"avg red peak diff: {avg_red_peak_diff}")

        # since 500 samples == 5 seconds, 1 sample is 5/500 is 0.01s or 10ms
        # this means that the avg peak diff is in multiples of 0.01s or 10ms
        # we need to convert it into seconds therefore
        ir_ac = float( avg_ir_peak_diff * (sample_time_s / sample_len)) 
        red_ac = float(avg_red_peak_diff * (sample_time_s / sample_len)) 

        print(f"ir ac: {ir_ac}")
        print(f"red ac: {red_ac}")


        # calculate ir ratio
        ir_ratio = ir_ac/ir_dc
        
        # calculate red ratio
        red_ratio = red_ac / red_dc

        print(f"ir ratio: {ir_ratio}")
        print(f"red ratio: {red_ratio}")

        # calculate R: ratio of ratio
        ratio_of_ratio = ir_ratio / red_ratio

        print(f"ratio of ratio: {ratio_of_ratio}")

        # calculate spo2
        spo2 = 110 - 25 * ratio_of_ratio
        print(f"calculated spo2: {spo2}")






else:
    print("Failed to initialize MAX30101. Check wiring and power.")

# Optional: Put sensor in shutdown mode at the end
# write_reg(REG_MODE_CONFIG, 0x80) # Set SHDN bit (Bit 7)
print("Program finished.")
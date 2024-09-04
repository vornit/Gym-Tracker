# Connect to Arduino Nano 33 IoT via bluetooth and get accelerometer data.

import time
import struct
from bluepy.btle import DefaultDelegate, Peripheral, UUID
import numpy as np
from edge_impulse_linux.runner import ImpulseRunner
from model_runner import run_inference
from scipy.signal import find_peaks
import matplotlib.pyplot as plt

SENSOR_SERVICE_UUID = "12345678-1234-1234-1234-123456789012"
SENSOR_CHAR_UUID = "87654321-4321-4321-4321-210987654321"

accelerometer_data = []
all_data = []

previous_exercises = ["stay","stay","stay","stay","stay"]
exercise_started = False
current_exercise_duration = 0

model_path = '/home/asdasd/projects/model.eim'
device_address = '84:CC:A8:78:D3:6E'

class NotificationDelegate(DefaultDelegate):
    def __init__(self, update_callback):
        super().__init__()
        self.update_callback = update_callback

    def handleNotification(self, cHandle, data):
        global accelerometer_data, previous_exercises, exercise_started, all_data, current_exercise_duration

        accelerometer_data3 = []
        set_length = ''
        exerciseStarted = False

        if len(data) == 12:
            ax, ay, az = struct.unpack('fff', data)
            ax = round(ax, 2)
            ay = round(ay, 2)
            az = round(az, 2)
            accelerometer_data.append(ax)
            accelerometer_data.append(ay)
            accelerometer_data.append(az)
            all_data.append(ax)
            all_data.append(ay)
            all_data.append(az)
            #print(f"ax: {ax}, ay: {ay}, az: {az}")

            if len(accelerometer_data) % 312 == 0:
                result = run_inference(model_path, features=accelerometer_data)
                accelerometer_data = []

                if result['result']['classification']["horizontal"] > 0.8:
                    new_exercises = ["horizontal"]
                    new_exercises.extend(previous_exercises[:4])
                    previous_exercises = new_exercises

                if result['result']['classification']["stay"] > 0.8:
                    new_exercises = ["stay"]
                    new_exercises.extend(previous_exercises[:4])
                    previous_exercises = new_exercises

                if result['result']['classification']["vertical"] > 0.8:
                    new_exercises = ["vertical"]
                    new_exercises.extend(previous_exercises[:4])
                    previous_exercises = new_exercises

                print (previous_exercises)

                if previous_exercises.count("horizontal") >= 3 and exercise_started == False:
                    print("horizontal started")
                    exercise_started = True
                    current_exercise_duration += 1
                elif previous_exercises.count("vertical") >= 3 and exercise_started == False:
                    print("vertical started")
                    exercise_started = True
                    current_exercise_duration += 1
                elif previous_exercises.count("horizontal") >= 3 and exercise_started == True:
                    print("horizontal continues")
                    current_exercise_duration += 1
                elif previous_exercises.count("vertical") >= 3 and exercise_started == True:
                    print("vertical continues")
                    current_exercise_duration += 1
                elif previous_exercises.count("stay") >= 3 and exercise_started == True:
                    print("exercise stopped")
                    exercise_started = False
                    slice_range = (current_exercise_duration + 6) * 312
                    current_exercise_duration = 0
                    all_data = all_data[-slice_range:]
                    np_data = np.array(all_data)

                    peaks, _ = find_peaks(np_data, height=12, distance=75, prominence=1)

                    print("Repetations:", len(peaks))

                    accelerometer_data3 = all_data.copy()
                    all_data.clear()

                    exerciseStarted = True

                    set_length = len(peaks)

                # Call the update callback to notify app.py
                if self.update_callback:
                    self.update_callback(accelerometer_data3, set_length, exerciseStarted)

def connect_to_device(device_address, stop_event, update_callback):
    print(f"Connecting to {device_address}...")
    try:
        peripheral = Peripheral(device_address)
        print("Connected!")
    except Exception as e:
        print(f"Failed to connect: {e}")
        return

    try:
        sensor_service = peripheral.getServiceByUUID(UUID(SENSOR_SERVICE_UUID))
        sensor_char = sensor_service.getCharacteristics(UUID(SENSOR_CHAR_UUID))[0]
    except Exception as e:
        print(f"Failed to find service or characteristic: {e}")
        return

    try:
        peripheral.setDelegate(NotificationDelegate(update_callback))
        peripheral.writeCharacteristic(sensor_char.getHandle() + 1, b'\x01\x00')  # Enable notifications
        print("Notifications enabled")
    except Exception as e:
        print(f"Failed to set notifications: {e}")
        return

    try:
        while not stop_event.is_set():
            if peripheral.waitForNotifications(1):  # 1-second timeout to check for notifications
                continue
    except KeyboardInterrupt:
        print("Disconnecting...")
    finally:
        peripheral.disconnect()
        print("Disconnected.")

    all_data.clear()
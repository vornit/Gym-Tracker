# Connect to Arduino Nano 33 IoT via bluetooth and get accelerometer data.

import time
import struct
from bluepy.btle import DefaultDelegate, Peripheral, UUID
import numpy as np
from edge_impulse_linux.runner import ImpulseRunner
from model_runner import run_inference

SENSOR_SERVICE_UUID = "12345678-1234-1234-1234-123456789012"
SENSOR_CHAR_UUID = "87654321-4321-4321-4321-210987654321"

accelerometer_data = []

detected_vertical = 0
detected_horizontal = 0
detected_stay = 0

model_path = '/home/asdasd/projects/model.eim'
device_address = '84:CC:A8:78:D3:6E'

class NotificationDelegate(DefaultDelegate):
    def __init__(self):
        DefaultDelegate.__init__(self)

    def handleNotification(self, cHandle, data):
        global accelerometer_data, detected_horizontal, detected_stay, detected_vertical

        if len(data) == 12:
            #print(data)
            ax, ay, az = struct.unpack('fff', data)
            ax = round(ax, 2)
            ay = round(ay, 2)
            az = round(az, 2)
            accelerometer_data.append(ax)
            accelerometer_data.append(ay)
            accelerometer_data.append(az)
            #print(f"ax: {ax}, ay: {ay}, az: {az}")

            if len(accelerometer_data) % 312 == 0:
                result = run_inference(model_path, features=accelerometer_data)
                print (result)
                accelerometer_data = []

                if result['result']['classification']["horizontal"] > 0.8:
                    detected_horizontal += 1

                if result['result']['classification']["stay"] > 0.8:
                    detected_stay += 1

                if result['result']['classification']["vertical"] > 0.8:
                    detected_vertical += 1

                print(f'horizontal: {detected_horizontal}')
                print(f'vertical: {detected_vertical}')
                print(f'stay: {detected_stay}')

def connect_to_device(device_address, stop_event):
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
        peripheral.setDelegate(NotificationDelegate())
        peripheral.writeCharacteristic(sensor_char.getHandle() + 1, b'\x01\x00')  # Enable notifications
        print("Notifications enabled")
    except Exception as e:
        print(f"Failed to set notifications: {e}")
        return

    try:
        while not stop_event.is_set():  # Check the stop_event to determine whether to continue
            if peripheral.waitForNotifications(1):  # 1-second timeout to check for notifications
                continue
    except KeyboardInterrupt:
        print("Disconnecting...")
    finally:
        peripheral.disconnect()
        print("Disconnected.")

    print(f"Number of accelerometer data points received: {len(accelerometer_data)}")
    print(accelerometer_data)

    accelerometer_data2 = accelerometer_data.copy()
    accelerometer_data.clear()  # Clear the global list
    return accelerometer_data2  # Return the data
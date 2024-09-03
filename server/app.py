import uuid
import threading
from flask import Flask, jsonify, request
from flask_cors import CORS
#from ble_tool import connect_to_device
from eim_ble_tool import connect_to_device
import time

app = Flask(__name__)
CORS(app)

stop_event = threading.Event()

accelerometer_data = []
chunked_accelerometer_data = []
scanning_on = False

def update_accelerometer_data(updated_sensor_data):
    global accelerometer_data
    accelerometer_data = updated_sensor_data

def background_sensor_task(device_address):
    global stop_event
    connect_to_device(device_address, stop_event, update_accelerometer_data)

@app.route('/stop_sensor', methods=['GET'])
def stop_sensor():
    global stop_event, scanning_on
    stop_event.set()
    scanning_on = False
    return jsonify({'status': 'Sensor data collection stopped'})

@app.route('/start_scanning', methods=['GET'])
def aaa():
    global stop_event, scanning_on, accelerometer_data

    if scanning_on == False:
        scanning_on = True
        if stop_event.is_set():
            stop_event.clear()
        device_address = '84:CC:A8:78:D3:6E'
        sensor_thread = threading.Thread(target=background_sensor_task, args=(device_address,))
        sensor_thread.daemon = True
        sensor_thread.start()

    return jsonify({'status': accelerometer_data})

if __name__ == '__main__':
    app.run(debug=True, port=5001)
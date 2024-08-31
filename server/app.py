import uuid
import threading
from flask import Flask, jsonify, request
from flask_cors import CORS
from ble_tool import connect_to_device

app = Flask(__name__)
CORS(app)


sensor_data = []
stop_event = threading.Event()

accelerometer_data = []


def background_sensor_task(device_address):
    global stop_event
    global accelerometer_data
    accelerometer_data = connect_to_device(device_address, stop_event)

@app.route('/start_sensor', methods=['GET'])
def start_sensor():
    global stop_event
    if stop_event.is_set():
        stop_event.clear()
    device_address = '84:CC:A8:78:D3:6E'
    sensor_thread = threading.Thread(target=background_sensor_task, args=(device_address,))
    sensor_thread.daemon = True
    sensor_thread.start()
    return jsonify({'status': 'Sensor data collection started'})

@app.route('/stop_sensor', methods=['GET'])
def stop_sensor():
    global stop_event
    stop_event.set()
    return jsonify({'status': 'Sensor data collection stopped'})

@app.route('/get_sensor_data', methods=['GET'])
def get_sensor_data():
    global accelerometer_data
    return jsonify({'sensor_data': accelerometer_data})

if __name__ == '__main__':
    app.run(debug=True, port=5001)
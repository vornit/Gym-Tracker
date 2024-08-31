import time
import numpy as np
from edge_impulse_linux.runner import ImpulseRunner
from ble_tool import connect_to_device

def run_inference(model_path, device_address=None, duration=5, features=None):
    # Ladataan malli ja ajetaan inferenssi
    runner = ImpulseRunner(model_path)

    try:
        model_info = runner.init()
        print('Model loaded successfully!')

        if features is None:
            if device_address is None:
                raise ValueError("Either features or device_address must be provided.")
            features = connect_to_device(device_address, duration=duration)

        horizon_count = 0
        stay_count = 0
        vertical_count = 0

        while len(features) > 0:
            
            expected_feature_count = model_info['model_parameters']['input_features_count']
            chunk = features[:expected_feature_count]

            #
            while len(chunk) < expected_feature_count:
                chunk.append(0)

            features = features[expected_feature_count:]

            try:
                result = runner.classify(chunk)
            except Exception as e:
                print(f"Error during classification: {str(e)}")
                print(f"Features: {chunk}")
                raise

            
            print("Predictions:")
            for label, score in result['result']['classification'].items():
                print(f'  {label}: {score:.5f}')

            if result['result']['classification']["horizon"] > 0.8:
                horizon_count += 1

            if result['result']['classification']["stay"] > 0.8:
                stay_count += 1

            if result['result']['classification']["vertical"] > 0.8:
                vertical_count += 1

            print(horizon_count)
            print(stay_count)
            print(vertical_count)

            time.sleep(0.4) 

        return vertical_count

    finally:
        runner.stop()

    return horizon_count
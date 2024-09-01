import time
import numpy as np
from edge_impulse_linux.runner import ImpulseRunner
from ble_tool import connect_to_device

def run_inference(model_path, features=None):

    try:

        runner = ImpulseRunner(model_path)

        model_info = runner.init()
    
        result = runner.classify(features)

        horizontal_count = 0
        stay_count = 0
        vertical_count = 0

        return result 

    finally:
        runner.stop()
<template>
  <div class="container">
    <div class="row">
      <div class="col-sm-10">
        <h1>Gym app</h1>
        <table class="table table-hover">
          <thead>
            <tr>
              <th scope="col">Exercise</th>
              <th scope="col">Set 1</th>
              <th scope="col">Set 2</th>
              <th scope="col">Set 3</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Bench</td>
              <td><input class="square-input"></td>
              <td><input class="square-input"></td>
              <td><input class="square-input"></td>
            </tr>
            <tr>
              <td>Squat</td>
              <td><input class="square-input"></td>
              <td><input class="square-input"></td>
              <td><input class="square-input"></td>
            </tr>
            <tr>
              <td>Pull-Up</td>
              <td><input class="square-input"></td>
              <td><input class="square-input"></td>
              <td><input class="square-input"></td>
            </tr>
          </tbody>
        </table>

        <div>
          <button type="button" class="btn btn-success btn-sm" @click="startSensor">
            Start scanning
          </button>
          <button type="button" class="btn btn-success btn-sm" @click="stopSensor">
            Stop scanning
          </button>
          <button type="button" class="btn btn-success btn-sm" @click="getSensorData">
            Print sensor data
          </button>
        </div>

        <div>
          <p style="display: flex; align-items: center;">
            <span style="width: 100px;">Features:</span>
            <input type="text" v-model="featuresInput" id="features" placeholder="Paste your features here"
              style="flex-grow: 1;" />
          </p>
          <p style="display: flex; align-items: center;">
            <span style="width: 100px;">Results:</span>
            <input type="text" :value="receivedSensorData[0]" readonly style="flex-grow: 1;" />
          </p>

          <p>
            <button @click="runInference">Run inference</button>
          </p>
          <p id="results">
          <pre>{{ results }}</pre>
          </p>
        </div>

      </div>
    </div>
  </div>
</template>

<script>
import axios from 'axios';

export default {
  data() {
    return {
      featuresInput: '',
      results: '',
      receivedSensorData: '',
      projectTitle: '',
      classifier: null,
      classifierInitialized: false,
    };
  },
  methods: {
    startSensor() {
      const path = 'http://localhost:5001/start_sensor';
      axios.get(path)
        .then((res) => {
          console.log(res.data.status);
        })
        .catch((error) => {
          console.error(`Error starting sensor: ${error}`);
        });
    },
    stopSensor() {
      const path = 'http://localhost:5001/stop_sensor';
      axios.get(path)
        .then((res) => {
          console.log(res.data.status);
          this.getSensorData();  // Fetch sensor data when stopping the sensor
        })
        .catch((error) => {
          console.error(`Error stopping sensor: ${error}`);
        });
    },
    getSensorData() {
      const path = 'http://localhost:5001/get_sensor_data';
      axios.get(path)
        .then((res) => {
          const fullSensorData = res.data.sensor_data;
          this.receivedSensorData = fullSensorData;
          console.log('Sensor data:', this.receivedSensorData);  // Print data to the console
        })
        .catch((error) => {
          console.error(`Error fetching sensor data: ${error}`);
        });
    },
    runInference() {
      if (!this.classifierInitialized) {
        alert('Classifier is not initialized yet.');
        return;
      }
      try {
        const features = this.featuresInput
          .split(',')
          .map((x) => Number(x.trim()));
        const res = this.classifier.classify(features);
        this.results = JSON.stringify(res, null, 4);
      } catch (ex) {
        alert('Failed to classify: ' + (ex.message || ex.toString()));
      }
    },
    runInference() {
      if (!this.classifierInitialized) {
        alert('Classifier is not initialized yet.');
        return;
      }
      try {
        const features = this.featuresInput
          .split(',')
          .map((x) => Number(x.trim()));
        const res = this.classifier.classify(features);
        this.results = JSON.stringify(res, null, 4);
      } catch (ex) {
        alert('Failed to classify: ' + (ex.message || ex.toString()));
      }
    },
  },
  mounted() {
    let edgeImpulseStandalone = document.createElement('script');
    edgeImpulseStandalone.setAttribute('src', 'static/edge-impulse-standalone.js');
    document.head.appendChild(edgeImpulseStandalone);

    edgeImpulseStandalone.onload = () => {
      let runImpulse = document.createElement('script');
      runImpulse.setAttribute('src', 'static/run-impulse.js');
      document.head.appendChild(runImpulse);

      runImpulse.onload = () => {
        this.classifier = new EdgeImpulseClassifier();
        this.classifier.init().then(() => {
          this.classifierInitialized = true;
          console.log('Classifier initialized.');
        });
      };
    };
  },
};
</script>

<style scoped>
.square-input {
  width: 50px;
  height: 50px;
  border-radius: 0;
  text-align: center;
  padding: 0;
}

.btn-success {
  margin-right: 18px;
  margin-bottom: 18px;
}
</style>

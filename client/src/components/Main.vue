<template>
  <div class="container">
    <TabsWrapper>
      <Tab title="Main">
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
              <button type="button" class="btn btn-success btn-sm" @click="startPolling">
                Start scanning
              </button>
              <button type="button" class="btn btn-success btn-sm" @click="stopSensor">
                Stop scanning
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
                <input type="text" :value="receivedSensorData" readonly style="flex-grow: 1;" />
              </p>

              <p>
                <button @click="runInference">Run inference</button>
              </p>

              <p>
                Set length: {{ results }}
              </p>

              <p>
                {{ storedRepetations }}
              </p>

            </div>
          </div>
        </div>
      </Tab>
      <Tab title="Tab22">
        <div class="row">
          <div class="col-sm-10">
            <h1>Gym app</h1>

            <div>
              <p style="display: flex; align-items: center;">
                <span style="width: 100px;">Features:</span>
                <input type="text" v-model="featuresInput" id="features" placeholder="Paste your features here"
                  style="flex-grow: 1;" />
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
      </Tab>
    </TabsWrapper>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue';
import axios from 'axios';
import TabsWrapper from './TabsWrapper.vue';
import Tab from './Tab.vue';

const featuresInput = ref('');
const results = ref('');
const receivedSensorData = ref('');
const projectTitle = ref('');
const classifier = ref(null);
const classifierInitialized = ref(false);
const pollingInterval = ref(null);
const storedRepetations = ref([])

const stopSensor = () => {
  const path = 'http://localhost:5001/stop_sensor';
  axios.get(path)
    .then((res) => {
      console.log(res.data.status);
      stopPolling();
    })
    .catch((error) => {
      console.error(`Error stopping sensor: ${error}`);
    });
};

const startPolling = () => {
  pollingInterval.value = setInterval(() => {
    const path = 'http://localhost:5001/start_scanning';
    axios.get(path)
      .then((res) => {
        const sensorData = res.data.status.sensor_data;
        const setLength = res.data.status.set_length;
        
        const valuesString = sensorData.join(', ');
        receivedSensorData.value = valuesString;  // Update with sensor data
        results.value = {setLength};  // Update with set length

        console.log(setLength);
        console.log(sensorData);
        if (setLength !== '' && sensorData.length > 0) {
          storedRepetations.value.push(setLength);
          console.log("AAAAAAAAAAA");
        }

        console.log(valuesString);
        console.log(`Set length: ${setLength}`);
      })
      .catch((error) => {
        console.error(`Error fetching sensor data: ${error.message || error}`);
      });
  }, 2000);  // Poll every 2 seconds
};

const stopPolling = () => {
  if (pollingInterval.value) {
    clearInterval(pollingInterval.value);
    pollingInterval.value = null;
  }
};

const runInference = () => {
  if (!classifierInitialized.value) {
    alert('Classifier is not initialized yet.');
    return;
  }
  try {
    const features = featuresInput.value
      .split(',')
      .map((x) => Number(x.trim()));
    const res = classifier.value.classify(features);
    results.value = JSON.stringify(res, null, 4);
  } catch (ex) {
    alert('Failed to classify: ' + (ex.message || ex.toString()));
  }
};

onMounted(() => {
  let edgeImpulseStandalone = document.createElement('script');
  edgeImpulseStandalone.setAttribute('src', 'static/edge-impulse-standalone.js');
  document.head.appendChild(edgeImpulseStandalone);

  edgeImpulseStandalone.onload = () => {
    let runImpulse = document.createElement('script');
    runImpulse.setAttribute('src', 'static/run-impulse.js');
    document.head.appendChild(runImpulse);

    runImpulse.onload = () => {
      classifier.value = new EdgeImpulseClassifier();
      classifier.value.init().then(() => {
        classifierInitialized.value = true;
        console.log('Classifier initialized.');
      });
    };
  };
});

// Clean up polling when the component is destroyed
onUnmounted(() => {
  stopPolling();
});
</script>

<style scoped>
.header-container {
  display: flex;
  align-items: center;
  margin-bottom: 20px;
}

.app-title {
  margin-left: 20px;
}

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
<template>
  <div class="container">
    <div class="row">
      <div class="col-sm-8">
        <TabsWrapper>
          <Tab title="Main">
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
                <tr v-for="(exercise, exerciseIndex) in exercises" :key="exerciseIndex">
                  <td>{{ exercise.name }}</td>
                  <td>
                    <input class="square-input" :value="getStoredValue(exerciseIndex * 3)" readonly />
                  </td>
                  <td>
                    <input class="square-input" :value="getStoredValue(exerciseIndex * 3 + 1)" readonly />
                  </td>
                  <td>
                    <input class="square-input" :value="getStoredValue(exerciseIndex * 3 + 2)" readonly />
                  </td>
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
                <span style="width: 100px;">Results:</span>
                <input type="text" :value="accelerometerData" readonly style="flex-grow: 1;" />
              </p>

              <div id="visualization">
                <Visualization :accelerometerData="accelerometerData" />
              </div>

              <p>Set length: {{ results }}</p>
              <p>{{ storedRepetations }}</p>
            </div>
          </Tab>

          <Tab title="Tab22">
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
          </Tab>
        </TabsWrapper>
      </div>

      <!-- Logging area -->
      <div class="col-sm-4">
        <h3>Logs:</h3>
        <div class="logging-area" ref="loggingArea">

          <div class="log-entry" v-for="log in logs" :key="log.id">
            <p>{{ log.timestamp }}: {{ log.message }}</p>
          </div>
        </div>

        <h3>5 recent model exercises:</h3>
        <div class="logging-area" ref="loggingArea">
          <div>
            <pre>{{ previousExercises[0] }}</pre>
            <pre>{{ previousExercises[1] }}</pre>
            <pre>{{ previousExercises[2] }}</pre>
            <pre>{{ previousExercises[3] }}</pre>
            <pre>{{ previousExercises[4] }}</pre>
          </div>
        </div>

        <h3>Latest model result:</h3>
        <pre>{{ modelResult }}</pre>
      </div>



    </div> <!-- Close the row div here -->
  </div>
</template>



<script setup>
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue';
import axios from 'axios';
import TabsWrapper from './TabsWrapper.vue';
import Tab from './Tab.vue';
import Visualization from './Visualization.vue';

const accelerometerData = ref('0,0,0,0,0,0,0,0,0');

const featuresInput = ref('');
const results = ref('');
const receivedSensorData = ref('');
const projectTitle = ref('');
const classifier = ref(null);
const classifierInitialized = ref(false);
const pollingInterval = ref(null);
const storedRepetations = ref([])
const exerciseNames = ['Bench', 'Squat', 'Pull-Up'];
const previousExercises = ref([]);
const modelResult = ref([]);

const logs = ref([]);
const loggingArea = ref(null);

const setLength = ref('');
const exerciseStarted = ref(false);
const sensorData = ref([]);

const addLog = (message) => {
  const timestamp = new Date().toLocaleTimeString();
  logs.value.push({ id: logs.value.length, message, timestamp });

  // Automatically scroll to the bottom when a log is added
  scrollToBottom();
};

const exercises = ref(exerciseNames.map((name, index) => ({
  name: name,
  set1: ref(index * 3 + 1),
  set2: ref(index * 3 + 2),
  set3: ref(index * 3 + 3)
})));

const getStoredValue = (index) => {
  return storedRepetations.value[index] !== undefined
    ? storedRepetations.value[index]
    : ''; // Empty if no value at this index
};

const stopSensor = () => {
  const path = 'http://localhost:5001/stop_sensor';
  axios.get(path)
    .then((res) => {
      addLog('Sensor stopped.');
      stopPolling();
    })
    .catch((error) => {
      addLog(`Error stopping sensor: ${error}`);
    });
};

const startPolling = () => {

  if (pollingInterval.value) {
    return;
  }

  if (!pollingInterval.value) {
    addLog('Sensor started.');

    pollingInterval.value = setInterval(() => {
      const path = 'http://localhost:5001/start_scanning';
      axios.get(path)
        .then((res) => {
          const sensorData = res.data.status.sensor_data;
          const setLength = res.data.status.set_length;
          const setStarted = res.data.status.exerciseStarted;
          previousExercises.value = res.data.status.previous_exercises;
          modelResult.value = res.data.status.result;

          console.log(modelResult);

          addLog(setStarted);

          //onsole.log(setLength);
          //onsole.log(sensorData);
          //onsole.log(exerciseStarted);
          console.log(previousExercises);

          if (setLength !== '' && sensorData.length > 0) {
            storedRepetations.value.push(setLength);
            const valuesString = sensorData.join(', ');
            accelerometerData.value = valuesString;
          }
        })
        .catch((error) => {
          console.error(`Error fetching sensor data: ${error.message || error}`);
        });
    }, 2000);
  }
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

const scrollToBottom = () => {
  nextTick(() => {
    if (loggingArea.value) {
      loggingArea.value.scrollTop = loggingArea.value.scrollHeight;
    }
  });
};

watch(logs, () => {
  scrollToBottom();
});

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
.logging-area {
  border: 1px solid #ccc;
  padding: 10px;
  height: 200px;
  margin-bottom: 10px;
  overflow-y: auto;
  background-color: #f9f9f9;
}

.log-entry {
  margin-bottom: 10px;
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
<template>
    <div id="visualization">
        <canvas id="accelerometerChart"></canvas>
    </div>
</template>

<script setup>
import { onMounted, watch } from 'vue';
import { Chart, LineController, LineElement, PointElement, LinearScale, Title, CategoryScale, Legend } from 'chart.js';

// Register Chart.js components including the Legend
Chart.register(LineController, LineElement, PointElement, LinearScale, Title, CategoryScale, Legend);

// Props to receive the accelerometer data from the parent
const props = defineProps({
    accelerometerData: {
        type: String,
        required: true
    }
});

const splitAccelerometerData = (dataString) => {
    const dataArray = dataString.split(',').map(Number);
    const xData = [];
    const yData = [];
    const zData = [];

    for (let i = 0; i < dataArray.length; i += 3) {
        xData.push(dataArray[i]);
        yData.push(dataArray[i + 1]);
        zData.push(dataArray[i + 2]);
    }

    return { xData, yData, zData };
};

let chartInstance;

onMounted(() => {
    const ctx = document.getElementById('accelerometerChart').getContext('2d');
    const { xData, yData, zData } = splitAccelerometerData(props.accelerometerData);

    chartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: Array.from({ length: xData.length }, (_, i) => i),
            datasets: [
                {
                    label: 'X-Axis',
                    data: xData,
                    borderColor: 'rgba(255, 99, 132, 1)',
                    borderWidth: 2,
                    fill: false,
                    pointRadius: 0
                },
                {
                    label: 'Y-Axis',
                    data: yData,
                    borderColor: 'rgba(54, 162, 235, 1)',
                    borderWidth: 2,
                    fill: false,
                    pointRadius: 0
                },
                {
                    label: 'Z-Axis',
                    data: zData,
                    borderColor: 'rgba(75, 192, 192, 1)',
                    borderWidth: 2,
                    fill: false,
                    pointRadius: 0
                }
            ]
        },
        options: {
            responsive: true,
            scales: {
                x: {
                    display: true,
                    title: {
                        display: true,
                        text: 'Sample Index'
                    }
                },
                y: {
                    display: true,
                    title: {
                        display: true,
                        text: 'Acceleration (m/s²)'
                    },
                    suggestedMin: -20,
                    suggestedMax: 10
                }
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: {
                        usePointStyle: true,
                        boxWidth: 20,
                        padding: 20,
                        font: {
                            size: 14
                        }
                    }
                },
                title: {
                    display: true,
                    text: 'Accelerometer Data Visualization'
                }
            },
            elements: {
                line: {
                    tension: 0.3
                }
            }
        }
    });
});

// Watch for changes in accelerometerData and update the chart
watch(
    () => props.accelerometerData,
    (newData) => {
        const { xData, yData, zData } = splitAccelerometerData(newData);

        if (chartInstance) {
            chartInstance.data.labels = Array.from({ length: xData.length }, (_, i) => i);
            chartInstance.data.datasets[0].data = xData;
            chartInstance.data.datasets[1].data = yData;
            chartInstance.data.datasets[2].data = zData;
            chartInstance.update();
        }
    }
);
</script>

<style scoped>
#visualization {
    width: 100%;
    padding: 20px;
    margin: 0 auto;
    text-align: center;
}

canvas {
    display: block;
    margin: 0 auto;
    width: 100% !important;
    height: auto !important;
}
</style>

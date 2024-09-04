import { createRouter, createWebHistory } from 'vue-router'
import Main from '../components/Main.vue'
import Visualization from '../components/Visualization.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'main',
      component: Main
    },
    {
      path: '/visualization',
      name: 'visualization',
      component: Visualization
    },
  ]
})

export default router

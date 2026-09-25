import DefaultTheme from 'vitepress/theme'
import MyLayout from './MyLayout.vue'
import Gallery from './components/Gallery.vue'
import AppCards from './components/AppCards.vue'
import Flink from './components/Flink.vue'
import Flinks from './components/Flinks.vue'
import MapView from './components/MapView.vue'
import FoodCards from './components/FoodCards.vue'
import './style.css'

export default {
  extends: DefaultTheme,
  Layout: MyLayout,
  enhanceApp({ app }) {
    app.component('Gallery', Gallery)
    app.component('AppCards', AppCards)
    app.component('Flink', Flink)
    app.component('flink', Flink)
    app.component('Flinks', Flinks)
    app.component('MapView', MapView)
    app.component('FoodCards', FoodCards)
  },
}

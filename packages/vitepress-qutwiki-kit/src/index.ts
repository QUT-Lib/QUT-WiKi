import type { App, Plugin } from 'vue'
import AppCards from './components/AppCards.vue'
import Flink from './components/Flink.vue'
import Flinks from './components/Flinks.vue'
import Gallery from './components/Gallery.vue'
import ImageViewer from './components/ImageViewer.vue'

export { AppCards, Flink, Flinks, Gallery, ImageViewer }
export type { AppCardItem } from './components/AppCards.vue'
export type { FlinkItem } from './components/Flinks.vue'

export interface WikiKitOptions {
  componentPrefix?: string
}

export function installWikiComponents(app: App, options: WikiKitOptions = {}) {
  const prefix = options.componentPrefix ?? ''
  app.component(`${prefix}AppCards`, AppCards)
  app.component(`${prefix}Flink`, Flink)
  app.component(`${prefix}Flinks`, Flinks)
  app.component(`${prefix}Gallery`, Gallery)
  app.component(`${prefix}ImageViewer`, ImageViewer)
}

export function createWikiKit(options: WikiKitOptions = {}): Plugin {
  return {
    install(app) {
      installWikiComponents(app, options)
    },
  }
}

export default createWikiKit()

<template>
  <Teleport to="body">
    <div class="emote-pet-container" @click="handleClick">
      <img :src="currentGif" alt="页宠" />
    </div>
  </Teleport>
</template>
 

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'


const gifList = ['idle', 'happy', 'wait']
const currentIndex = ref(0)
const currentGif = computed(() => `/pet/${gifList[currentIndex.value]}.gif`)

let resetTimer = null


function handleClick() {

  let newIndex
  do {
    newIndex = Math.floor(Math.random() * gifList.length)
  } while (newIndex === currentIndex.value)
  
  currentIndex.value = newIndex


  if (resetTimer) clearTimeout(resetTimer)


  if (currentIndex.value !== 0) {
    resetTimer = setTimeout(() => {
      currentIndex.value = 0
    }, 3000)
  }
}


onMounted(() => {
  gifList.forEach(name => {
    const img = new Image()
    img.src = `/pet/${name}.gif`
  })
})


onBeforeUnmount(() => {
  if (resetTimer) clearTimeout(resetTimer)
})
</script>

<style scoped>
.emote-pet-container {
  position: fixed;
  bottom: 20px;
  right: 20px;
  z-index: 9999;
  width: 150px;
  cursor: pointer; 
}

.emote-pet-container:active {
  transform: scale(0.9);
  transition: transform 0.1s;
}
</style>
<template>
  <div class="bubble-row" :class="message.role">
    <div class="bubble">
      <span v-if="message.loading" class="loading">思考中… 🤔</span>
      <template v-else>
        <div class="text">{{ message.text }}</div>
        <div v-if="message.images && message.images.length" class="images">
          <a v-for="(img, i) in message.images" :key="i" :href="img" target="_blank">
            <img :src="img" />
          </a>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
defineProps({
  message: { type: Object, required: true },
})
</script>

<style scoped>
.bubble-row { display: flex; margin-bottom: 14px; }
.bubble-row.user { justify-content: flex-end; }
.bubble-row.agent { justify-content: flex-start; }
.bubble {
  max-width: 75%;
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.6;
}
.user .bubble { background: #4f8cff; color: #fff; }
.agent .bubble { background: #fff; color: #333; border: 1px solid #eee; }
.text { white-space: pre-wrap; word-break: break-word; }
.images { display: flex; gap: 8px; margin-top: 8px; flex-wrap: wrap; }
.images img {
  width: 120px;
  height: 120px;
  object-fit: cover;
  border-radius: 8px;
  cursor: pointer;
  border: 1px solid #eee;
}
.loading { color: #999; }
</style>

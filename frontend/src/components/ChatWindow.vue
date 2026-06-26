<template>
  <div class="chat-window">
    <!-- 消息列表 -->
    <div class="messages" ref="messagesRef">
      <MessageBubble v-for="(m, i) in messages" :key="i" :message="m" />
    </div>

    <!-- 已选图片预览 -->
    <div v-if="previewUrl" class="preview">
      <img :src="previewUrl" />
      <button class="clear" @click="clearImage">×</button>
    </div>

    <!-- 输入区 -->
    <div class="input-area">
      <label class="upload-btn" title="上传图片">
        📎
        <input type="file" accept="image/*" @change="onPick" hidden />
      </label>
      <input
        v-model="text"
        @keyup.enter="send"
        placeholder="发消息…（可附图片，如：把这个做成拼豆）"
        :disabled="sending"
      />
      <button @click="send" :disabled="sending || (!text.trim() && !imageFile)">
        {{ sending ? '生成中…' : '发送' }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick } from 'vue'
import { sendMessage } from '../api.js'
import MessageBubble from './MessageBubble.vue'

const messages = ref([
  {
    role: 'agent',
    text: '你好呀茜茜～我能帮你做拼豆图、生成 AIGC 创意图。可以发文字，也能发图片哦 🐾',
    images: [],
  },
])
const text = ref('')
const imageFile = ref(null)
const previewUrl = ref('')
const sending = ref(false)
const messagesRef = ref(null)

function onPick(e) {
  const f = e.target.files[0]
  if (f) {
    imageFile.value = f
    previewUrl.value = URL.createObjectURL(f)
  }
}
function clearImage() {
  imageFile.value = null
  previewUrl.value = ''
}

async function send() {
  const t = text.value.trim()
  if (!t && !imageFile.value) return
  // 用户气泡（含上传图预览）
  messages.value.push({
    role: 'user',
    text: t,
    images: previewUrl.value ? [previewUrl.value] : [],
  })
  text.value = ''
  // Agent 占位（记下索引，稍后用「整体替换」触发响应式更新——直接改对象属性不会刷新界面）
  messages.value.push({ role: 'agent', text: '', images: [], loading: true })
  const agentIdx = messages.value.length - 1
  sending.value = true
  await scrollBottom()
  try {
    const { reply, images } = await sendMessage(t, imageFile.value)
    messages.value[agentIdx] = { role: 'agent', text: reply, images, loading: false }
  } catch (e) {
    messages.value[agentIdx] = { role: 'agent', text: '❌ ' + e.message, images: [], loading: false }
  }
  clearImage()
  sending.value = false
  await scrollBottom()
}

async function scrollBottom() {
  await nextTick()
  if (messagesRef.value) messagesRef.value.scrollTop = messagesRef.value.scrollHeight
}
</script>

<style scoped>
.chat-window { flex: 1; display: flex; flex-direction: column; background: #f5f5f7; min-height: 0; }
.messages { flex: 1; overflow-y: auto; padding: 20px; }
.preview { display: flex; align-items: center; gap: 8px; padding: 8px 20px; background: #fff; border-top: 1px solid #eee; }
.preview img { height: 56px; border-radius: 6px; }
.preview .clear { border: none; background: #ccc; width: 22px; height: 22px; border-radius: 50%; cursor: pointer; }
.input-area { display: flex; gap: 8px; padding: 12px 20px; background: #fff; border-top: 1px solid #eee; }
.input-area input { flex: 1; padding: 10px 12px; border: 1px solid #ddd; border-radius: 8px; font-size: 14px; }
.upload-btn { cursor: pointer; font-size: 22px; display: flex; align-items: center; }
.input-area button { padding: 0 18px; border: none; background: #4f8cff; color: #fff; border-radius: 8px; cursor: pointer; font-size: 14px; }
.input-area button:disabled { background: #aaa; cursor: not-allowed; }
</style>

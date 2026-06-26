<template>
  <div class="bubble-row" :class="message.role">
    <!-- Agent 头像在左（图片，圆形；图片没放时用 emoji 兜底）-->
    <div v-if="message.role === 'agent'" class="avatar">
      <img v-if="agentImgOk" src="/agent.png" @error="agentImgOk = false" alt="AI" />
      <span v-else>🤖</span>
    </div>
    <div class="bubble">
      <span v-if="message.loading" class="loading">思考中… 🤔</span>
      <template v-else>
        <!-- 文字：隐藏掉里面的图片绝对路径，不暴露服务器路径给用户 -->
        <div class="text">{{ cleanedText }}</div>
        <!-- 图片：缩略图（点击放大）+ 下载按钮 -->
        <div v-if="message.images && message.images.length" class="images">
          <div v-for="(img, i) in message.images" :key="i" class="img-item">
            <img :src="img" @click="lightboxSrc = img" title="点击放大" />
            <a
              v-if="message.role === 'agent'"
              class="dl-btn"
              :href="img"
              :download="fileName(img)"
              target="_blank"
            >⬇ 下载</a>
          </div>
        </div>
      </template>
    </div>
    <!-- 用户头像在右 -->
    <div v-if="message.role === 'user'" class="avatar">
      <img v-if="userImgOk" src="/user.png" @error="userImgOk = false" alt="我" />
      <span v-else>🧑</span>
    </div>
  </div>

  <!-- 大图预览遮罩：点击缩略图弹出，点击任意处关闭 -->
  <div v-if="lightboxSrc" class="lightbox" @click="lightboxSrc = ''">
    <img :src="lightboxSrc" />
    <span class="lightbox-tip">点击任意处关闭</span>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  message: { type: Object, required: true },
})

const lightboxSrc = ref('')
const agentImgOk = ref(true)   // agent.png 加载失败则降级为 emoji
const userImgOk = ref(true)    // user.png 加载失败则降级为 emoji

// 隐藏 reply 里的图片绝对路径（D:\...\xxx.png），换成提示，不暴露服务器路径
const cleanedText = computed(() => {
  let t = props.message.text || ''
  t = t.replace(/\*{0,2}[A-Za-z]:[\\\/][^\s*]*\.(?:png|jpg|jpeg|webp)\*{0,2}/gi, '（见下方图片 🖼️）')
  t = t.replace(/路径[:：]\s*/g, '')
  t = t.replace(/\*{2,}/g, '').replace(/\n{3,}/g, '\n\n').trim()
  return t
})

function fileName(url) {
  return decodeURIComponent(url.split('/').pop() || 'image.png')
}
</script>

<style scoped>
.bubble-row { display: flex; margin-bottom: 14px; gap: 8px; align-items: flex-start; }
.bubble-row.agent { justify-content: flex-start; }   /* AI 消息靠左 */
.bubble-row.user { justify-content: flex-end; }      /* 用户消息靠右（头像+气泡）*/
.avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;       /* 圆形 */
  overflow: hidden;         /* 图片超出圆形部分裁掉 */
  flex-shrink: 0;
  margin-top: 2px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  background: #f0f0f0;
}
.avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;        /* 图片填满圆形，不变形 */
}
.bubble {
  max-width: calc(100% - 48px);
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.6;
}
.user .bubble { background: #4f8cff; color: #fff; text-align: right; }
.agent .bubble { background: #fff; color: #333; border: 1px solid #eee; }
.text { white-space: pre-wrap; word-break: break-word; }
.images { display: flex; gap: 10px; margin-top: 8px; flex-wrap: wrap; }
.img-item { display: flex; flex-direction: column; align-items: center; }
.img-item img {
  width: 120px;
  height: 120px;
  object-fit: cover;
  border-radius: 8px;
  cursor: zoom-in;
  border: 1px solid #eee;
}
.dl-btn {
  margin-top: 4px;
  font-size: 12px;
  color: #4f8cff;
  text-decoration: none;
}
.dl-btn:hover { text-decoration: underline; }
.loading { color: #999; }

/* 大图预览遮罩 */
.lightbox {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.85);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  cursor: zoom-out;
}
.lightbox img {
  max-width: 90%;
  max-height: 90%;
  object-fit: contain;
  border-radius: 4px;
}
.lightbox-tip {
  position: absolute;
  bottom: 24px;
  color: #fff;
  font-size: 13px;
  opacity: 0.8;
}
</style>

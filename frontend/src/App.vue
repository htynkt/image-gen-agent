<template>
  <div class="app">
    <header class="app-header">
      🎨 图片生成 Agent
      <span class="sub">前端 Vue + 后端 FastAPI</span>
    </header>
    <ChatWindow />
  </div>
</template>

<script setup>
import ChatWindow from './components/ChatWindow.vue'
</script>

<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Microsoft YaHei", sans-serif;
  background: #f5f5f7;
}
.app {
  max-width: 760px;
  margin: 0 auto;
  height: 100vh;
  display: flex;
  flex-direction: column;
}
.app-header {
  padding: 16px 20px;
  background: #fff;
  border-bottom: 1px solid #eee;
  font-size: 18px;
  font-weight: 600;
}
.app-header .sub {
  font-size: 12px;
  color: #999;
  font-weight: normal;
  margin-left: 8px;
}
</style>

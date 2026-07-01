// AI 问答页：一进来就有 AI 提示语；AI 头像 🤖，用户头像=微信头像；宽度自适应
const api = require('../../utils/api')
const app = getApp()

Page({
  data: {
    text: '',
    imagePath: '',
    // 进页面就有 AI 提示语（欢迎 + 引导）
    messages: [
      {
        role: 'agent',
        text: '你好呀～我是画灵 🐾\n发文字让我生成图片（如「画一只赛博朋克柴犬」），或上传图片做成拼豆图～',
        images: [], loading: false
      }
    ],
    sending: false,
    userAvatar: ''
  },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({ selected: 1 })
    }
    this.setData({ userAvatar: app.globalData.avatarUrl || '' })
  },

  onText(e) { this.setData({ text: e.detail.value }) },

  chooseImage() {
    wx.chooseMedia({
      count: 1, mediaType: ['image'], sourceType: ['album', 'camera'],
      success: r => this.setData({ imagePath: r.tempFiles[0].tempFilePath })
    })
  },
  clearImage() { this.setData({ imagePath: '' }) },

  send() {
    const t = this.data.text.trim()
    const imgPath = this.data.imagePath
    if (!t && !imgPath) return
    const userMsg = { role: 'user', text: t, images: imgPath ? [imgPath] : [] }
    const messages = [...this.data.messages, userMsg,
                      { role: 'agent', text: '', images: [], loading: true }]
    const idx = messages.length - 1
    this.setData({ messages, text: '', imagePath: '', sending: true })

    const p = imgPath ? api.chatUpload(imgPath, t) : api.chatText(t)
    p.then(d => {
      const imgs = (d.images || []).map(u => api.imgUrl(u))
      this.setData({
        [`messages[${idx}]`]: { role: 'agent', text: d.reply || '（空）', images: imgs, loading: false },
        sending: false
      })
    }).catch(e => {
      this.setData({
        [`messages[${idx}]`]: { role: 'agent', text: '❌ ' + (e.errMsg || '请求失败'), images: [], loading: false },
        sending: false
      })
    })
  },

  previewImage(e) {
    const { url, urls } = e.currentTarget.dataset
    wx.previewImage({ current: url, urls: urls || [url] })
  },

  saveImage(e) {
    const url = e.currentTarget.dataset.url
    wx.showLoading({ title: '保存中…' })
    wx.downloadFile({
      url,
      success: r => wx.saveImageToPhotosAlbum({
        filePath: r.tempFilePath,
        success: () => wx.showToast({ title: '已保存到相册' }),
        fail: () => wx.showToast({ title: '保存失败', icon: 'none' }),
        complete: () => wx.hideLoading()
      }),
      fail: () => wx.hideLoading()
    })
  }
})

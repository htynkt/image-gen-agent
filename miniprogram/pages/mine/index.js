// 我的页：头像 + 昵称（chooseAvatar / nickname 合规授权）+ 同步后端 + 我的收藏
const api = require('../../utils/api')
const app = getApp()

Page({
  data: {
    openid: '',
    nickname: '',
    avatarUrl: '',     // 选了但没存：临时路径；存了：后端完整 url
    favorites: []
  },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({ selected: 2 })
    }
    this.setData({
      openid: app.globalData.openid || '登录中…',
      nickname: app.globalData.nickname || '',
      avatarUrl: app.globalData.avatarUrl || ''
    })
    if (app.globalData.openid) this.loadFavorites()
  },

  // 选微信头像（button open-type=chooseAvatar，合规）
  chooseAvatar(e) {
    this.setData({ avatarUrl: e.detail.avatarUrl })   // 临时路径，待「保存」时上传
  },

  onNickname(e) {
    this.setData({ nickname: e.detail.value })
  },

  // 保存昵称 + 头像到后端（跨设备同步）
  saveProfile() {
    const { avatarUrl, nickname } = this.data
    if (!avatarUrl) { wx.showToast({ title: '请先选头像', icon: 'none' }); return }
    if (!app.globalData.openid) { wx.showToast({ title: '登录中，稍后再试', icon: 'none' }); return }
    wx.showLoading({ title: '保存中…' })
    api.updateProfile(avatarUrl, nickname).then(d => {
      const full = d.avatar ? api.imgUrl(d.avatar) : ''
      app.globalData.nickname = d.nickname
      app.globalData.avatarUrl = full
      wx.setStorageSync('avatarUrl', full)
      this.setData({ nickname: d.nickname, avatarUrl: full })
      wx.hideLoading()
      wx.showToast({ title: '已保存' })
    }).catch(() => {
      wx.hideLoading()
      wx.showToast({ title: '保存失败', icon: 'none' })
    })
  },

  loadFavorites() {
    api.favorites().then(d => {
      const favs = (d.items || []).map(it => ({ ...it, url: api.imgUrl(it.url) }))
      this.setData({ favorites: favs })
    })
  },

  tapImage(e) {
    const url = e.currentTarget.dataset.url
    const urls = this.data.favorites.map(f => f.url)
    wx.previewImage({ current: url, urls })
  }
})

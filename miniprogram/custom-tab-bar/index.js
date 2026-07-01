// 自定义 tabBar：可控字体大小 / 配色（原生 tabBar 字体改不了）
Component({
  data: {
    selected: 0,
    list: [
      { pagePath: '/pages/home/index', text: '主页', icon: '🏠' },
      { pagePath: '/pages/chat/index', text: 'AI问答', icon: '💬' },
      { pagePath: '/pages/mine/index', text: '我的', icon: '👤' }
    ]
  },
  methods: {
    switchTab(e) {
      const idx = e.currentTarget.dataset.index
      wx.switchTab({ url: this.data.list[idx].pagePath })
      this.setData({ selected: idx })
    }
  }
})

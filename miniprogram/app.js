// 全局 app：登录拿 openid + 取后端已存的头像/昵称
App({
  globalData: {
    openid: '',
    nickname: '',
    avatarUrl: '',
    baseUrl: 'http://localhost:8000'  // 开发期后端地址；上线需换成 https 已备案域名
  },
  onLaunch() {
    this.login()
  },
  login() {
    wx.login({
      success: res => {
        if (!res.code) return
        wx.request({
          url: this.globalData.baseUrl + '/api/login',
          method: 'POST',
          data: { code: res.code },
          success: r => {
            if (r.data && r.data.openid) {
              this.globalData.openid = r.data.openid
              this.globalData.nickname = r.data.nickname || ''
              // 后端有头像用后端（跨设备同步）；否则用本地缓存兜底
              this.globalData.avatarUrl = r.data.avatar
                ? this.globalData.baseUrl + r.data.avatar
                : (wx.getStorageSync('avatarUrl') || '')
              console.log('登录完成', this.globalData.openid, this.globalData.nickname)
            }
          }
        })
      }
    })
  }
})

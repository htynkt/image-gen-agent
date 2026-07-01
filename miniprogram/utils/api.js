// 接口封装：统一 baseUrl + openid
const app = getApp()
const BASE = () => app.globalData.baseUrl

function request(path, { method = 'GET', data = {} } = {}) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: BASE() + path,
      method, data,
      header: { 'content-type': 'application/json' },
      success: r => (r.statusCode === 200 ? resolve(r.data) : reject(r)),
      fail: reject
    })
  })
}

module.exports = {
  // 画廊
  categories: () => request('/api/categories'),
  gallery: (category, page = 1) =>
    request(`/api/gallery?category=${encodeURIComponent(category)}&page=${page}&user_id=${app.globalData.openid}`),
  search: (kw) =>
    request(`/api/search?kw=${encodeURIComponent(kw)}&user_id=${app.globalData.openid}`),
  // 收藏
  favorite: (image_id, user_id) =>
    request('/api/favorite', { method: 'POST', data: { image_id, user_id } }),
  favorites: () =>
    request(`/api/favorites?user_id=${app.globalData.openid}`),
  // AI 问答（纯文字，带 openid 做历史隔离）
  chatText: (text) => request('/api/chat', { method: 'POST', data: { text, user_id: app.globalData.openid || 'mini' } }),
  // AI 问答（上传图片 + 文字，带 openid）
  chatUpload: (filePath, text) => new Promise((resolve, reject) => {
    wx.uploadFile({
      url: BASE() + '/api/chat_upload',
      filePath, name: 'file',
      formData: { text, user_id: app.globalData.openid || 'mini' },
      success: r => resolve(JSON.parse(r.data)),
      fail: reject
    })
  }),
  // 更新昵称 + 头像（上传到后端，跨设备同步）
  updateProfile: (avatarPath, nickname) => new Promise((resolve, reject) => {
    wx.uploadFile({
      url: BASE() + '/api/profile',
      filePath: avatarPath, name: 'avatar',
      formData: { openid: app.globalData.openid, nickname },
      success: r => resolve(JSON.parse(r.data)),
      fail: reject
    })
  }),
  // 图片地址拼接：/files/... → 完整 url
  imgUrl: (url) => BASE() + url
}

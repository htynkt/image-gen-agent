// 主页三段式：①搜索框 ②分类导航 ③该分类图片瀑布流
// 瀑布流：用后端给的 width/height 同步贪心分配到较矮列（无 bindload，稳定无闪烁）
const api = require('../../utils/api')
const app = getApp()

Page({
  data: {
    categories: [],
    activeCat: '最热',
    leftCol: [],
    rightCol: [],
    keyword: '',
    loading: false,
    colWidth: 0          // 单列宽（px）
  },

  onLoad() {
    const sys = wx.getSystemInfoSync()
    this.setData({ colWidth: (sys.windowWidth - 24) / 2 })   // 24 ≈ 左右padding+中间gap
    this.loadCategories()
    this.loadGallery('最热')
  },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({ selected: 0 })
    }
  },

  loadCategories() {
    api.categories().then(d => this.setData({ categories: d.categories || [] }))
      .catch(() => wx.showToast({ title: '分类加载失败，请确认后端已启动', icon: 'none' }))
  },

  loadGallery(cat) {
    this.setData({ activeCat: cat, loading: true, leftCol: [], rightCol: [] })
    api.gallery(cat).then(d => {
      const items = (d.items || []).map(it => ({ ...it, url: api.imgUrl(it.url) }))
      this.allocate(items)
      this.setData({ loading: false })
    }).catch(() => {
      this.setData({ loading: false })
      wx.showToast({ title: '图片加载失败，请确认后端已启动', icon: 'none' })
    })
  },

  // 同步分配：按宽高贪心放到【较矮的列】（后端已给 width/height）
  allocate(items) {
    const colW = this.data.colWidth
    const left = [], right = []
    let lH = 0, rH = 0
    items.forEach(it => {
      const ratio = (it.height && it.width) ? it.height / it.width : 1.2   // 无宽高默认比
      const cardH = colW * ratio + 56                                     // +标题/边距约 56px
      if (lH <= rH) { left.push(it); lH += cardH }
      else { right.push(it); rH += cardH }
    })
    this.setData({ leftCol: left, rightCol: right })
  },

  switchCat(e) {
    const cat = e.currentTarget.dataset.cat
    if (cat === this.data.activeCat) return
    this.setData({ keyword: '' })
    this.loadGallery(cat)
  },

  onKeyword(e) { this.setData({ keyword: e.detail.value }) },

  doSearch() {
    const kw = this.data.keyword.trim()
    if (!kw) { this.loadGallery('最热'); return }
    this.setData({ activeCat: '', loading: true })
    api.search(kw).then(d => {
      const items = (d.items || []).map(it => ({ ...it, url: api.imgUrl(it.url) }))
      this.allocate(items)
      this.setData({ loading: false })
    })
  },

  toggleFav(e) {
    const id = e.currentTarget.dataset.id
    const openid = app.globalData.openid
    if (!openid) { wx.showToast({ title: '登录中，稍后再试', icon: 'none' }); return }
    api.favorite(id, openid).then(d => {
      wx.showToast({ title: d.liked ? '已收藏' : '已取消', icon: 'none' })
      this.loadGallery(this.data.activeCat || '最热')
    })
  },

  tapImage() {
    wx.showToast({ title: '详情页待开发', icon: 'none' })
  }
})

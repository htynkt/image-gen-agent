// 把 File 读成 base64 data URL（后端会 split 掉前缀）
function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const r = new FileReader()
    r.onload = () => resolve(r.result)
    r.onerror = reject
    r.readAsDataURL(file)
  })
}

// 发消息给后端 /api/chat，返回 { reply, images }
export async function sendMessage(text, imageFile) {
  const body = { text }
  if (imageFile) body.image = await fileToBase64(imageFile)
  const resp = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!resp.ok) {
    const err = await resp.text()
    throw new Error(`后端错误 ${resp.status}: ${err}`)
  }
  return resp.json()
}

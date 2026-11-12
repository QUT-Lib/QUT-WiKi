/**
 * 高德地图 Web 端 JS API 公共加载器
 * key 在 lbs.amap.com 控制台申请，应用类型：Web端(JS API)
 * 2021 年后申请的 key 需要安全密钥，必须在 SDK 脚本加载前设置。
 */
export const AMAP_KEY = 'cc942326fd33951c36e3f35a16bc204f'

const AMAP_SECURITY_CODE = '08b66b63cfa12c5beccf95cb1cdb8839'

/* 高德官方内置样式：normal 标准 / dark 夜间 */
export const MAP_STYLES = { light: 'amap://styles/normal', dark: 'amap://styles/dark' }

export function loadAMap() {
  return new Promise((resolve, reject) => {
    if (window.AMap) return resolve(window.AMap)
    window._AMapSecurityConfig = {
      securityJsCode: AMAP_SECURITY_CODE
    }
    window.__QUTMapReady = () => {
      if (window.AMap) resolve(window.AMap)
      else reject(new Error('高德地图 SDK 已响应，但没有提供地图对象'))
    }
    const script = document.createElement('script')
    script.async = true
    script.src = `https://webapi.amap.com/maps?v=2.0&key=${encodeURIComponent(AMAP_KEY)}&callback=__QUTMapReady`
    script.onerror = () => reject(new Error('高德地图 SDK 加载失败'))
    document.head.appendChild(script)
    setTimeout(() => reject(new Error('高德地图 SDK 加载超时')), 15000)
  })
}

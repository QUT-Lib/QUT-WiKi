/**
 * QUTWiKi 首页海报数据
 *
 * 添加海报：在 POSTERS 数组追加条目。
 *   desktop  桌面端图片（横版，建议 16:9）
 *   mobile   移动端图片（竖版，建议 9:16）
 *   image    通用图，desktop / mobile 都缺省时兜底
 *   ratio    可选，图片宽高比（如 16 / 9、9 / 16），用于图片加载前先占位排版
 *   orientation 可选，'landscape' 或 'portrait'，等价于填写 ratio
 *   title    海报标题（可选）
 *   description 描述文字（可选）
 *   author   作者（可选）
 *   date     创作日期（可选，原样展示）
 *   href     点击跳转链接（可选，支持站内 / 开头路径或 http(s) 外链）
 *
 * desktop / mobile / image 至少提供其一即可。只提供横版或只提供竖版时，
 * 组件会自动按图片实际比例排版，同一行的海报等高对齐，不会裁切。
 * 图片需为 https:// 直链或 / 开头的站内 public 路径。
 */

export const POSTERS = [
  {
    desktop: '',
    mobile: '',
    title: '',
    description: '',
    author: '',
    date: '',
    href: '',
  },
  {
    mobile: '',
    title: '',
    description: '',
    author: '',
    date: '',
    href: '',
  },
]

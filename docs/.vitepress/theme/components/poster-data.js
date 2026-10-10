/**
 * QUTWiKi 首页海报数据
 *
 * 添加海报：在 POSTERS 数组追加条目。
 *   desktop  桌面端图片（16:9），必填
 *   mobile   移动端图片（9:16），必填
 *   image    可选，桌面/移动通用图（当 desktop 或 mobile 缺省时兜底）
 *   title    海报标题（可选）
 *   description 描述文字（可选）
 *   author   作者（可选）
 *   date     创作日期（可选，原样展示）
 *   href     点击跳转链接（可选，支持站内 / 开头路径或 http(s) 外链）
 *
 * 图片需为 https:// 直链或 / 开头的站内 public 路径。
 * 桌面端展示 16:9、移动端展示 9:16，两套图请按对应比例提供。
 */

export const POSTERS = [
  {
    // TODO: 替换为实际海报图（桌面端 16:9 / 移动端 9:16）
    desktop: 'https://pic1.imgdb.cn/i/034dJHSpIagHETSgP31igm.webp',
    mobile: 'https://pic1.imgdb.cn/i/034dJHpyCs1bOM5nXXydcU.webp',
    title: '“青海油”三校狼人杀联赛｜集结开赛！',
    description: '以发言交锋，用逻辑破局。青岛理工大学、中国石油大学、中国海洋大学的狼人杀玩家们，是时候上桌了！“青海油”三校狼人杀联赛即将开赛，我们诚邀三校同学参赛，在真假交织的发言中寻找线索，在阵营对抗中默契协作，一起争夺决赛席位！',
    author: '青岛理工大学棋牌与游戏爱好者协会',
    date: '2026.10.17-11.01',
    href: '',
  },
]

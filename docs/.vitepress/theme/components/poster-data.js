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
    desktop: 'https://pic1.imgdb.cn/i/034dYpIad38m3SsprrzEh2.webp',
    mobile: 'https://pic1.imgdb.cn/i/034dYpW39kkDiqnoCr6D2H.webp',
    title: '“青海油”三校狼人杀联赛｜集结开赛！',
    description: '以发言交锋，用逻辑破局。青岛理工大学、中国石油大学、中国海洋大学的狼人杀玩家们，是时候上桌了！“青海油”三校狼人杀联赛即将开赛，我们诚邀三校同学参赛，在真假交织的发言中寻找线索，在阵营对抗中默契协作，一起争夺决赛席位！',
    author: '青岛理工大学棋牌与游戏爱好者协会',
    date: '2026.10.17-11.01',
    href: '',
  },
  {
    mobile: 'https://pic1.imgdb.cn/i/034gM6n2U5oKLqVShFQJed.webp',
    title: '【青音逐梦，理颂韶华】校园歌手大赛',
    description: '2026年青岛理工大学校园歌手大赛初赛海选开启！线上赛事，面向全校在读学生（往届十佳歌手除外）。限中文歌曲、单人演绎，时长≤1分钟，清唱或自备伴奏均可，鼓励 rap、吉他弹唱等创新形式。加入海选群 1130127927，截止前将视频以「班级+姓名+手机号」命名发送至指定QQ邮箱；成功报名并提交作品可获 1 个到梦空间学时。',
    author: '共青团青岛理工大学委员会 · 校团委大学生艺术发展中心',
    date: '2026.10.15',
    href: '',
  },
]

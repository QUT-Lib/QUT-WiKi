/**
 * QUTWiKi 美食数据
 * 添加条目：在 FOODS 数组追加 { id, name, cover, gallery, category, campus, location, price, tags, recommend, desc }
 * id 是评论与评分的唯一标识（Twikoo url 为 /food/<id>），一经发布不要再修改，否则历史评论会丢失。
 * cover / gallery / photos 需要是 https:// 直链，支持多图（gallery 与 photos 等价，photos 兼容地图数据命名）。
 *
 * 部分条目整理自青岛理工大学吧探店帖（作者：你的幻想由我抹杀）
 * https://tieba.baidu.com/home/main?id=tb.1.97518fbf.K5DMFTn6xD6PjeWnmMWGaQ
 */

export const FOOD_CAMPUS = {
  h: '黄岛校区',
  s: '市北校区',
  l: '临沂校区'
}

export const FOOD_CATEGORIES = [
  { key: 'canteen', label: '校内食堂' },
  { key: 'inside', label: '校内店铺' },
  { key: 'outside', label: '校外周边' },
  { key: 'night', label: '夜市小吃' },
  { key: 'dessert', label: '饮品甜点' },
  { key: 'takeout', label: '外卖' }
]

function photoList(item) {
  if (Array.isArray(item.gallery) && item.gallery.length) return item.gallery.filter(Boolean)
  if (Array.isArray(item.photos) && item.photos.length) return item.photos.filter(Boolean)
  return item.cover ? [item.cover] : []
}

export const FOODS = [
  {
    id: 'xiaojiehutong-niuzamian',
    name: '小街胡同牛杂面',
    cover: 'https://pic1.imgdb.cn/i/034ScgdiEsqt8PkxdlAx01.webp',
    category: 'inside',
    campus: 'h',
    location: '慧园餐厅一楼',
    price: '¥12-15',
    tags: ['汤面', '拌面'],
    recommend: '油泼，牛杂，肉沫豆角，炸酱多种浇头',
    desc: '站长 LucasAndrew 倾情推荐他家的鸡丝面'
  },
  {
    id: 'huiyuan-3-malatang',
    name: '慧园三楼麻辣烫',
    cover: 'https://pic1.imgdb.cn/i/034Sz0TP3iVOryMkCh8HIo.webp',
    category: 'canteen',
    campus: 'h',
    location: '慧园三楼',
    price: '¥9 左右',
    tags: ['麻辣烫', '自选调料', '性价比'],
    recommend: '豆制品、麻酱自调',
    desc: '味道自调，选择很多，可以加麻酱；炸肉的味还不错，鸡块和其他肉类丸子不太推荐。性价比很好，便宜量大，人一般不多，好不好吃全靠自己的一手调料技术。'
  },
  {
    id: 'huiyuan-2-yangza-mian-jitui',
    name: '慧园二楼羊杂面窗口鸡腿面',
    cover: 'https://pic1.imgdb.cn/i/034Sz0dpe1Z1y2JYVgrjZA.webp',
    category: 'canteen',
    campus: 'h',
    location: '慧园二楼最右边羊杂面窗口',
    price: '¥10（不加豆干）',
    tags: ['汤面', '鸡腿', '经济实惠'],
    recommend: '鸡腿面加豆干',
    desc: '味道还不错，鸡腿挺大的也有味道，可惜面条差了点意思。慧园吃饭就得找经济实惠的，这个可以做选择。'
  },
  {
    id: 'huiyuan-2-zhengxin-jipai',
    name: '慧园二楼正新鸡排',
    cover: 'https://pic1.imgdb.cn/i/034Sz0XznW3Bhl1CUm8GZ6.webp',
    category: 'canteen',
    campus: 'h',
    location: '慧园二楼',
    price: '原价 ¥14，周末约 ¥12.3',
    tags: ['炸鸡', '套餐', '周末打折'],
    recommend: '鸡排炸鸡馍套餐（甘梅味）',
    desc: '两个鸡排馍加一杯对冲可乐，口味可选，甘梅味不错。可乐气不太足也不太凉，当小甜水喝。适合周末去吃，会打折而且不用挤，不过人多时出餐很慢，军训时等过 30 分钟。'
  },
  {
    id: 'xiangyuan-b1-koushuiji-banmian',
    name: '祥源负一楼口水鸡拌面',
    cover: 'https://pic1.imgdb.cn/i/034Sz0xc8gN5XTYszp760d.webp',
    category: 'canteen',
    campus: 'h',
    location: '祥源负一楼',
    price: '¥12',
    tags: ['拌面', '麻辣', '可加面'],
    recommend: '口水鸡拌面（微辣）',
    desc: '档口面味道统一，是麻辣麻酱口味。面热鸡凉，鸡肉没骨头、份量不少，还有小配菜。整体份量刚合适，可以免费加面，阿姨很热情；负一楼晚关门，去晚了也有饭吃。'
  },
  {
    id: 'xiangyuan-2-wazhu-lanrou-fan',
    name: '祥源二楼佤族烂肉饭',
    cover: 'https://pic1.imgdb.cn/i/034Sz0nebDTCqCNGgfwwvc.webp',
    category: 'canteen',
    campus: 'h',
    location: '祥源二楼（原黄金鸡腿饭档口）',
    price: '¥13',
    tags: ['鸡腿饭', '重辣', '不推荐'],
    recommend: '不加胡辣椒',
    desc: '鸡腿很大一个，撒上料很香；胡辣椒非常辣，慎重。米饭偏黏、没有配菜，整体不太推荐，除非你信邪。'
  },
  {
    id: 'xiangyuan-2-pizza',
    name: '祥源二楼披萨',
    cover: 'https://pic1.imgdb.cn/i/034Sz0sgvPSAo0oBlAU6m6.webp',
    category: 'canteen',
    campus: 'h',
    location: '祥源二楼最里边',
    price: '约 ¥16（七寸套餐 ¥16.9）',
    tags: ['披萨', '套餐', '只吃披萨'],
    recommend: '七寸烤肠披萨',
    desc: '建议只吃披萨——刚烤出来很香，味道不错。炸鸡有嚼劲、薯条跟木棍一样，番茄酱也是最差的一档。电烤，等的时间不算长，有预定群可以预定。七寸大概七分饱。'
  },
  {
    id: 'xiangyuan-1-hainan-jifan',
    name: '祥源一楼海南鸡饭',
    cover: 'https://pic1.imgdb.cn/i/034Sz0ijsTRiGWDztBOMpH.webp',
    category: 'canteen',
    campus: 'h',
    location: '祥源一楼往里走',
    price: '招牌 ¥14',
    tags: ['鸡饭', '可吃饱'],
    recommend: '招牌海南鸡饭',
    desc: '味道挺不错，配酱油、姜汁、辣椒酱三种料，肉挺嫩也没骨头，配菜是白菜本身没什么味，可以把料倒上去。饭量对瘦一点但能吃的人刚好能吃饱。'
  },
  {
    id: 'baogexing-zhishi-niurou-hanbao',
    name: '堡格星芝士牛肉汉堡店',
    cover: 'https://pic1.imgdb.cn/i/034Sz0K3LXjF9wZnAdvcds.webp',
    gallery: [
      'https://pic1.imgdb.cn/i/034Sz0K3LXjF9wZnAdvcds.webp',
      'https://pic1.imgdb.cn/i/034Sz0NFiK2CeAuDLxkQh4.webp',
      'https://pic1.imgdb.cn/i/034Sz0QEL9iT5D6G8M3vEa.webp'
    ],
    category: 'takeout',
    campus: 'h',
    location: '美团外卖',
    price: '¥30 出头（四件套加运费）',
    tags: ['外卖', '汉堡', '可乐'],
    recommend: '芝士牛肉汉堡（辣蛋酱）',
    desc: '点的神抢手四件套加运费三十小几。汉堡鸡蛋和肉饼很大，辣蛋酱味道不错，酸黄瓜基本吃不出味，整体比 KFC 的大，面包像是黄油面包。粗薯很面有一点点脆、没撒盐，配番茄酱还行；鸡块黑胡椒味、软的偏粘连但送糖醋酱；鸡条很油很咸。'
  },
  {
    id: '0090-hanbao-gongchang',
    name: '0090 汉堡工厂（橙堡）',
    cover: '',
    category: 'inside',
    campus: 'h',
    location: '西操下橙堡',
    price: '汉堡+薯条+可乐 ¥12',
    tags: ['汉堡', '便宜', '服务差'],
    recommend: '暂无',
    desc: '肉排挺大但就是很普通的汉堡，薯条份量不多、味道一般也没盐味，不如慧园三楼那个薯条好吃，饮料就是小甜水。人多的时候千万别去，服务很差、顾东不顾西，番茄酱没了也不提前说，饮料接完要自己拿也不给袋子。总体不如慧园三楼，唯一优势是便宜一块。'
  }
]

export function getFoodPhotos(item) {
  return photoList(item || {})
}

export function getFoodCategoryLabel(key) {
  return FOOD_CATEGORIES.find(category => category.key === key)?.label || '其他'
}

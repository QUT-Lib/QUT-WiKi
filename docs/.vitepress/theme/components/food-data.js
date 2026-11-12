/**
 * QUTWiKi 美食数据
 * 添加条目：在 FOODS 数组追加 { id, name, cover, gallery, category, campus, location, price, tags, recommend, desc }
 * id 是评论与评分的唯一标识（Twikoo url 为 /food/<id>），一经发布不要再修改，否则历史评论会丢失。
 * cover / gallery / photos 需要是 https:// 直链，支持多图（gallery 与 photos 等价，photos 兼容地图数据命名）。
 *
 * 校内条目部分整理自青岛理工大学吧「探店厚比多，真假一方说」系列（作者：你的幻想由我抹杀）
 * https://tieba.baidu.com/home/main?id=tb.1.97518fbf.K5DMFTn6xD6PjeWnmMWGaQ
 *
 * 2026-11 新增的「青岛美味地图」系列整理自贴吧帖（作者：sirokono）
 * https://tieba.baidu.com/p/11185193061
 * coord 为高德 GCJ02 坐标（[经度, 纬度]），用于美食地图与导航，不影响卡片展示。
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
  },
  {
    id: '137-pingjia-huoguo',
    name: '137平价火锅',
    cover: 'https://pic1.imgdb.cn/i/034w8wcA757bTnEBzRafQ4.webp',
    gallery: [
      'https://pic1.imgdb.cn/i/034w8wcA757bTnEBzRafQ4.webp',
      'https://pic1.imgdb.cn/i/034w91nfosiT0KJzwahfbs.webp'
    ],
    category: 'outside',
    campus: 's',
    location: '市北区瑞昌路60号（瑞昌路与重庆南路交叉口西北）',
    price: '建议抖音买六折券',
    tags: ['潮汕牛肉火锅', '鲜切牛肉', '免费水果'],
    recommend: '鲜切牛肉、免费冰淇淋',
    desc: '这家店建议抖音买六折券去自己点着吃。肉很新鲜，是潮汕牛肉火锅那一类的店。店内有免费水果、冰淇淋和大麦茶，但是桌子上的纸巾是收费的，这点需要注意。之前这家店有 1 元 1 只的活虾，味道非常不错，虾很鲜甜，但是现在的虾换成了冻虾，卖四块钱一只，拉完了。店里面的鸭血是合成的，蔬菜什么的还算便宜新鲜。综合评分（6.5/10），如果恢复了之前 1 元 1 只活虾的话可以给到（7/10）。',
    coord: [120.37047, 36.108148]
  },
  {
    id: 'nongtangli-chaoshan',
    name: '浓汤里潮汕牛肉火锅（台东店）',
    cover: 'https://pic1.imgdb.cn/i/034w8y0nea9R13UZMtqmY5.webp',
    gallery: [
      'https://pic1.imgdb.cn/i/034w8y0nea9R13UZMtqmY5.webp',
      'https://pic1.imgdb.cn/i/034w8y5nqAxCr5K5xItu4Y.webp'
    ],
    category: 'outside',
    campus: 's',
    location: '市北区汉口路45号（海泊桥海慈医疗地铁站D口步行约470米）',
    price: '抖音直播间五折券更划算',
    tags: ['潮汕牛肉火锅', '烤串', '免费水果'],
    recommend: '五花趾、吊龙',
    desc: '这家店和第一家一样是潮汕牛肉火锅店，但是这家还卖烤串（味道还不赖）。肉的品质很好，推荐五花趾和吊龙。然后就是基本的水果和茶都有，纸巾也是单独收费的。平时直接去吃性价比一般，推荐抖音直播间买五折券自己去点单。综合评分可以给到（6.8/10）。',
    coord: [120.360814, 36.090469]
  },
  {
    id: 'guolaotou-niurou-huoguo',
    name: '锅佬头牛肉火锅（热河路店）',
    cover: 'https://pic1.imgdb.cn/i/034w8xaSHMFhEwFqH4btDB.webp',
    gallery: [
      'https://pic1.imgdb.cn/i/034w8xaSHMFhEwFqH4btDB.webp',
      'https://pic1.imgdb.cn/i/034w8xfH3gqVtKPwGJB7j9.webp'
    ],
    category: 'outside',
    campus: 's',
    location: '市北区热河路36号',
    price: '抖音券约 ¥88/1.5斤；单点牛肉 ¥64/斤',
    tags: ['牛肉火锅', '冻切牛肉', '菊花茶'],
    recommend: '1.5斤牛肉自选套餐',
    desc: '这一家不是鲜牛肉，是那种冻了切片的肉。抖音上刷券 88 左右买 1.5 斤牛肉自选套餐最划算，单点牛肉 64 一斤（不建议）。肉很大片，吃起来非常爽。依然水果、茶、小零食免费，这家特有菊花茶还不赖。综合评分（6.5/10）。',
    coord: [120.329606, 36.077917]
  },
  {
    id: 'xueer-pijiuwu',
    name: '雪儿啤酒屋（台西三路店）',
    cover: 'https://pic1.imgdb.cn/i/034w92ZyVM3PASEhfiiej1.webp',
    category: 'outside',
    campus: 's',
    location: '市南区台西三路3号（西镇地铁站B口步行390米，近团岛农贸市场）',
    price: '散啤 ¥4/斤，原浆 ¥19/斤',
    tags: ['海鲜加工', '啤酒屋', '团岛市场'],
    recommend: '白灼虾、油泼石斑',
    desc: '在团岛农贸市场买完海鲜可以去这家店加工，价格不算贵，味道也不错。可以搞点白灼虾和石斑吃，老大爷的油泼石斑还挺不赖的。散啤 4/斤，原浆 19/斤。综合评分（6.5/10）。',
    coord: [120.301496, 36.059862]
  },
  {
    id: 'liangkeke-kaochuan',
    name: '梁珂珂二元烤串',
    cover: 'https://pic1.imgdb.cn/i/034w8xoYa0GE8nT4YSTx0m.webp',
    category: 'outside',
    campus: 's',
    location: '市北区抚顺路15号甲-4（东山社区东南侧）',
    tags: ['炒菜', '烧烤', '平价'],
    recommend: '青椒擂皮蛋、香酥鸡、农家小炒肉',
    desc: 'lz 吃的最多的一家店，之前的老店是在万科负一楼的，专门做炒菜。现在新店换到抚顺路上面了，炒菜依然美味且平价，还丰富了菜品（烧烤），味道不赖也便宜。综合评分（7.5/10），回忆加了 0.5 分。',
    coord: [120.368211, 36.100173]
  },
  {
    id: 'banbu-dashu',
    name: '班布大叔的店',
    cover: 'https://pic1.imgdb.cn/i/034w8xFiK4hlLv8lKtNMQP.webp',
    gallery: [
      'https://pic1.imgdb.cn/i/034w8xFiK4hlLv8lKtNMQP.webp',
      'https://pic1.imgdb.cn/i/034w8xM7M9ayekyuDXU3dH.webp'
    ],
    category: 'outside',
    campus: 's',
    location: '市北区南宁路102-6号（西吴家村地铁站B1口步行390米）',
    tags: ['韩料', '情侣约会', '氛围感'],
    recommend: '免费小菜、土豆泥',
    desc: '小而美的一家店，适合情侣去吃（套餐分量比较少，但是环境很有氛围感）。小菜都是免费的，土豆泥好吃。综合评分（6.8/10）。',
    coord: [120.375954, 36.097564]
  },
  {
    id: 'yijiayue-fushunlu',
    name: '忆家悦手工水饺（抚顺路店）',
    cover: 'https://pic1.imgdb.cn/i/034w91VFLnXYC2ZNtcDLNG.webp',
    category: 'outside',
    campus: 's',
    location: '市北区抚顺路15号甲-7户1层',
    tags: ['水饺', '炒面', '日常'],
    recommend: '青椒肉丝炒面（9/10）',
    desc: '这家店特有青椒肉丝炒面，其他的忆家悦都没有。味道真的是香麻了太好吃了，里面的面是那种拉面的面，裹上青椒肉丝的酱汁一起炒，真的无敌强烈推荐。其他的小吃就是很正常的小吃了，但是单价不贵适合日常吃。青椒肉丝炒面评分（9/10），综合评分（6.8/10）。',
    coord: [120.368023, 36.100246]
  },
  {
    id: 'miya-zhaji-taidong',
    name: '米娅韩式炸鸡自助（台东店）',
    cover: 'https://pic1.imgdb.cn/i/034w8xvOuYJvRPNXsLzncO.webp',
    category: 'outside',
    campus: 's',
    location: '市北区和兴路59号万佳广场F1',
    tags: ['炸鸡', '自助', '关东煮'],
    recommend: '炸鸡、关东煮',
    desc: '米娅炸鸡梦开始的地方，品牌首店的含金量。新品比其他的店先上，炸鸡师傅的品控是所有店里最好的，关东煮的种类和味道是所有店里面最好吃的。唯一缺点就是地方太小了，有时过去需要排队。综合评分可以给到（7/10）。',
    coord: [120.358078, 36.085573]
  },
  {
    id: 'zhongyuan-yijue',
    name: '中原一绝（豫一绝鸡蛋灌饼）',
    cover: 'https://pic1.imgdb.cn/i/034w91e5g4UVGwGFkEmWdo.webp',
    category: 'night',
    campus: 's',
    location: '市北区山东路171号乙万科东第B1-6；晚上在理工大学夜市摆摊',
    tags: ['鸡蛋灌饼', '夜市', '便宜'],
    recommend: '鸡蛋灌饼',
    desc: '理工大学夜市的 top，白天在万科一楼的店里面卖，晚上到理工大学夜市摆摊卖。东西不贵，饼很脆，味道不赖。建议白天去店里买，晚上排队的人太多了。综合评分（7/10）。',
    coord: [120.374111, 36.099084]
  },
  {
    id: 'juminlou-malatang',
    name: '居民楼麻辣烫',
    cover: 'https://pic1.imgdb.cn/i/034w8xjSRyf39xrN6T5a2w.webp',
    category: 'night',
    campus: 's',
    location: '市北区山东路171号丙B1-2（中原一绝对面）',
    tags: ['麻辣烫', '炸串', '东北老式'],
    recommend: '自选麻辣烫、炸串',
    desc: '高德这个废物地图上面没有标注，具体位置就在中原一绝的对面。价格便宜，麻辣烫的种类很多，里面还有炸串，是那种东北老式麻辣烫，味道不错量大管饱。综合评分（6.5/10）。（高德当前标注为暂停营业，去之前留意。）',
    coord: [120.374141, 36.099306]
  },
  {
    id: 'queshi-erciyuan',
    name: '雀食二次元主题餐厅',
    cover: 'https://pic1.imgdb.cn/i/034w8yHYh7qAkLyAyopzhP.webp',
    gallery: [
      'https://pic1.imgdb.cn/i/034w8yHYh7qAkLyAyopzhP.webp',
      'https://pic1.imgdb.cn/i/034w8yNr0KgDBhvqXR5crQ.webp'
    ],
    category: 'outside',
    campus: 'h',
    location: '黄岛区玉兰山路尚嘉中心A区二楼（霸王茶姬楼上）',
    price: '偏高',
    tags: ['二次元', '主题餐厅', '出片'],
    recommend: '香煎 ntr',
    desc: '浓度爆表的一集，勇哥夸过的餐厅。里面的装潢和布景真的别出心裁，喜欢二次元的人去会有一种归属感。一楼大厅有 live 台可以搞乐队，吧台附近有物料区，可以免费拿物料。二楼有 PS5 和二次元杂志、期刊、漫画，都是可以免费玩免费看的，老板真的很懂二次元。餐品价格有点偏高，但个人觉得味道对得起这个价格，强推香煎 ntr。适合和朋友一起去玩，也很出片。综合评分（7.5/10）。',
    coord: [120.234061, 35.968905]
  },
  {
    id: 'xiaohu-shengtang-mixian',
    name: '小阿虎生烫牛肉米线（理工大学店）',
    cover: 'https://pic1.imgdb.cn/i/034w90UxHkagp64yByUOLX.webp',
    category: 'outside',
    campus: 's',
    location: '市北区山东路171号创新大厦乙-9（西吴家村地铁站B1口步行390米）',
    tags: ['云南米线', '可续粉', '调料多'],
    recommend: '生烫牛肉米线',
    desc: '非常正宗的一家云南米线（我的云南朋友认证），调料台上调料的种类非常多，米线可以续。平时想嗦粉了可以去这家试试。综合评价（6.5/10）。',
    coord: [120.37413, 36.099217]
  },
  {
    id: 'shuangheyuan-shangjieli',
    name: '双合园·海鲜水饺青岛菜（上街里店）',
    cover: 'https://pic1.imgdb.cn/i/034w91zDcONoSCspabUtQC.webp',
    category: 'outside',
    campus: 's',
    location: '市北区四方路39号',
    price: '偏高',
    tags: ['青岛菜', '海鲜水饺', '现炒'],
    recommend: '脆炸虾仁、风味茄子、海鲜水饺',
    desc: '又是一家品牌首店，含金量不用多说。推荐脆炸虾仁和风味茄子还有海鲜水饺，青岛本土餐饮品牌，点餐尽可能往海边的菜点。价格偏高，但都是现炒的，没有预制菜。综合评分（6.8/10）。',
    coord: [120.32069, 36.070407]
  },
  {
    id: 'tongguolang-niurou-huoguo',
    name: '铜锅郎肥牛火锅（青岛首店）',
    cover: 'https://pic1.imgdb.cn/i/034w91x6nLlkb60KoDXN7O.webp',
    gallery: [
      'https://pic1.imgdb.cn/i/034w91x6nLlkb60KoDXN7O.webp',
      'https://pic1.imgdb.cn/i/034w90QFKzAT2AIE0XT894.webp'
    ],
    category: 'outside',
    campus: 'h',
    location: '黄岛区薛家岛街道敖江路20号4号楼A座一层',
    price: '抖音券约 ¥135/2.5斤肥牛四人餐',
    tags: ['肥牛火锅', '鲜鸭血', '免费雪糕'],
    recommend: '2.5斤肥牛四人餐、鲜鸭血',
    desc: 'lz 转来黄岛校区吃的第一顿火锅，抖音刷券能刷到 135 左右 2.5 斤肥牛四人餐的券，夯爆了。这家店里面的菜品单点是我吃过这么多火锅店里面最便宜的，菜品的品质也是中上游的，里面的鸭血是正儿八经的鲜鸭血而且只要八块钱。大麦茶免费、水果免费而且更新速度很快，里面还有非杂牌的雪糕免费吃，调料区的更新速度也很快。唯一的缺点就是位置比较偏，属于酒香也怕巷子深的那种店。综合评分（7.5/10）。',
    coord: [120.220541, 35.987242]
  },
  {
    id: 'yebaibai-zaopocu',
    name: '椰摆摆海南糟粕醋火锅（保税区店）',
    cover: 'https://pic1.imgdb.cn/i/034w91KbPiyE8OYVImhzRM.webp',
    gallery: [
      'https://pic1.imgdb.cn/i/034w91KbPiyE8OYVImhzRM.webp',
      'https://pic1.imgdb.cn/i/034w91PbsvypYSUJZRJuxh.webp'
    ],
    category: 'outside',
    campus: 'h',
    location: '黄岛区长江路街道兰溪路与渔湾路交叉口214号',
    price: '抖音券约 ¥80',
    tags: ['糟粕醋', '原切肉', '手工甜品'],
    recommend: '手工甜品、雪花、上脑、嫩肉',
    desc: '一个火锅店为了让顾客能吃到好吃的甜品，直接把隔壁的甜品店收购了，伟大无需多言。甜品几乎就是外面甜品店卖的十几一份的甜品的质量，进店就能看到甜品加工区，全是手工做的。肉的方面也很不错，都是原切肉，除了高钙肥羊和肥牛卷吃起来怪怪的，其他的雪花、上脑、嫩肉都很不错，牛肉味很浓厚。糟粕醋的锅底味道也不错，美中不足的是调料台的调料比较单薄。抖音刷券能刷到 80 左右，这个价格过去就很夯。保税区店工作日只做晚餐，节假日做中晚餐，去之前记得在美团上面排个队。综合评分（9/10）。',
    coord: [120.176125, 35.979925]
  },
  {
    id: 'xiaoxian-shitang',
    name: '小鲜食堂（漳州路店）',
    cover: 'https://pic1.imgdb.cn/i/034w90ZNn9xA2GtNRzGTV7.webp',
    category: 'outside',
    campus: 's',
    location: '市南区漳州路39号',
    tags: ['家常菜', '约会', '出片'],
    recommend: '家常菜',
    desc: '小而美的家常菜，菜品的品控很稳，卖的都是一些家常菜。环境不错，比较出片，适合小情侣约会的时候去吃。价格也不贵，中规中矩的一家店。综合评分（6.5/10）。',
    coord: [120.400992, 36.069604]
  },
  {
    id: 'gujieli-cuipi-zhouti',
    name: '古街里脆皮烤肘子（台东店）',
    cover: 'https://pic1.imgdb.cn/i/034w8xUS6LKYGGVOgMjKjl.webp',
    category: 'outside',
    campus: 's',
    location: '市北区长兴路80号（台东地铁站E口步行390米）',
    tags: ['脆皮肘子', '台东老店', '巷子'],
    recommend: '脆皮肘子、套餐面包',
    desc: '一家藏在台东巷子里面的老店，菜品非常有特色。脆皮肘子的原料很不错，就是有时候脆皮会过硬。套餐里面的那个面包很不错，很香很脆。适合想吃荤腥的人去吃。综合评分（6.8/10）。',
    coord: [120.355959, 36.085133]
  },
  {
    id: 'ximuda-niuroumian',
    name: '西穆达牛肉面',
    cover: 'https://pic1.imgdb.cn/i/034w90cXRB1n8CDVjltMpc.webp',
    gallery: [
      'https://pic1.imgdb.cn/i/034w90cXRB1n8CDVjltMpc.webp',
      'https://pic1.imgdb.cn/i/034w9DhAogHp2pkyrFEYjh.webp'
    ],
    category: 'outside',
    campus: 's',
    location: '市北区山东路与抚顺路交汇万科东第171号1-15西',
    price: '抖音券 ¥8.6/碗',
    tags: ['兰州牛肉面', '免费红枣茶', '可续面'],
    recommend: '传统牛肉面、炒拉面',
    desc: '我的食堂之一，品控稳定，价格实惠。店里面有免费的红枣茶喝，可以免费续面。推荐传统牛肉面和炒拉面，平时不知道吃什么去这家准没错。抖音上刷刷券能刷到 8.6 一碗牛肉面，性价比很高。综合评分（6.8/10）。',
    coord: [120.374075, 36.099325]
  },
  {
    id: 'taihe-zhengzong-banmian',
    name: '太和正宗牛肉板面',
    cover: 'https://pic1.imgdb.cn/i/034w8zKAq58kDuU1ZjMXc1.webp',
    gallery: [
      'https://pic1.imgdb.cn/i/034w8zKAq58kDuU1ZjMXc1.webp',
      'https://pic1.imgdb.cn/i/034w8zOoV6CAFQS2LU7mZu.webp',
      'https://pic1.imgdb.cn/i/034w9Dg70pOtgXZCNVIEAt.webp'
    ],
    category: 'outside',
    campus: 's',
    location: '市北区山东路171号丁1-2户-1',
    price: '¥17/人',
    tags: ['板面', '河北正宗', '出餐快'],
    recommend: '二细中辣、糊辣椒',
    desc: '很正宗的板面（河北同学认证），隔几天就想整点板面。推荐二细中辣，吃面的时候就一口面里面的糊辣椒，糊辣椒不辣很香，就着面吃非常惬意。这家店也是我的食堂之一。综合评分（6.8/10）。',
    coord: [120.374105, 36.099882]
  },
  {
    id: 'zhengjia-jituifan',
    name: '兴源记郑家烤鸡腿饭',
    cover: 'https://pic1.imgdb.cn/i/034w91Yum0cPmwfSEjF4sh.webp',
    category: 'outside',
    campus: 's',
    location: '市北区山东路万科东第（西吴家村地铁站A口步行320米）',
    price: '¥13 起',
    tags: ['鸡腿饭', '平价', '食堂'],
    recommend: '卤手枪腿、免费加饭',
    desc: '只需要 13 块就能买到一个卤的手枪腿、两个配菜和米饭，手枪腿在老板不忙的时候还可以免费拆一下，米饭可以跟老师说免费加饭。也是我的食堂之一，之前在健身房练完喜欢去他家吃练后餐，味道不错、品控稳定、价格实惠。综合评分（6.9/10）。',
    coord: [120.374129, 36.098963]
  },
  {
    id: 'xiangyuan-2-lizhiji',
    name: '祥源二楼荔枝鸡窗口',
    cover: 'https://pic1.imgdb.cn/i/034w9g6X3DzeUeHmbv3BJL.webp',
    gallery: [
      'https://pic1.imgdb.cn/i/034w9g6X3DzeUeHmbv3BJL.webp',
      'https://pic1.imgdb.cn/i/034w9fvMkBEutlL6gCETh7.webp'
    ],
    category: 'canteen',
    campus: 'h',
    location: '祥源二楼（新开的荔枝鸡窗口，旁边是酱油鸡）',
    price: '大份 ¥14.8 / 小份 ¥12.8',
    tags: ['番茄牛肉饭', '荔枝鸡', '量大实惠'],
    recommend: '番茄牛肉饭、荔枝鸡双拼',
    desc: '今天吃祥源二楼新开的荔枝鸡窗口，lz 点的是番茄牛肉饭。土豆软烂，牛肉还可以，汤有点咸，吃到后边越吃越咸，不过下饭，大家自己考虑。这家窗口和旁边酱油鸡一个老板，特点就是量大实惠不难吃，到时候点餐最好是让那个男老板给你盛，老板很大气，给的量很足；至于那位阿姨，建议去高中食堂应聘，相比之下，怪不得每次就这个窗口人最多。附图二为荔枝鸡双拼（阿姨盛的，当时就觉得怎么这么少，都没几块肉，不过味道还不错）。'
  },
  {
    id: 'xiangyuan-b1-xizhi-huajiafen',
    name: '祥源负一楼锡纸花甲粉',
    cover: 'https://pic1.imgdb.cn/i/034w9futVBL3RkMlzSoFww.webp',
    category: 'canteen',
    campus: 'h',
    location: '祥源负一楼（麻辣烫窗口）',
    price: '¥10',
    tags: ['花甲粉', '锡纸', '夜宵'],
    recommend: '锡纸花甲粉',
    desc: '今天吃祥源负一楼的锡纸花甲粉，在麻辣烫那个窗口。价格 10 元，尝着还是挺美味的，lz 加了香菜和醋还有麻酱；花甲不太行，有点小，吃完数了一下七个壳，吃到一个有沙子。总结：价格不高，如果看到外边牌子想吃了，尝一次不觉得白花钱。'
  },
  {
    id: 'huiyuan-3-zixuancai',
    name: '慧园三楼自选菜',
    cover: 'https://pic1.imgdb.cn/i/034w9gKThM8cOdo9fwuyWU.webp',
    gallery: [
      'https://pic1.imgdb.cn/i/034w9gKThM8cOdo9fwuyWU.webp',
      'https://pic1.imgdb.cn/i/034w9gHiEJH9JrvoqTZw6o.webp',
      'https://pic1.imgdb.cn/i/034w9gJVM7XZerVsiPvSVy.webp'
    ],
    category: 'canteen',
    campus: 'h',
    location: '慧园三楼',
    price: '¥12/斤（一般 9-11 元）',
    tags: ['自选菜', '米饭可续', '免费汤'],
    recommend: '甜红薯、当季特色菜',
    desc: '今天吃慧园三楼自选菜，这家 lz 十分推荐，每次上三楼之后门口会有个牌子讲这周的特色菜。口味：有时候会有些好吃的菜，比如这个甜红薯基本上 lz 每次都拿几个当饭后甜点，大部分菜中规中矩。价格：12 一斤，一般人应该吃不到 12，lz 基本上 9 到 11 解决。总结：怀疑这家来了个策划，这么一改感觉比以前强了，米饭可续，还有免费的汤。（评论区反馈：现在免费汤可能没了，加米收费情况也可能有变化。）'
  }
]

export function getFoodPhotos(item) {
  return photoList(item || {})
}

export function getFoodCategoryLabel(key) {
  return FOOD_CATEGORIES.find(category => category.key === key)?.label || '其他'
}

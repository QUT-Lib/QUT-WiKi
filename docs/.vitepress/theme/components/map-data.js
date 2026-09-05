/**
 * QUTWiKi 校园地图数据
 * 坐标统一使用 GCJ02（高德坐标系），从高德拾取器获取：https://lbs.amap.com/tools/picker
 * 添加点位：在 BUILDINGS 数组追加 { id, name, category, campusId, coord: [经度, 纬度], desc }
 */

export const CATEGORY_CONFIG = {
  teaching:   { label: '教学楼',   color: '#015D95' },
  dormitory:  { label: '学生宿舍', color: '#2C8AC9' },
  canteen:    { label: '食堂',     color: '#5BA3D6' },
  library:    { label: '图书馆',   color: '#01416B' },
  sports:     { label: '运动场馆', color: '#9BC4E2' },
  admin:      { label: '行政楼',   color: '#015D95' },
  gate:       { label: '校门',     color: '#2C8AC9' },
  hospital:   { label: '校医院',   color: '#5BA3D6' },
  theater:    { label: '剧场',     color: '#0E6FA8' },
  busstation: { label: '校车站',   color: '#5A82B8' },
  landmark:   { label: '地标建筑', color: '#015D95' },
  college:    { label: '学院楼',   color: '#0E6FA8' },
  food:       { label: '附近美食', color: '#7BA8E0' },
  shop:       { label: '商铺',     color: '#6C8FD4' },
  express:    { label: '快递点',   color: '#4A7CC0' },
  transit:    { label: '轨道交通', color: '#3B6BA5' }
}

/* 分类 SVG 图标 path 数据（Lucide 风格，抄自 CQU-openlib markerIcons.ts） */
export const CATEGORY_ICON_PATHS = {
  teaching:
    '<path d="M14 21v-3a2 2 0 0 0-4 0v3"/><path d="M18 5v16"/><path d="m4 6 7.106-3.79a2 2 0 0 1 1.788 0L20 6"/><path d="m6 11-3.52 2.147a1 1 0 0 0-.48.854V19a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-5a1 1 0 0 0-.48-.853L18 11"/><path d="M6 5v16"/><circle cx="12" cy="9" r="2"/>',
  dormitory:
    '<path d="M2 20v-8a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v8"/><path d="M4 10V6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v4"/><path d="M12 4v6"/><path d="M2 18h20"/>',
  canteen:
    '<path d="M3 2v7c0 1.1.9 2 2 2h4a2 2 0 0 0 2-2V2"/><path d="M7 2v20"/><path d="M21 15V2a5 5 0 0 0-5 5v6c0 1.1.9 2 2 2h3Zm0 0v7"/>',
  library:
    '<path d="m16 6 4 14"/><path d="M12 6v14"/><path d="M8 8v12"/><path d="M4 4v16"/>',
  sports:
    '<path d="M17.596 12.768a2 2 0 1 0 2.829-2.829l-1.768-1.767a2 2 0 0 0 2.828-2.829l-2.828-2.828a2 2 0 0 0-2.829 2.828l-1.767-1.768a2 2 0 1 0-2.829 2.829z"/><path d="m2.5 21.5 1.4-1.4"/><path d="m20.1 3.9 1.4-1.4"/><path d="M5.343 21.485a2 2 0 1 0 2.829-2.828l1.767 1.768a2 2 0 1 0 2.829-2.829l-6.364-6.364a2 2 0 1 0-2.829 2.829l1.768 1.767a2 2 0 0 0-2.828 2.829z"/><path d="m9.6 14.4 4.8-4.8"/>',
  admin:
    '<path d="M10 12h4"/><path d="M10 8h4"/><path d="M14 21v-3a2 2 0 0 0-4 0v3"/><path d="M6 10H4a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-2"/><path d="M6 21V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v16"/>',
  gate: '<path d="M11 20H2"/><path d="M11 4.562v16.157a1 1 0 0 0 1.242.97L19 20V5.562a2 2 0 0 0-1.515-1.94l-4-1A2 2 0 0 0 11 4.561z"/><path d="M11 4H8a2 2 0 0 0-2 2v14"/><path d="M14 12h.01"/><path d="M22 20h-3"/>',
  hospital:
    '<path d="M12 7v4"/><path d="M14 21v-3a2 2 0 0 0-4 0v3"/><path d="M14 9h-4"/><path d="M18 11h2a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-9a2 2 0 0 1 2-2h2"/><path d="M18 21V5a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16"/>',
  theater:
    '<path d="M10 11h.01"/><path d="M14 6h.01"/><path d="M18 6h.01"/><path d="M6.5 13.1h.01"/><path d="M22 5c0 9-4 12-6 12s-6-3-6-12c0-2 2-3 6-3s6 1 6 3"/><path d="M17.4 9.9c-.8.8-2 .8-2.8 0"/><path d="M10.1 7.1C9 7.2 7.7 7.7 6 8.6c-3.5 2-4.7 3.9-3.7 5.6 4.5 7.8 9.5 8.4 11.2 7.4.9-.5 1.9-2.1 1.9-4.7"/><path d="M9.1 16.5c.3-1.1 1.4-1.7 2.4-1.4"/>',
  busstation:
    '<path d="M4 6 2 7"/><path d="M10 6h4"/><path d="m22 7-2-1"/><rect width="16" height="16" x="4" y="3" rx="2"/><path d="M4 11h16"/><path d="M8 15h.01"/><path d="M16 15h.01"/><path d="M6 19v2"/><path d="M18 21v-2"/>',
  transit:
    '<path d="M8 3.1V7a4 4 0 0 0 8 0V3.1"/><path d="m9 15-1-1"/><path d="m15 15 1-1"/><path d="M9 19c-2.8 0-5-2.2-5-5v-4a8 8 0 0 1 16 0v4c0 2.8-2.2 5-5 5Z"/><path d="m8 19-2 3"/><path d="m16 19 2 3"/>',
  landmark:
    '<path d="M10 18v-7"/><path d="M11.12 2.198a2 2 0 0 1 1.76.006l7.866 3.847c.476.233.31.949-.22.949H3.474c-.53 0-.695-.716-.22-.949z"/><path d="M14 18v-7"/><path d="M18 18v-7"/><path d="M3 22h18"/><path d="M6 18v-7"/>',
  college:
    '<path d="M21.42 10.922a1 1 0 0 0-.019-1.838L12.83 5.18a2 2 0 0 0-1.66 0L2.6 9.08a1 1 0 0 0 0 1.832l8.57 3.908a2 2 0 0 0 1.66 0z"/><path d="M22 10v6"/><path d="M6 12.5V16a6 3 0 0 0 12 0v-3.5"/>',
  food: '<path d="M12 21a9 9 0 0 0 9-9H3a9 9 0 0 0 9 9Z"/><path d="M7 21h10"/><path d="M19.5 12 22 6"/><path d="M16.25 3c.27.1.8.53.75 1.36-.06.83-.93 1.2-1 2.02-.05.78.34 1.24.73 1.62"/><path d="M11.25 3c.27.1.8.53.74 1.36-.05.83-.93 1.2-.98 2.02-.06.78.33 1.24.72 1.62"/><path d="M6.25 3c.27.1.8.53.75 1.36-.06.83-.93 1.2-1 2.02-.05.78.34 1.24.74 1.62"/>',
  shop: '<path d="M3 9l1-5h16l1 5"/><path d="M5 13v7h14v-7"/><path d="M9 20v-6h6v6"/><path d="M3 9a2 2 0 0 0 4 0 2 2 0 0 0 4 0 2 2 0 0 0 4 0 2 2 0 0 0 4 0 2 2 0 0 0 4 0"/>',
  express:
    '<path d="M12 22v-9"/><path d="M15.17 2.21a1.67 1.67 0 0 1 1.63 0L21 4.57a1.93 1.93 0 0 1 0 3.36L8.82 14.79a1.655 1.655 0 0 1-1.64 0L3 12.43a1.93 1.93 0 0 1 0-3.36z"/><path d="M20 13v3.87a2.06 2.06 0 0 1-1.11 1.83l-6 3.08a1.93 1.93 0 0 1-1.78 0l-6-3.08A2.06 2.06 0 0 1 4 16.87V13"/><path d="M21 12.43a1.93 1.93 0 0 0 0-3.36L8.83 2.2a1.64 1.64 0 0 0-1.63 0L3 4.57a1.93 1.93 0 0 0 0 3.36l12.18 6.86a1.636 1.636 0 0 0 1.63 0z"/>'
}

export const CAMPUS_CONFIG = {
  h: { name: '黄岛校区', coord: [120.204898, 35.974005], zoom: 16 },
  s: { name: '市北校区', coord: [120.370843, 36.101175], zoom: 16 },
  l: { name: '临沂校区', coord: [118.271856, 35.187084], zoom: 16 }
}

export const FILTER_LIST = [
  { key: 'all',        label: '全部',     icon: 'fa-th-large' },
  { key: 'teaching',   label: '教学楼',   icon: 'fa-graduation-cap' },
  { key: 'dormitory',  label: '学生宿舍', icon: 'fa-building' },
  { key: 'canteen',    label: '食堂',     icon: 'fa-cutlery' },
  { key: 'library',    label: '图书馆',   icon: 'fa-book' },
  { key: 'sports',     label: '运动场馆', icon: 'fa-futbol-o' },
  { key: 'admin',      label: '行政楼',   icon: 'fa-briefcase' },
  { key: 'gate',       label: '校门',     icon: 'fa-flag' },
  { key: 'hospital',   label: '校医院',   icon: 'fa-hospital-o' },
  { key: 'theater',    label: '剧场',     icon: 'fa-ticket' },
  { key: 'busstation', label: '校车站',   icon: 'fa-bus' },
  { key: 'landmark',   label: '地标建筑', icon: 'fa-star' },
  { key: 'college',    label: '学院楼',   icon: 'fa-university' },
  { key: 'food',       label: '附近美食', icon: 'fa-coffee' },
  { key: 'shop',       label: '商铺',     icon: 'fa-shopping-bag' },
  { key: 'express',    label: '快递/外卖点',   icon: 'fa-archive' },
  { key: 'transit',    label: '轨道交通', icon: 'fa-train' }
]

export const BUILDINGS = [
  {
    id: 'h_teaching_01',
    name: '一号教学楼',
    category: 'teaching',
    campusId: 'h',
    coord: [120.204472,35.977797],
    desc: '黄岛校区主教学楼，中部弧形建筑。'
  },
  {
    id: 'h_teaching_02',
    name: '二号教学楼',
    category: 'teaching',
    campusId: 'h',
    coord: [120.204057,35.974134],
    desc: '新教学楼，位于礼贤广场西南侧。'
  },
  {
    id: 'h_college_01',
    name: '实验楼',
    category: 'college',
    campusId: 'h',
    coord: [120.206655,35.971914],
    desc: '中央院系区实验楼，供各学院实验教学、竞赛及课题组科研实验使用。'
  },
  {
    id: 'h_library_01',
    name: '图书馆',
    category: 'library',
    campusId: 'h',
    coord: [120.20438,35.976418],
    desc: '位于一号教学楼与礼贤广场之间，支持人脸/校园卡进入，自习区一座一码。'
  },
  {
    id: 'h_landmark_01',
    name: '礼贤广场',
    category: 'landmark',
    campusId: 'h',
    coord: [120.204446,35.975244],
    desc: '用于学院升旗仪式、奖学金颁发、毕业典礼、百团大战等活动。'
  },
  {
    id: 'h_canteen_01',
    name: '荷园餐厅',
    category: 'canteen',
    campusId: 'h',
    coord: [120.206732,35.975231],
    desc: '较新的餐厅，内部装修更现代化。'
  },
  {
    id: 'h_canteen_02',
    name: '祥园餐厅',
    category: 'canteen',
    campusId: 'h',
    coord: [120.202231,35.974954],
    desc: '靠近西区宿舍。'
  },
  {
    id: 'h_canteen_03',
    name: '慧园餐厅',
    category: 'canteen',
    campusId: 'h',
    coord: [120.202237,35.977989],
    desc: '靠近北区宿舍。'
  },
  {
    id: 'h_dormitory_n01',
    name: '北区1号公寓',
    category: 'dormitory',
    campusId: 'h',
    coord: [120.201709,35.978887],
    desc: '北区1号公寓（配电梯，北区学生公寓），靠近慧园餐厅。'
  },
  {
    id: 'h_dormitory_n02',
    name: '北区2号公寓',
    category: 'dormitory',
    campusId: 'h',
    coord: [120.202167,35.979117],
    desc: '北区2号公寓（配电梯，北区学生公寓），靠近慧园餐厅，北区2号公寓东南方向为校医院。'
  },
  {
    id: 'h_dormitory_n03',
    name: '北区3号公寓',
    category: 'dormitory',
    campusId: 'h',
    coord: [120.202838,35.979464],
    desc: '北区3号公寓（配电梯，北区学生公寓），靠近慧园餐厅。'
  },
  {
    id: 'h_dormitory_n04',
    name: '北区4号公寓',
    category: 'dormitory',
    campusId: 'h',
    coord: [120.203384,35.979742],
    desc: '北区4号公寓（配电梯，北区学生公寓），靠近慧园餐厅。'
  },
  {
    id: 'h_dormitory_n05',
    name: '北区5号公寓',
    category: 'dormitory',
    campusId: 'h',
    coord: [120.204077,35.979355],
    desc: '北区5号公寓（配电梯，北区学生公寓），靠近慧园餐厅。'
  },
  {
    id: 'h_dormitory_n06',
    name: '北区6号公寓',
    category: 'dormitory',
    campusId: 'h',
    coord: [120.204769,35.97938],
    desc: '北区6号公寓（配电梯，北区学生公寓），靠近慧园餐厅。'
  },
  {
    id: 'h_dormitory_n07',
    name: '北区7号公寓',
    category: 'dormitory',
    campusId: 'h',
    coord: [120.204133,35.979967],
    desc: '北区7号公寓（配电梯，北区学生公寓），靠近慧园餐厅。'
  },
  {
    id: 'h_dormitory_n08',
    name: '北区8号公寓',
    category: 'dormitory',
    campusId: 'h',
    coord: [120.204832,35.979942],
    desc: '北区8号公寓（配电梯，北区学生公寓），靠近慧园餐厅。'
  },
  {
    id: 'h_dormitory_n09',
    name: '北区9号公寓',
    category: 'dormitory',
    campusId: 'h',
    coord: [120.205544,35.979386],
    desc: '北区9号公寓（配电梯，北区学生公寓），靠近慧园餐厅。'
  },
  {
    id: 'h_dormitory_n10',
    name: '北区10号公寓',
    category: 'dormitory',
    campusId: 'h',
    coord: [120.205539,35.97981],
    desc: '北区10号公寓（配电梯，北区学生公寓），靠近慧园餐厅。'
  },
  {
    id: 'h_dormitory_w01',
    name: '西区1号公寓',
    category: 'dormitory',
    campusId: 'h',
    coord: [120.201749,35.975091],
    desc: '西区1号公寓（无电梯，西区学生公寓），靠近西操场与祥园、慧园餐厅。'
  },
  {
    id: 'h_dormitory_w02',
    name: '西区2号公寓',
    category: 'dormitory',
    campusId: 'h',
    coord: [120.201119,35.975556],
    desc: '西区2号公寓（无电梯，西区学生公寓），靠近西操场与祥园、慧园餐厅。'
  },
  {
    id: 'h_dormitory_w03',
    name: '西区3号公寓',
    category: 'dormitory',
    campusId: 'h',
    coord: [120.201145,35.97596],
    desc: '西区3号公寓（无电梯，西区学生公寓），靠近西操场与祥园、慧园餐厅。'
  },
  {
    id: 'h_dormitory_w04',
    name: '西区4号公寓',
    category: 'dormitory',
    campusId: 'h',
    coord: [120.201181,35.976348],
    desc: '西区4号公寓（无电梯，西区学生公寓），靠近西操场与祥园、慧园餐厅。'
  },
  {
    id: 'h_dormitory_w05',
    name: '西区5号公寓',
    category: 'dormitory',
    campusId: 'h',
    coord: [120.200982,35.976843],
    desc: '西区5号公寓（无电梯，西区学生公寓），靠近西操场与祥园、慧园餐厅。'
  },
  {
    id: 'h_dormitory_w06',
    name: '西区6号公寓',
    category: 'dormitory',
    campusId: 'h',
    coord: [120.20127,35.977269],
    desc: '西区6号公寓（无电梯，西区学生公寓），靠近西操场与祥园、慧园餐厅。'
  },
  {
    id: 'h_dormitory_w07',
    name: '西区7号公寓',
    category: 'dormitory',
    campusId: 'h',
    coord: [120.201939,35.977669],
    desc: '西区7号公寓（无电梯，西区学生公寓），靠近西操场与祥园、慧园餐厅。'
  },
  {
    id: 'h_dormitory_w08',
    name: '西区8号公寓',
    category: 'dormitory',
    campusId: 'h',
    coord: [120.201131,35.977869],
    desc: '西区8号公寓（无电梯，西区学生公寓），靠近西操场与祥园、慧园餐厅。'
  },
  {
    id: 'h_dormitory_w09',
    name: '西区9号公寓',
    category: 'dormitory',
    campusId: 'h',
    coord: [120.202007,35.978448],
    desc: '西区9号公寓（无电梯，西区学生公寓），靠近西操场与祥园、慧园餐厅。'
  },
  {
    id: 'h_dormitory_w10',
    name: '西区10号公寓',
    category: 'dormitory',
    campusId: 'h',
    coord: [120.200635,35.97739],
    desc: '西区10号公寓（无电梯，西区学生公寓），靠近西操场与祥园、慧园餐厅。'
  },
  {
    id: 'h_dormitory_e01',
    name: '东区1号公寓',
    category: 'dormitory',
    campusId: 'h',
    coord: [120.207982,35.975534],
    desc: '东区1号公寓（配电梯，东区学生公寓），靠近东操场与荷园餐厅，楼下有打印店、理发店、超市、东区菜鸟驿站。'
  },
  {
    id: 'h_dormitory_e02',
    name: '东区2号公寓',
    category: 'dormitory',
    campusId: 'h',
    coord: [120.208428,35.975949],
    desc: '东区2号公寓（配电梯，东区学生公寓），靠近东操场与荷园餐厅。'
  },
  {
    id: 'h_dormitory_e03',
    name: '东区3号公寓',
    category: 'dormitory',
    campusId: 'h',
    coord: [120.208451,35.976563],
    desc: '东区3号公寓（配电梯，东区学生公寓），靠近东操场与荷园餐厅。'
  },
  {
    id: 'h_dormitory_e04',
    name: '东区4号公寓',
    category: 'dormitory',
    campusId: 'h',
    coord: [120.208494,35.975039],
    desc: '东区4号公寓（配电梯，东区学生公寓），靠近东操场与荷园餐厅。'
  },
  {
    id: 'h_dormitory_e05',
    name: '东区5号公寓',
    category: 'dormitory',
    campusId: 'h',
    coord: [120.209146,35.975478],
    desc: '东区5号公寓（配电梯，东区学生公寓），靠近东操场与荷园餐厅。'
  },
  {
    id: 'h_dormitory_e06',
    name: '东区6号公寓',
    category: 'dormitory',
    campusId: 'h',
    coord: [120.209216,35.975976],
    desc: '东区6号公寓（配电梯，东区学生公寓），靠近东操场与荷园餐厅。'
  },
  {
    id: 'h_dormitory_e07',
    name: '东区7号公寓',
    category: 'dormitory',
    campusId: 'h',
    coord: [120.209262,35.976536],
    desc: '东区7号公寓（配电梯，东区学生公寓），靠近东操场与荷园餐厅，楼下有东区学生服务中心。'
  },
  {
    id: 'h_sports_01',
    name: '西操场',
    category: 'sports',
    campusId: 'h',
    coord: [120.20237,35.97623],
    desc: '学校主要运动场地，2025 年暑假翻新，西操场下有各类餐饮商铺。'
  },
  {
    id: 'h_sports_02',
    name: '东操场',
    category: 'sports',
    campusId: 'h',
    coord: [120.206612,35.976481],
    desc: '靠近东区宿舍。'
  },
  {
    id: 'h_sports_03',
    name: '室内体育馆',
    category: 'sports',
    campusId: 'h',
    coord: [120.207519,35.976355],
    desc: '主要用于健美操等室内课程，面积较小。'
  },
  {
    id: 'h_sports_04',
    name: '羽毛球馆',
    category: 'sports',
    campusId: 'h',
    coord: [120.204737,35.978853],
    desc: '学校 2026 年新增设施，校内师生羽毛球课免费使用。'
  },
  {
    id: 'h_sports_05',
    name: '露天运动场（篮球/网球/排球）',
    category: 'sports',
    campusId: 'h',
    coord: [120.203651,35.97867],
    desc: '露天的篮球场、网球场、排球场，集中在北区公寓和一号教学楼之间。'
  },
  {
    id: 'h_food_01',
    name: '西操场下餐饮商铺',
    category: 'food',
    campusId: 'h',
    coord: [120.202899,35.976352],
    desc: '西操场下有肯德基、天下好面、临榆炸鸡腿、茶百道、云南傣族米线、橙堡（多摊位）、好想来、超市等。'
  },
  {
    id: 'h_express_00',
    name: '北区外卖点',
    category: 'express',
    campusId: 'h',
    coord: [120.203668,35.98031],
    desc: '位于北区4公寓和7公寓之间，收取外卖。'
  },
  {
    id: 'h_express_01',
    name: '西菜鸟驿站',
    category: 'express',
    campusId: 'h',
    coord: [120.202863,35.976703],
    desc: '位于西操场下（西操场东侧），收取 200 号以下的快递（中通、圆通、申通、韵达、极兔等）。'
  },
  {
    id: 'h_express_02',
    name: '东菜鸟驿站',
    category: 'express',
    campusId: 'h',
    coord: [120.208302,35.976257],
    desc: '位于东区公寓楼下，收取 200 号以上的快递（中通、圆通、申通、韵达、极兔等）。'
  },
  {
    id: 'h_express_03',
    name: '顺丰快递点',
    category: 'express',
    campusId: 'h',
    coord: [120.20403,35.979858],
    desc: '位于北区公寓楼下，收取顺丰快递。'
  },
  {
    id: 'h_express_04',
    name: '京东快递点',
    category: 'express',
    campusId: 'h',
    coord: [120.204153,35.979834],
    desc: '位于北区公寓楼下，收取京东快递。'
  },
  {
    id: 'h_express_05',
    name: '邮政快递点',
    category: 'express',
    campusId: 'h',
    coord: [120.202607,35.9755],
    desc: '位于西操场下（西操场南侧），收取邮政快递。'
  },
  {
    id: 'h_hospital_01',
    name: '校医院',
    category: 'hospital',
    campusId: 'h',
    coord: [120.203131,35.978872],
    desc: '位于北区 2 号公寓东南方向，负责学生体检与日常就诊，设有药房，支持大学生医保购药。'
  },
  {
    id: 'h_food_02',
    name: '翰墨轩打印店',
    category: 'shop',
    campusId: 'h',
    coord: [120.202456,35.977137],
    desc: '位于西操场下东北入口处，提供打印、复印、装订等服务。'
  },
  {
    id: 'h_food_03',
    name: '东区学生服务中心',
    category: 'shop',
    campusId: 'h',
    coord: [120.208323,35.976362],
    desc: '位于东区宿舍下，提供打印等服务。'
  },
  {
    id: 'h_gate_01',
    name: '黄岛校区南1号门',
    category: 'gate',
    campusId: 'h',
    coord: [120.210024,35.968035],
    desc: '黄岛校区南1号门（嘉陵江路）。'
  },
  {
    id: 'h_gate_02',
    name: '黄岛校区南2号门',
    category: 'gate',
    campusId: 'h',
    coord: [120.208859,35.968175],
    desc: '黄岛校区南2号门（嘉陵江路）。'
  },
  {
    id: 'h_admin_01',
    name: '行政楼',
    category: 'admin',
    campusId: 'h',
    coord: [120.205283,35.971689],
    desc: '学校行政办公场所。'
  },
  {
    id: 's_teaching_01',
    name: '10号楼',
    category: 'teaching',
    campusId: 's',
    coord: [120.370441,36.101934],
    desc: '市北校区教学楼（高德POI）。'
  },
  {
    id: 's_teaching_04',
    name: '一号教学楼',
    category: 'teaching',
    campusId: 's',
    coord: [120.371245,36.099380],
    desc: '市北校区主教学楼（南院），位置经高德POI「卓越人才培养办公室（1号教学楼309）」与「抚顺路11号甲（1号教学楼西北80米）」交叉确认。'
  },
  {
    id: 's_teaching_02',
    name: '暖通实验楼',
    category: 'teaching',
    campusId: 's',
    coord: [120.372275,36.100425],
    desc: '位于市北校区南区（高德POI）。'
  },
  {
    id: 's_teaching_03',
    name: 'BIM实验教学中心',
    category: 'teaching',
    campusId: 's',
    coord: [120.370816,36.101944],
    desc: '位于理工大学3号实验楼（高德POI）。'
  },
  {
    id: 's_college_01',
    name: '建筑馆',
    category: 'college',
    campusId: 's',
    coord: [120.371958,36.098772],
    desc: '建筑与城乡规划学院所在建筑。'
  },
  {
    id: 's_college_02',
    name: '滨海仁居研究中心',
    category: 'college',
    campusId: 's',
    coord: [120.370883,36.098352],
    desc: '滨海人居环境相关研究机构所在地。'
  },
  {
    id: 's_college_03',
    name: '建筑与城乡规划学院',
    category: 'college',
    campusId: 's',
    coord: [120.371933,36.098678],
    desc: '位于建筑馆（高德POI）。'
  },
  {
    id: 's_college_04',
    name: '国际学院',
    category: 'college',
    campusId: 's',
    coord: [120.371127,36.100080],
    desc: '市北校区国际学院（高德POI）。'
  },
  {
    id: 's_college_05',
    name: '艺术与设计学院',
    category: 'college',
    campusId: 's',
    coord: [120.370086,36.100520],
    desc: '市北校区艺术与设计学院（高德POI）。'
  },
  {
    id: 's_college_06',
    name: '机械实验室',
    category: 'college',
    campusId: 's',
    coord: [120.372019,36.101833],
    desc: '市北校区机械实验室（高德POI）。'
  },
  {
    id: 's_college_07',
    name: '建筑设计研究院',
    category: 'college',
    campusId: 's',
    coord: [120.374022,36.097842],
    desc: '市北校区建筑设计研究院（高德POI）。'
  },
  {
    id: 's_landmark_01',
    name: '南院',
    category: 'landmark',
    campusId: 's',
    coord: [120.371043,36.099099],
    desc: '青岛理工大学南院（高德POI）。'
  },
  {
    id: 's_landmark_02',
    name: '家属楼',
    category: 'landmark',
    campusId: 's',
    coord: [120.369102,36.101222],
    desc: '青岛理工大学家属楼（高德POI）。'
  },
  {
    id: 's_library_01',
    name: '图书馆',
    category: 'library',
    campusId: 's',
    coord: [120.372609,36.099799],
    desc: '市北校区图书馆，供自习与图书借阅。'
  },
  {
    id: 's_theater_01',
    name: '礼堂',
    category: 'theater',
    campusId: 's',
    coord: [120.372725,36.101525],
    desc: '用于举办讲座、演出与大型活动的场所。'
  },
  {
    id: 's_canteen_01',
    name: '食堂（思源餐厅）',
    category: 'canteen',
    campusId: 's',
    coord: [120.371154,36.101604],
    desc: '市北校区食堂。'
  },
  {
    id: 's_dormitory_01',
    name: '学生宿舍',
    category: 'dormitory',
    campusId: 's',
    coord: [120.372052,36.100509],
    desc: '市北校区学生宿舍（高德POI）。'
  },
  {
    id: 's_sports_01',
    name: '篮球场',
    category: 'sports',
    campusId: 's',
    coord: [120.372267,36.100789],
    desc: '露天篮球场。'
  },
  {
    id: 's_admin_01',
    name: '卓越人才培养办公室',
    category: 'admin',
    campusId: 's',
    coord: [120.371245,36.099380],
    desc: '位于市北校区1号教学楼309（高德POI）。'
  },
  {
    id: 's_admin_02',
    name: '校园卡管理中心',
    category: 'admin',
    campusId: 's',
    coord: [120.370864,36.099308],
    desc: '市北校区校园卡管理中心（高德POI）。'
  },
  {
    id: 's_admin_03',
    name: '财务自助服务中心',
    category: 'admin',
    campusId: 's',
    coord: [120.371725,36.099275],
    desc: '市北校区财务自助服务中心（高德POI）。'
  },
  {
    id: 's_express_01',
    name: '青岛理工大学快递站',
    category: 'express',
    campusId: 's',
    coord: [120.371775,36.100325],
    desc: '市北校区快递站（高德POI）。'
  },
  {
    id: 's_express_02',
    name: '丽丰菜鸟驿站',
    category: 'express',
    campusId: 's',
    coord: [120.368349,36.100893],
    desc: '市北校区丽丰菜鸟驿站（高德POI）。'
  },
  {
    id: 's_food_01',
    name: '百度图文',
    category: 'library',
    campusId: 's',
    coord: [120.371432,36.101743],
    desc: '理工大学北院食堂楼下网点（高德POI）。'
  },
  {
    id: 's_food_02',
    name: '理工大学夜市',
    category: 'food',
    campusId: 's',
    coord: [120.370037,36.100221],
    desc: '抚顺路与抚顺支路交叉口东侧（高德POI）。'
  },
  {
    id: 'l_teaching_01',
    name: '弘文楼',
    category: 'teaching',
    campusId: 'l',
    coord: [118.272733,35.187697],
    desc: '临沂校区教学楼。'
  },
  {
    id: 'l_teaching_02',
    name: '行远楼',
    category: 'teaching',
    campusId: 'l',
    coord: [118.273356,35.187124],
    desc: '临沂校区教学楼。'
  },
  {
    id: 'l_teaching_03',
    name: '知源楼',
    category: 'teaching',
    campusId: 'l',
    coord: [118.271323,35.186651],
    desc: '临沂校区教学楼。'
  },
  {
    id: 'l_teaching_04',
    name: '敏行楼',
    category: 'teaching',
    campusId: 'l',
    coord: [118.272411,35.186876],
    desc: '临沂校区教学楼。'
  },
  {
    id: 'l_teaching_05',
    name: '知心楼',
    category: 'teaching',
    campusId: 'l',
    coord: [118.271253,35.187936],
    desc: '临沂校区教学楼。'
  },
  {
    id: 'l_college_01',
    name: '筑韵楼',
    category: 'college',
    campusId: 'l',
    coord: [118.272596,35.186061],
    desc: '临沂校区学院楼。'
  },
  {
    id: 'l_hospital_01',
    name: '校医院',
    category: 'hospital',
    campusId: 'l',
    coord: [118.269555,35.187855],
    desc: '临沂校区校医院，负责日常就诊与体检。'
  },
  {
    id: 'l_canteen_01',
    name: '西餐厅（文苑餐厅）',
    category: 'canteen',
    campusId: 'l',
    coord: [118.269615,35.187218],
    desc: '临沂校区西侧餐厅。'
  },
  {
    id: 'l_canteen_02',
    name: '东餐厅（知苑餐厅）',
    category: 'canteen',
    campusId: 'l',
    coord: [118.274048,35.187027],
    desc: '临沂校区东侧餐厅。'
  },
  {
    id: 'l_dormitory_01',
    name: '一号公寓',
    category: 'dormitory',
    campusId: 'l',
    coord: [118.270121,35.188731],
    desc: '临沂校区北区学生公寓。'
  },
  {
    id: 'l_dormitory_02',
    name: '二号公寓',
    category: 'dormitory',
    campusId: 'l',
    coord: [118.270664,35.188736],
    desc: '临沂校区北区学生公寓。'
  },
  {
    id: 'l_dormitory_03',
    name: '三号公寓',
    category: 'dormitory',
    campusId: 'l',
    coord: [118.271207,35.188741],
    desc: '临沂校区北区学生公寓。'
  },
  {
    id: 'l_dormitory_04',
    name: '四号公寓',
    category: 'dormitory',
    campusId: 'l',
    coord: [118.271750,35.188746],
    desc: '临沂校区北区学生公寓。'
  },
  {
    id: 'l_dormitory_05',
    name: '五号公寓',
    category: 'dormitory',
    campusId: 'l',
    coord: [118.272293,35.188751],
    desc: '临沂校区北区学生公寓。'
  },
  {
    id: 'l_dormitory_06',
    name: '六号公寓',
    category: 'dormitory',
    campusId: 'l',
    coord: [118.272836,35.188756],
    desc: '临沂校区北区学生公寓。'
  },
  {
    id: 'l_dormitory_07',
    name: '七号公寓',
    category: 'dormitory',
    campusId: 'l',
    coord: [118.270121,35.185219],
    desc: '临沂校区南区学生公寓。'
  },
  {
    id: 'l_dormitory_08',
    name: '八号公寓',
    category: 'dormitory',
    campusId: 'l',
    coord: [118.270664,35.185224],
    desc: '临沂校区南区学生公寓。'
  },
  {
    id: 'l_dormitory_09',
    name: '九号公寓',
    category: 'dormitory',
    campusId: 'l',
    coord: [118.271207,35.185229],
    desc: '临沂校区南区学生公寓。'
  },
  {
    id: 'l_dormitory_10',
    name: '十号公寓',
    category: 'dormitory',
    campusId: 'l',
    coord: [118.271750,35.185234],
    desc: '临沂校区南区学生公寓。'
  },
  {
    id: 'l_dormitory_11',
    name: '十一号公寓',
    category: 'dormitory',
    campusId: 'l',
    coord: [118.272293,35.185239],
    desc: '临沂校区南区学生公寓。'
  },
  {
    id: 'l_dormitory_12',
    name: '十二号公寓',
    category: 'dormitory',
    campusId: 'l',
    coord: [118.272836,35.185244],
    desc: '临沂校区南区学生公寓。'
  },
  {
    id: 'l_sports_01',
    name: '西操场',
    category: 'sports',
    campusId: 'l',
    coord: [118.268426,35.186497],
    desc: '临沂校区西侧田径运动场。'
  },
  {
    id: 'l_sports_02',
    name: '东操场',
    category: 'sports',
    campusId: 'l',
    coord: [118.274562,35.186252],
    desc: '临沂校区东侧田径运动场。'
  },
  {
    id: 'l_sports_03',
    name: '体育馆',
    category: 'sports',
    campusId: 'l',
    coord: [118.273521,35.188028],
    desc: '临沂校区室内体育馆，供室内课程与比赛使用。'
  }
]

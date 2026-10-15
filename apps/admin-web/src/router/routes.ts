import type { RouteRecordRaw } from 'vue-router'

import Layout from '@/layout/index.vue'

/**
 * 静态路由表。
 *
 * 权限约定：
 *  - `meta.permission` 为按钮级/路由级权限码，路由守卫按 /auth/me 返回的 permissions 拦截；
 *  - `meta.title` 用于菜单、面包屑、标签页与 document.title；
 *  - `meta.icon` 为 @element-plus/icons-vue 的组件名；
 *  - `meta.hidden` 为 true 时不显示在侧边菜单。
 */
export const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/index.vue'),
    meta: { title: '登录', hidden: true, public: true }
  },
  {
    path: '/register', name: 'PublicRegister', component: () => import('@/views/portal/register.vue'),
    meta: { title: '注册平台用户', hidden: true, public: true }
  },
  {
    path: '/consult', name: 'PublicConsult', component: () => import('@/views/portal/consult.vue'),
    meta: { title: '留下合作需求', hidden: true, public: true }
  },
  {
    path: '/account', name: 'PublicAccount', component: () => import('@/views/portal/account.vue'),
    meta: { title: '我的需求与企业资料', hidden: true }
  },
  {
    path: '/home',
    name: 'ShowcaseHome',
    component: () => import('@/views/showcase/index.vue'),
    meta: { title: '平台首页', hidden: true, public: true }
  },
  {
    path: '/hall',
    redirect: '/supply'
  },
  {
    path: '/merchants',
    redirect: '/enterprises'
  },
  {
    path: '/item/:id',
    redirect: to => `/supply/${to.params.id}`
  },
  {
    path: '/supply', name: 'SupplyHall', component: () => import('@/views/showcase/index.vue'),
    meta: { title: '供应大厅', hidden: true, public: true }
  },
  {
    path: '/supply/:id', name: 'SupplyDetail', component: () => import('@/views/showcase/index.vue'),
    meta: { title: '供应详情', hidden: true, public: true }
  },
  {
    path: '/procurement', name: 'ProcurementHall', component: () => import('@/views/showcase/index.vue'),
    meta: { title: '采购大厅', hidden: true, public: true }
  },
  {
    path: '/enterprises', name: 'EnterpriseHall', component: () => import('@/views/showcase/index.vue'),
    meta: { title: '企业展示', hidden: true, public: true }
  },
  {
    path: '/enterprise/:id', name: 'EnterpriseProfile', component: () => import('@/views/showcase/index.vue'),
    meta: { title: '企业主页', hidden: true, public: true }
  },
  {
    path: '/industry-news', name: 'IndustryNews', component: () => import('@/views/showcase/index.vue'),
    meta: { title: '产业资讯', hidden: true, public: true }
  },
  {
    path: '/matching-service', name: 'MatchingService', component: () => import('@/views/showcase/index.vue'),
    meta: { title: '撮合服务', hidden: true, public: true }
  },
  {
    path: '/purchase/new', name: 'PurchaseRequirementNew', component: () => import('@/views/showcase/index.vue'),
    meta: { title: '发布采购需求', hidden: true, public: true }
  },
  {
    path: '/inquiry/new/:id', name: 'SupplyInquiryNew',
    component: () => import('@/views/showcase/index.vue'),
    meta: { title: '提交询价', hidden: true, public: true }
  },
  {
    path: '/',
    component: Layout,
    redirect: '/home',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/dashboard/index.vue'),
        meta: { title: '数据驾驶舱', icon: 'Odometer', permission: 'data:read', affix: true }
      }
    ]
  },
  {
    path: '/system',
    component: Layout,
    redirect: '/system/user',
    meta: { title: '系统管理', icon: 'Setting' },
    children: [
      {
        path: 'user',
        name: 'SystemUser',
        component: () => import('@/views/system/user/index.vue'),
        meta: { title: '用户管理', icon: 'User', permission: 'user:read' }
      },
      {
        path: 'role',
        name: 'SystemRole',
        component: () => import('@/views/system/role/index.vue'),
        meta: { title: '角色权限', icon: 'Lock', permission: 'role:read' }
      },
      {
        path: 'org',
        name: 'SystemOrg',
        component: () => import('@/views/system/org/index.vue'),
        meta: { title: '组织架构', icon: 'OfficeBuilding', permission: 'org:read' }
      },
      {
        path: 'about',
        name: 'SystemAbout',
        component: () => import('@/views/system/about/index.vue'),
        meta: { title: '关于系统', hidden: true }
      }
    ]
  },
  {
    path: '/merchant',
    component: Layout,
    redirect: '/merchant/enterprise',
    meta: { title: '商户管理', icon: 'Shop' },
    children: [
      {
        path: 'enterprise',
        name: 'MerchantEnterprise',
        component: () => import('@/views/merchant/enterprise/index.vue'),
        meta: { title: '商户档案', icon: 'Postcard', permission: 'merchant:read' }
      },
      {
        path: 'entry',
        name: 'MerchantEntry',
        component: () => import('@/views/merchant/entry/index.vue'),
        meta: { title: '入驻审核', icon: 'DocumentChecked', permission: 'merchant:read' }
      }
    ]
  },
  {
    path: '/product',
    component: Layout,
    redirect: '/product/list',
    meta: { title: '商品中心', icon: 'Goods' },
    children: [
      {
        path: 'category',
        name: 'ProductCategory',
        component: () => import('@/views/product/category/index.vue'),
        meta: { title: '商品分类', icon: 'Grid', permission: 'product:read' }
      },
      {
        path: 'list',
        name: 'ProductList',
        component: () => import('@/views/product/list/index.vue'),
        meta: { title: '商品列表', icon: 'ShoppingBag', permission: 'product:read' }
      },
      {
        path: 'detail/:id',
        name: 'ProductDetail',
        component: () => import('@/views/product/detail/index.vue'),
        meta: { title: '商品详情', icon: 'Tickets', permission: 'product:read', hidden: true }
      }
    ]
  },
  {
    path: '/matching', component: Layout, redirect: '/matching/workbench',
    meta: { title: '撮合中心', icon: 'Connection', roles: ['platform_admin'] },
    children: [
      { path: 'workbench', name: 'MatchingWorkbench', component: () => import('@/views/matching/index.vue'),
        meta: { title: '撮合管理', icon: 'Connection', permission: 'trade:read', roles: ['platform_admin'] } },
      { path: 'leads', name: 'LeadCenter', component: () => import('@/views/matching/leads.vue'),
        meta: { title: '线索中心', icon: 'ChatLineSquare', permission: 'trade:read', roles: ['platform_admin'] } }
    ]
  },
  {
    path: '/inventory',
    component: Layout,
    redirect: '/inventory/warehouse',
    meta: { title: '仓储库存', icon: 'Box' },
    children: [
      {
        path: 'warehouse',
        name: 'InventoryWarehouse',
        component: () => import('@/views/inventory/warehouse/index.vue'),
        meta: { title: '仓库库位', icon: 'House', permission: 'inventory:read' }
      },
      {
        path: 'stock',
        name: 'InventoryStock',
        component: () => import('@/views/inventory/stock/index.vue'),
        meta: { title: '库存查询', icon: 'Coin', permission: 'inventory:read' }
      },
      {
        path: 'move',
        name: 'InventoryMove',
        component: () => import('@/views/inventory/move/index.vue'),
        meta: { title: '出入库与流水', icon: 'Sort', permission: 'inventory:read' }
      }
    ]
  },
  {
    path: '/trade',
    component: Layout,
    redirect: '/trade/inquiry',
    meta: { title: '交易服务', icon: 'ShoppingCart' },
    children: [
      {
        path: 'inquiry',
        name: 'TradeInquiry',
        component: () => import('@/views/trade/inquiry/index.vue'),
        meta: { title: '询价单', icon: 'ChatDotRound', permission: 'trade:read' }
      },
      {
        path: 'inquiry/:id',
        name: 'TradeInquiryDetail',
        component: () => import('@/views/trade/inquiry/detail.vue'),
        meta: { title: '询价详情', icon: 'ChatLineSquare', permission: 'trade:read', hidden: true }
      },
      {
        path: 'order',
        name: 'TradeOrder',
        component: () => import('@/views/trade/order/index.vue'),
        meta: { title: '订单管理', icon: 'List', permission: 'trade:read' }
      },
      {
        path: 'order/:id',
        name: 'TradeOrderDetail',
        component: () => import('@/views/trade/order/detail.vue'),
        meta: { title: '订单详情', icon: 'Document', permission: 'trade:read', hidden: true }
      },
      {
        path: 'contract',
        name: 'TradeContract',
        component: () => import('@/views/trade/contract/index.vue'),
        meta: { title: '合同管理', icon: 'Files', permission: 'trade:read' }
      }
    ]
  },
  {
    path: '/settlement',
    component: Layout,
    redirect: '/settlement/list',
    meta: { title: '结算财务', icon: 'Money' },
    children: [
      {
        path: 'list',
        name: 'SettlementList',
        component: () => import('@/views/settlement/list/index.vue'),
        meta: { title: '结算单', icon: 'Wallet', permission: 'settlement:read' }
      },
      {
        path: 'flow',
        name: 'SettlementFlow',
        component: () => import('@/views/settlement/flow/index.vue'),
        meta: { title: '流水与对账', icon: 'TrendCharts', permission: 'settlement:read' }
      }
    ]
  },
  {
    path: '/park',
    component: Layout,
    redirect: '/park/park',
    meta: { title: '智慧园区', icon: 'OfficeBuilding' },
    children: [
      {
        path: 'park',
        name: 'ParkPark',
        component: () => import('@/views/park/park/index.vue'),
        meta: { title: '园区与区域', icon: 'MapLocation', permission: 'park:read' }
      },
      {
        path: 'stall',
        name: 'ParkStall',
        component: () => import('@/views/park/stall/index.vue'),
        meta: { title: '档口管理', icon: 'Shop', permission: 'park:read' }
      }
    ]
  },
  {
    path: '/trace',
    component: Layout,
    redirect: '/trace/batch',
    meta: { title: '质量溯源', icon: 'Document' },
    children: [
      {
        path: 'batch',
        name: 'TraceBatch',
        component: () => import('@/views/trace/batch/index.vue'),
        meta: { title: '溯源批次', icon: 'Aim', permission: 'trace:read' }
      }
    ]
  },
  {
    path: '/403',
    name: 'Forbidden',
    component: () => import('@/views/error/404.vue'),
    meta: { title: '访问受限', hidden: true, public: true }
  },
  {
    path: '/404',
    name: 'NotFound',
    component: () => import('@/views/error/404.vue'),
    meta: { title: '页面不存在', hidden: true, public: true }
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/404',
    meta: { hidden: true, public: true }
  }
]

export default routes

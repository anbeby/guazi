<script setup lang="ts">
/**
 * 商品列表：筛选 / 新增 / 编辑 / 上架 / 下架 / 审核 / 删除 / 库存查看 / 详情跳转。
 * 接口：/products、/products/{id}、/products/{id}/publish、/offline、/audit、/inventory、/categories/tree
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'

import PageTable from '@/components/PageTable.vue'
import StatusTag from '@/components/StatusTag.vue'
import DictSelect from '@/components/DictSelect.vue'
import FileUpload from '@/components/FileUpload.vue'
import {
  auditProduct,
  createProduct,
  deleteProduct,
  getProduct,
  getProductInventory,
  listProducts,
  offlineProduct,
  publishProduct,
  updateProduct
} from '@/api/product'
import { getCategoryTree } from '@/api/category'
import { listEnterprises } from '@/api/enterprise'
import type {
  Category,
  Enterprise,
  Product,
  ProductInventoryItem,
  ProductPayload,
  ProductQuery
} from '@/api/types'
import { formatDateTime, formatMoney, formatQuantity } from '@/utils/format'

const router = useRouter()

/* 主图可单独替换，避免编辑整条商品时误改报价与库存配置。 */
const imageVisible = ref(false)
const imageSaving = ref(false)
const imageProduct = ref<Product | null>(null)
const imageUrl = ref('')
const imageUploaded = ref(false)

function openImage(row: Product): void {
  imageProduct.value = row
  imageUrl.value = row.main_image || ''
  imageUploaded.value = false
  imageVisible.value = true
}

async function saveImage(): Promise<void> {
  if (!imageProduct.value || !imageUploaded.value || !imageUrl.value) {
    ElMessage.warning('请先上传一张新图片')
    return
  }
  imageSaving.value = true
  try {
    await updateProduct(imageProduct.value.id, { main_image: imageUrl.value })
    ElMessage.success('商品主图已更新，门户和手机端刷新后可见')
    imageVisible.value = false
    await loadList()
  } catch {
    /* 错误由请求拦截器提示 */
  } finally {
    imageSaving.value = false
  }
}

/* ---------------- 列表 ---------------- */
const loading = ref(false)
const list = ref<Product[]>([])
const total = ref(0)
const categories = ref<Category[]>([])
const enterprises = ref<Enterprise[]>([])
const query = reactive<ProductQuery>({
  page: 1,
  page_size: 20,
  keyword: '',
  category_id: null,
  enterprise_id: null,
  status: '',
  grade: '',
  origin: '',
  harvest_year: ''
})

async function loadList(): Promise<void> {
  loading.value = true
  try {
    const data = await listProducts(query)
    list.value = data.items || []
    total.value = data.total || 0
  } catch {
    list.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function handleSearch(): void {
  query.page = 1
  loadList()
}

function handleReset(): void {
  query.keyword = ''
  query.category_id = null
  query.enterprise_id = null
  query.status = ''
  query.grade = ''
  query.origin = ''
  query.harvest_year = ''
  query.page = 1
  loadList()
}

/** 扁平化分类选项 */
const categoryOptions = computed(() => {
  const rows: { label: string; value: number }[] = []
  const walk = (nodes: Category[], depth: number): void => {
    nodes.forEach((node) => {
      rows.push({ label: `${'　'.repeat(depth)}${node.name}`, value: node.id })
      if (node.children?.length) walk(node.children, depth + 1)
    })
  }
  walk(categories.value, 0)
  return rows
})

async function loadOptions(): Promise<void> {
  try {
    categories.value = await getCategoryTree()
  } catch {
    categories.value = []
  }
  try {
    const data = await listEnterprises({ page: 1, page_size: 200 })
    enterprises.value = data.items || []
  } catch {
    enterprises.value = []
  }
}

/* ---------------- 新增 / 编辑 ---------------- */
const dialogVisible = ref(false)
const dialogTitle = ref('发布商品')
const submitting = ref(false)
const formRef = ref<FormInstance>()
const editingId = ref<number | null>(null)
const form = reactive<ProductPayload>({
  name: '',
  code: '',
  category_id: undefined as unknown as number,
  enterprise_id: null,
  spec: '',
  grade: 'special',
  origin: '新疆阿勒泰',
  harvest_year: String(new Date().getFullYear()),
  package: '50kg 编织袋',
  unit: 'ton',
  price: '',
  currency: 'CNY',
  min_order_qty: '',
  stock_warn_qty: '',
  supply_quantity: '',
  supply_period: '',
  pricing_mode: 'listed',
  supply_status: 'active',
  allow_inquiry: true,
  allow_bulk_purchase: true,
  main_image: '',
  test_report_url: '',
  trace_enabled: true,
  description: ''
})

const rules: FormRules = {
  name: [{ required: true, message: '请输入商品名称', trigger: 'blur' }],
  category_id: [{ required: true, message: '请选择商品分类', trigger: 'change' }],
  grade: [{ required: true, message: '请选择等级', trigger: 'change' }],
  price: []
}

function resetForm(): void {
  Object.assign(form, {
    name: '',
    code: '',
    category_id: undefined,
    enterprise_id: null,
    spec: '',
    grade: 'special',
    origin: '新疆阿勒泰',
    harvest_year: String(new Date().getFullYear()),
    package: '50kg 编织袋',
    unit: 'ton',
    price: '',
    currency: 'CNY',
    min_order_qty: '',
    stock_warn_qty: '',
    supply_quantity: '',
    supply_period: '',
    pricing_mode: 'listed',
    supply_status: 'active',
    allow_inquiry: true,
    allow_bulk_purchase: true,
    main_image: '',
    test_report_url: '',
    trace_enabled: true,
    description: ''
  })
}

function openCreate(): void {
  editingId.value = null
  dialogTitle.value = '发布商品'
  resetForm()
  dialogVisible.value = true
}

async function openEdit(row: Product): Promise<void> {
  editingId.value = row.id
  dialogTitle.value = `编辑商品：${row.name}`
  let detail = row
  try {
    detail = await getProduct(row.id)
  } catch {
    /* 详情失败时退回列表行数据 */
  }
  Object.assign(form, {
    name: detail.name,
    code: detail.code,
    category_id: detail.category_id,
    enterprise_id: detail.enterprise_id,
    spec: detail.spec || '',
    grade: (detail.grade as ProductPayload['grade']) || 'special',
    origin: detail.origin || '',
    harvest_year: detail.harvest_year || '',
    package: detail.package || '',
    unit: detail.unit || 'ton',
    price: detail.price || '',
    currency: detail.currency || 'CNY',
    min_order_qty: detail.min_order_qty || '',
    stock_warn_qty: detail.stock_warn_qty || '',
    supply_quantity: detail.supply_quantity || '',
    supply_period: detail.supply_period || '',
    pricing_mode: detail.pricing_mode || 'listed',
    supply_status: detail.supply_status || 'active',
    allow_inquiry: detail.allow_inquiry ?? true,
    allow_bulk_purchase: detail.allow_bulk_purchase ?? true,
    main_image: detail.main_image || '',
    test_report_url: detail.test_report_url || '',
    trace_enabled: detail.trace_enabled ?? true,
    description: detail.description || ''
  })
  dialogVisible.value = true
}

async function submitForm(): Promise<void> {
  const el = formRef.value
  if (!el) return
  await el.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      if (editingId.value === null) {
        await createProduct({ ...form, price: form.price === '' ? undefined : form.price, supply_quantity: form.supply_quantity === '' ? undefined : form.supply_quantity })
        ElMessage.success('商品创建成功，待审核通过后可上架')
      } else {
        await updateProduct(editingId.value, { ...form, price: form.price === '' ? undefined : form.price, supply_quantity: form.supply_quantity === '' ? undefined : form.supply_quantity })
        ElMessage.success('商品已更新')
      }
      dialogVisible.value = false
      loadList()
    } catch {
      /* 已提示 */
    } finally {
      submitting.value = false
    }
  })
}

/* ---------------- 上架 / 下架 / 审核 ---------------- */
async function handlePublish(row: Product): Promise<void> {
  if (row.audit_status !== 'approved') {
    ElMessage.warning('该商品尚未审核通过，不能上架')
    return
  }
  try {
    await publishProduct(row.id)
    ElMessage.success('商品已上架')
    loadList()
  } catch {
    /* 已提示 */
  }
}

async function handleOffline(row: Product): Promise<void> {
  try {
    await ElMessageBox.confirm(`确认下架商品「${row.name}」？`, '提示', {
      type: 'warning',
      confirmButtonText: '下架',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }
  try {
    await offlineProduct(row.id)
    ElMessage.success('商品已下架')
    loadList()
  } catch {
    /* 已提示 */
  }
}

const auditVisible = ref(false)
const auditSubmitting = ref(false)
const auditForm = reactive<{ id: number | null; name: string; approved: boolean; remark: string }>({
  id: null,
  name: '',
  approved: true,
  remark: ''
})

function openAudit(row: Product, approved: boolean): void {
  auditForm.id = row.id
  auditForm.name = row.name
  auditForm.approved = approved
  auditForm.remark = ''
  auditVisible.value = true
}

async function submitAudit(): Promise<void> {
  if (auditForm.id === null) return
  if (!auditForm.approved && !auditForm.remark.trim()) {
    ElMessage.warning('驳回时必须填写审核意见')
    return
  }
  auditSubmitting.value = true
  try {
    await auditProduct(auditForm.id, { approved: auditForm.approved, remark: auditForm.remark })
    ElMessage.success(auditForm.approved ? '审核通过' : '已驳回')
    auditVisible.value = false
    loadList()
  } catch {
    /* 已提示 */
  } finally {
    auditSubmitting.value = false
  }
}

async function handleDelete(row: Product): Promise<void> {
  try {
    await ElMessageBox.confirm(`确认删除商品「${row.name}」？`, '危险操作', {
      type: 'error',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }
  try {
    await deleteProduct(row.id)
    ElMessage.success('删除成功')
    loadList()
  } catch {
    /* 已提示 */
  }
}

/* ---------------- 库存查看 ---------------- */
const stockVisible = ref(false)
const stockLoading = ref(false)
const stockRows = ref<ProductInventoryItem[]>([])
const stockProduct = ref<Product | null>(null)

async function openStock(row: Product): Promise<void> {
  stockProduct.value = row
  stockVisible.value = true
  stockLoading.value = true
  try {
    stockRows.value = await getProductInventory(row.id)
  } catch {
    stockRows.value = []
  } finally {
    stockLoading.value = false
  }
}

onMounted(async () => {
  await Promise.all([loadList(), loadOptions()])
})
</script>

<template>
  <div class="page-container">
    <PageTable
      :data="list"
      :total="total"
      :loading="loading"
      v-model:page="query.page"
      v-model:page-size="query.page_size"
      @change="loadList"
    >
      <template #search>
        <div class="page-card">
          <el-form class="search-form" :inline="true" @submit.prevent>
            <el-form-item label="关键词">
              <el-input
                v-model="query.keyword"
                placeholder="商品名称 / 编码"
                clearable
                style="width: 200px"
                @keyup.enter="handleSearch"
              />
            </el-form-item>
            <el-form-item label="分类">
              <el-select v-model="query.category_id" placeholder="全部分类" clearable style="width: 170px">
                <el-option v-for="item in categoryOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
            <el-form-item label="商户">
              <el-select
                v-model="query.enterprise_id"
                placeholder="全部商户"
                clearable
                filterable
                style="width: 200px"
              >
                <el-option v-for="item in enterprises" :key="item.id" :label="item.name" :value="item.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="状态">
              <DictSelect v-model="query.status" group="productStatus" with-all placeholder="全部状态" />
            </el-form-item>
            <el-form-item label="等级">
              <DictSelect v-model="query.grade" group="productGrade" with-all placeholder="全部等级" />
            </el-form-item>
            <el-form-item label="产地">
              <el-input v-model="query.origin" placeholder="如 新疆阿勒泰" clearable style="width: 160px" />
            </el-form-item>
            <el-form-item label="年份">
              <el-input v-model="query.harvest_year" placeholder="如 2025" clearable style="width: 120px" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleSearch">查询</el-button>
              <el-button @click="handleReset">重置</el-button>
            </el-form-item>
          </el-form>
        </div>
      </template>

      <template #toolbar>
        <el-button v-permission="'product:write'" type="primary" @click="openCreate">
          <el-icon><Plus /></el-icon>
          <span>发布商品</span>
        </el-button>
      </template>

      <el-table-column label="商品图片" width="102" align="center">
        <template #default="{ row }">
          <el-image v-if="row.main_image" :src="row.main_image" fit="cover" class="product-thumb" :preview-src-list="[row.main_image]" preview-teleported />
          <span v-else class="text-sub">待上传</span>
        </template>
      </el-table-column>
      <el-table-column prop="code" label="商品编码" width="140" />
      <el-table-column prop="name" label="商品 / 报价 / 供应企业" min-width="270">
        <template #default="{ row }">
          <el-link type="primary" :underline="false" @click="router.push(`/product/detail/${row.id}`)">
            {{ row.name }}
          </el-link>
          <div class="product-main__spec">{{ row.spec || '规格待完善' }}</div>
          <div class="product-main__price">{{ formatMoney(row.price) }} 元/{{ row.unit === 'ton' ? '吨' : row.unit }}</div>
          <div class="product-main__enterprise">{{ row.enterprise_name || '供应企业待完善' }}</div>
        </template>
      </el-table-column>
      <el-table-column prop="category_name" label="分类" width="110" />
      <el-table-column prop="enterprise_name" label="供应企业" min-width="200" show-overflow-tooltip />
      <el-table-column label="等级" width="80">
        <template #default="{ row }">
          <StatusTag group="productGrade" :value="row.grade" />
        </template>
      </el-table-column>
      <el-table-column prop="spec" label="规格" min-width="130" show-overflow-tooltip />
      <el-table-column prop="origin" label="产地" width="120" />
      <el-table-column label="参考价" width="120" align="right">
        <template #default="{ row }">{{ formatMoney(row.price) }} 元/{{ row.unit === 'ton' ? '吨' : row.unit }}</template>
      </el-table-column>
      <el-table-column label="总库存" width="110" align="right">
        <template #default="{ row }">{{ formatQuantity(row.total_quantity) }}</template>
      </el-table-column>
      <el-table-column label="可用库存" width="110" align="right">
        <template #default="{ row }">
          <span class="text-amount">{{ formatQuantity(row.available_quantity) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <StatusTag group="productStatus" :value="row.status" />
        </template>
      </el-table-column>
      <el-table-column label="审核" width="90">
        <template #default="{ row }">
          <StatusTag group="auditStatus" :value="row.audit_status" />
        </template>
      </el-table-column>
      <el-table-column label="更新时间" min-width="160">
        <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="365" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="router.push(`/product/detail/${row.id}`)">详情</el-button>
          <el-button link type="primary" @click="openStock(row as Product)">库存</el-button>
          <el-button v-permission="'product:write'" link type="primary" @click="openEdit(row as Product)">编辑</el-button>
          <el-button v-permission="'product:write'" link type="primary" @click="openImage(row as Product)">更换主图</el-button>
          <el-button
            v-permission="'product:write'"
            link
            type="success"
            :disabled="row.status === 'published'"
            @click="handlePublish(row as Product)"
          >
            上架
          </el-button>
          <el-button
            v-permission="'product:write'"
            link
            type="warning"
            :disabled="row.status !== 'published'"
            @click="handleOffline(row as Product)"
          >
            下架
          </el-button>
          <el-button
            v-permission="'product:audit'"
            link
            type="primary"
            :disabled="row.audit_status === 'approved'"
            @click="openAudit(row as Product, true)"
          >
            审核通过
          </el-button>
          <el-button
            v-permission="'product:audit'"
            link
            type="warning"
            :disabled="row.audit_status === 'rejected'"
            @click="openAudit(row as Product, false)"
          >
            驳回
          </el-button>
          <el-button v-permission="'product:write'" link type="danger" @click="handleDelete(row as Product)">删除</el-button>
        </template>
      </el-table-column>
    </PageTable>

    <el-dialog v-model="imageVisible" :title="`更换商品主图：${imageProduct?.name || ''}`" width="480px" append-to-body>
      <p class="image-hint">上传后点击保存；商品名称、价格、库存及交易状态不会改变。</p>
      <el-image v-if="imageUrl" :src="imageUrl" fit="cover" class="image-preview" />
      <FileUpload v-model="imageUrl" biz-type="product_image" accept=".jpg,.jpeg,.png,.webp" :max-size="10" @uploaded="() => imageUploaded = true" />
      <template #footer>
        <el-button @click="imageVisible = false">取消</el-button>
        <el-button type="primary" :loading="imageSaving" :disabled="!imageUploaded || !imageUrl" @click="saveImage">保存主图</el-button>
      </template>
    </el-dialog>

    <!-- 新增 / 编辑 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="760px" append-to-body>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="110px">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="商品名称" prop="name">
              <el-input v-model="form.name" placeholder="如 新疆特级葵花籽" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="商品编码">
              <el-input v-model="form.code" placeholder="留空由后端生成，如 GZ-SUN-0001" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="商品分类" prop="category_id">
              <el-select v-model="form.category_id" placeholder="请选择分类" filterable style="width: 100%">
                <el-option v-for="item in categoryOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="归属商户">
              <el-select
                v-model="form.enterprise_id"
                placeholder="默认当前用户企业"
                clearable
                filterable
                style="width: 100%"
              >
                <el-option v-for="item in enterprises" :key="item.id" :label="item.name" :value="item.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="等级" prop="grade">
              <DictSelect v-model="form.grade" group="productGrade" :clearable="false" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="规格">
              <el-input v-model="form.spec" placeholder="如 千粒重≥180g" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="产地">
              <el-input v-model="form.origin" placeholder="如 新疆阿勒泰" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="收获年份">
              <el-input v-model="form.harvest_year" placeholder="如 2025" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="包装">
              <el-input v-model="form.package" placeholder="如 50kg 编织袋" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="计量单位">
              <DictSelect v-model="form.unit" group="productUnit" :clearable="false" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="参考价">
              <el-input v-model="form.price" placeholder="元/单位，如 6800.00">
                <template #append>元</template>
              </el-input>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="起订量">
              <el-input v-model="form.min_order_qty" placeholder="如 10.000" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="库存预警值">
              <el-input v-model="form.stock_warn_qty" placeholder="如 20.000" />
            </el-form-item>
          </el-col>
          <el-col :span="12"><el-form-item label="供应数量"><el-input v-model="form.supply_quantity" placeholder="不填则展示可用库存" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="供应周期"><el-input v-model="form.supply_period" placeholder="例如：现货 / 每月供货" maxlength="64" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="价格方式"><el-select v-model="form.pricing_mode" style="width:100%"><el-option label="挂牌参考价" value="listed" /><el-option label="价格协商" value="negotiable" /><el-option label="询价面议" value="inquiry" /></el-select></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="供应状态"><el-select v-model="form.supply_status" style="width:100%"><el-option label="供应中" value="active" /><el-option label="已暂停" value="paused" /><el-option label="已完成" value="completed" /></el-select></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="支持询价"><el-switch v-model="form.allow_inquiry" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="批量采购"><el-switch v-model="form.allow_bulk_purchase" /></el-form-item></el-col>
          <el-col :span="12">
            <el-form-item label="启用溯源">
              <el-switch v-model="form.trace_enabled" active-text="启用" inactive-text="关闭" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="主图">
              <FileUpload v-model="form.main_image" biz-type="product_image" accept=".jpg,.jpeg,.png,.webp" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="检测报告">
              <FileUpload v-model="form.test_report_url" biz-type="product_report" accept=".pdf,.jpg,.png" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="商品详情">
              <el-input v-model="form.description" type="textarea" :rows="3" placeholder="品质、加工工艺、交付说明等" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>

    <!-- 库存查看 -->
    <el-dialog v-model="stockVisible" :title="`库存分布：${stockProduct?.name || ''}`" width="720px" append-to-body>
      <el-table v-loading="stockLoading" :data="stockRows" border stripe>
        <el-table-column prop="warehouse_name" label="仓库" min-width="150" />
        <el-table-column prop="location_name" label="库位" min-width="120" />
        <el-table-column prop="batch_no" label="批次号" min-width="130" />
        <el-table-column label="账面数量" width="110" align="right">
          <template #default="{ row }">{{ formatQuantity(row.quantity) }}</template>
        </el-table-column>
        <el-table-column label="预占数量" width="110" align="right">
          <template #default="{ row }">{{ formatQuantity(row.locked_quantity) }}</template>
        </el-table-column>
        <el-table-column label="可用数量" width="110" align="right">
          <template #default="{ row }">
            <span class="text-amount">{{ formatQuantity(row.available_quantity) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="质量" width="90">
          <template #default="{ row }">
            <StatusTag group="qualityStatus" :value="row.quality_status" />
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="stockVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 审核 -->
    <el-dialog
      v-model="auditVisible"
      :title="auditForm.approved ? '商品审核通过' : '商品审核驳回'"
      width="480px"
      append-to-body
    >
      <el-form label-width="90px">
        <el-form-item label="商品名称">
          <span>{{ auditForm.name }}</span>
        </el-form-item>
        <el-form-item label="审核意见">
          <el-input
            v-model="auditForm.remark"
            type="textarea"
            :rows="3"
            :placeholder="auditForm.approved ? '可选填' : '驳回必填，请说明原因'"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="auditVisible = false">取消</el-button>
        <el-button
          :type="auditForm.approved ? 'success' : 'warning'"
          :loading="auditSubmitting"
          @click="submitAudit"
        >
          确认{{ auditForm.approved ? '通过' : '驳回' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.image-preview { width: 100%; height: 190px; border-radius: 8px; margin: 8px 0 16px; }
.image-hint { color: var(--gz-text-sub); font-size: 13px; line-height: 1.6; }
.product-thumb { width: 68px; height: 52px; border-radius: 6px; display: block; margin: 2px auto; }
.product-main__spec, .product-main__enterprise { color: #7c8b80; font-size: 12px; max-width: 255px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.product-main__price { color: #df6819; font-weight: 700; font-size: 13px; }
</style>

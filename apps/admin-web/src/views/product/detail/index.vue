<script setup lang="ts">
/**
 * 商品详情：基础信息 + 库存分布（GET /products/{id}/inventory）+ 检测报告预览 + 上下架/审核操作。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import StatusTag from '@/components/StatusTag.vue'
import { auditProduct, getProduct, getProductInventory, offlineProduct, publishProduct } from '@/api/product'
import type { Product, ProductInventoryItem } from '@/api/types'
import { formatDateTime, formatMoney, formatQuantity, unitLabel } from '@/utils/format'
import { downloadByUrl } from '@/utils/download'

const route = useRoute()
const router = useRouter()

const productId = computed(() => Number(route.params.id))

const loading = ref(false)
const product = ref<Product | null>(null)
const inventory = ref<ProductInventoryItem[]>([])
const inventoryLoading = ref(false)

const totalQuantity = computed(() =>
  inventory.value.reduce((sum, item) => sum + Number(item.quantity || 0), 0)
)
const totalLocked = computed(() =>
  inventory.value.reduce((sum, item) => sum + Number(item.locked_quantity || 0), 0)
)
const totalAvailable = computed(() =>
  inventory.value.reduce(
    (sum, item) => sum + Number(item.available_quantity ?? Number(item.quantity || 0) - Number(item.locked_quantity || 0)),
    0
  )
)

const reportIsPdf = computed(() => (product.value?.test_report_url || '').toLowerCase().includes('.pdf'))
const reportIsImage = computed(() => /\.(jpg|jpeg|png|webp|gif)$/i.test(product.value?.test_report_url || ''))

async function loadDetail(): Promise<void> {
  if (!productId.value) return
  loading.value = true
  try {
    product.value = await getProduct(productId.value)
  } catch {
    product.value = null
  } finally {
    loading.value = false
  }
}

async function loadInventory(): Promise<void> {
  if (!productId.value) return
  inventoryLoading.value = true
  try {
    inventory.value = await getProductInventory(productId.value)
  } catch {
    inventory.value = []
  } finally {
    inventoryLoading.value = false
  }
}

/* ---------------- 上下架 / 审核 ---------------- */
const auditVisible = ref(false)
const auditSubmitting = ref(false)
const auditForm = reactive({ approved: true, remark: '' })

function openAudit(approved: boolean): void {
  auditForm.approved = approved
  auditForm.remark = ''
  auditVisible.value = true
}

async function submitAudit(): Promise<void> {
  if (!product.value) return
  if (!auditForm.approved && !auditForm.remark.trim()) {
    ElMessage.warning('驳回时必须填写审核意见')
    return
  }
  auditSubmitting.value = true
  try {
    await auditProduct(product.value.id, { approved: auditForm.approved, remark: auditForm.remark })
    ElMessage.success(auditForm.approved ? '审核通过' : '已驳回')
    auditVisible.value = false
    loadDetail()
  } catch {
    /* 已提示 */
  } finally {
    auditSubmitting.value = false
  }
}

async function handlePublish(): Promise<void> {
  if (!product.value) return
  if (product.value.audit_status !== 'approved') {
    ElMessage.warning('该商品尚未审核通过，不能上架')
    return
  }
  try {
    await publishProduct(product.value.id)
    ElMessage.success('商品已上架')
    loadDetail()
  } catch {
    /* 已提示 */
  }
}

async function handleOffline(): Promise<void> {
  if (!product.value) return
  try {
    await offlineProduct(product.value.id)
    ElMessage.success('商品已下架')
    loadDetail()
  } catch {
    /* 已提示 */
  }
}

onMounted(async () => {
  await loadDetail()
  await loadInventory()
})
</script>

<template>
  <div class="page-container" v-loading="loading">
    <div class="page-card">
      <div class="page-title">
        <span>
          商品详情
          <span class="page-title__sub">{{ product?.code || '' }}</span>
        </span>
        <div class="flex-center" style="gap: 8px">
          <el-button size="small" @click="router.back()">返回</el-button>
          <el-button size="small" @click="loadDetail(); loadInventory()">
            <el-icon><Refresh /></el-icon>
            <span>刷新</span>
          </el-button>
          <el-button
            v-permission="'product:write'"
            size="small"
            type="success"
            :disabled="!product || product.status === 'published'"
            @click="handlePublish"
          >
            上架
          </el-button>
          <el-button
            v-permission="'product:write'"
            size="small"
            type="warning"
            :disabled="!product || product.status !== 'published'"
            @click="handleOffline"
          >
            下架
          </el-button>
          <el-button
            v-permission="'product:audit'"
            size="small"
            type="primary"
            :disabled="!product || product.audit_status === 'approved'"
            @click="openAudit(true)"
          >
            审核通过
          </el-button>
          <el-button
            v-permission="'product:audit'"
            size="small"
            type="danger"
            :disabled="!product || product.audit_status === 'rejected'"
            @click="openAudit(false)"
          >
            驳回
          </el-button>
        </div>
      </div>

      <template v-if="product">
        <el-descriptions :column="3" border>
          <el-descriptions-item label="商品名称">{{ product.name }}</el-descriptions-item>
          <el-descriptions-item label="商品编码">{{ product.code }}</el-descriptions-item>
          <el-descriptions-item label="分类">{{ product.category_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="归属企业">{{ product.enterprise_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="等级">
            <StatusTag group="productGrade" :value="product.grade" />
          </el-descriptions-item>
          <el-descriptions-item label="规格">{{ product.spec || '-' }}</el-descriptions-item>
          <el-descriptions-item label="产地">{{ product.origin || '-' }}</el-descriptions-item>
          <el-descriptions-item label="收获年份">{{ product.harvest_year || '-' }}</el-descriptions-item>
          <el-descriptions-item label="包装">{{ product.package || '-' }}</el-descriptions-item>
          <el-descriptions-item label="参考价">
            {{ formatMoney(product.price) }} 元/{{ unitLabel(product.unit) }}
          </el-descriptions-item>
          <el-descriptions-item label="起订量">
            {{ formatQuantity(product.min_order_qty) }} {{ unitLabel(product.unit) }}
          </el-descriptions-item>
          <el-descriptions-item label="库存预警值">
            {{ formatQuantity(product.stock_warn_qty) }} {{ unitLabel(product.unit) }}
          </el-descriptions-item>
          <el-descriptions-item label="质量状态">
            <StatusTag group="qualityStatus" :value="product.quality_status" />
          </el-descriptions-item>
          <el-descriptions-item label="商品状态">
            <StatusTag group="productStatus" :value="product.status" />
          </el-descriptions-item>
          <el-descriptions-item label="审核状态">
            <StatusTag group="auditStatus" :value="product.audit_status" />
          </el-descriptions-item>
          <el-descriptions-item label="启用溯源">
            {{ product.trace_enabled ? '是' : '否' }}
          </el-descriptions-item>
          <el-descriptions-item label="总库存">
            {{ formatQuantity(product.total_quantity) }} {{ unitLabel(product.unit) }}
          </el-descriptions-item>
          <el-descriptions-item label="可用库存">
            <span class="text-amount">
              {{ formatQuantity(product.available_quantity) }} {{ unitLabel(product.unit) }}
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="审核意见" :span="3">{{ product.audit_remark || '-' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatDateTime(product.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="更新时间">{{ formatDateTime(product.updated_at) }}</el-descriptions-item>
          <el-descriptions-item label="商品详情" :span="3">{{ product.description || '-' }}</el-descriptions-item>
        </el-descriptions>

        <div class="detail-block">
          <div class="detail-block__title">商品图片</div>
          <el-image
            v-if="product.main_image"
            :src="product.main_image"
            :preview-src-list="[product.main_image]"
            fit="cover"
            class="detail-image"
            preview-teleported
          />
          <span v-else class="text-sub">暂无图片</span>
        </div>
      </template>

      <el-empty v-else-if="!loading" description="商品不存在或已被删除" />
    </div>

    <div class="page-card">
      <div class="page-title">
        <span>
          库存分布
          <span class="page-title__sub">
            账面 {{ formatQuantity(totalQuantity) }} · 预占 {{ formatQuantity(totalLocked) }} · 可用
            {{ formatQuantity(totalAvailable) }}
          </span>
        </span>
      </div>

      <el-table v-loading="inventoryLoading" :data="inventory" border stripe>
        <el-table-column prop="warehouse_name" label="仓库" min-width="150" />
        <el-table-column prop="location_name" label="库位" min-width="120" />
        <el-table-column prop="batch_no" label="批次号" min-width="140" />
        <el-table-column label="账面数量" width="120" align="right">
          <template #default="{ row }">{{ formatQuantity(row.quantity) }}</template>
        </el-table-column>
        <el-table-column label="预占数量" width="120" align="right">
          <template #default="{ row }">{{ formatQuantity(row.locked_quantity) }}</template>
        </el-table-column>
        <el-table-column label="可用数量" width="120" align="right">
          <template #default="{ row }">
            <span class="text-amount">{{ formatQuantity(row.available_quantity) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="成本单价" width="120" align="right">
          <template #default="{ row }">{{ formatMoney(row.unit_cost) }}</template>
        </el-table-column>
        <el-table-column label="生产日期" width="120">
          <template #default="{ row }">{{ row.production_date || '-' }}</template>
        </el-table-column>
        <el-table-column label="质量状态" width="100">
          <template #default="{ row }">
            <StatusTag group="qualityStatus" :value="row.quality_status" />
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="page-card">
      <div class="page-title">
        <span>检测报告</span>
      </div>
      <template v-if="product?.test_report_url">
        <el-image
          v-if="reportIsImage"
          :src="product.test_report_url"
          :preview-src-list="[product.test_report_url]"
          fit="contain"
          class="report-image"
          preview-teleported
        />
        <div v-else>
          <el-link type="primary" :href="product.test_report_url" target="_blank">
            <el-icon><Document /></el-icon>
            <span>打开检测报告{{ reportIsPdf ? '（PDF）' : '' }}</span>
          </el-link>
          <el-button link type="primary" @click="downloadByUrl(product.test_report_url, `${product.code}-检测报告`)">
            下载报告
          </el-button>
        </div>
      </template>
      <el-empty v-else description="该商品未上传检测报告" :image-size="80" />
    </div>

    <el-dialog
      v-model="auditVisible"
      :title="auditForm.approved ? '商品审核通过' : '商品审核驳回'"
      width="480px"
      append-to-body
    >
      <el-form label-width="90px">
        <el-form-item label="商品名称">
          <span>{{ product?.name }}</span>
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
.detail-block {
  margin-top: 16px;
}

.detail-block__title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 8px;
}

.detail-image {
  width: 180px;
  height: 180px;
  border-radius: 6px;
  border: 1px solid var(--gz-border);
}

.report-image {
  max-width: 420px;
  max-height: 560px;
  border: 1px solid var(--gz-border);
  border-radius: 6px;
}
</style>

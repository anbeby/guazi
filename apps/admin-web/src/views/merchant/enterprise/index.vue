<script setup lang="ts">
/**
 * 商户档案：列表查询 + 详情抽屉（含经营统计与资质附件）+ 审核通过/驳回 + 新增/编辑。
 * 接口：/enterprises、/enterprises/{id}、/enterprises/{id}/audit、/enterprises/{id}/stats、/files/upload
 */
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'

import PageTable from '@/components/PageTable.vue'
import StatusTag from '@/components/StatusTag.vue'
import DictSelect from '@/components/DictSelect.vue'
import FileUpload from '@/components/FileUpload.vue'
import { useUserStore } from '@/stores/user'
import {
  auditEnterprise,
  createEnterprise,
  deleteEnterprise,
  getEnterprise,
  getEnterpriseStats,
  listEnterprises,
  setEnterpriseImage,
  updateEnterprise
} from '@/api/enterprise'
import { listParks } from '@/api/park'
import type {
  Enterprise,
  EnterprisePayload,
  EnterpriseQuery,
  EnterpriseStats,
  Park
} from '@/api/types'
import { formatAmount, formatDateTime, formatQuantity } from '@/utils/format'

const userStore = useUserStore()

/* ---------------- 列表 ---------------- */
const loading = ref(false)
const list = ref<Enterprise[]>([])
const total = ref(0)
const parks = ref<Park[]>([])
const query = reactive<EnterpriseQuery>({
  page: 1,
  page_size: 20,
  keyword: '',
  enterprise_type: '',
  audit_status: '',
  status: ''
})

async function loadList(): Promise<void> {
  loading.value = true
  try {
    const data = await listEnterprises(query)
    list.value = data.items || []
    total.value = data.total || 0
  } catch {
    list.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

async function loadParks(): Promise<void> {
  try {
    const data = await listParks({ page: 1, page_size: 200 })
    parks.value = data.items || []
  } catch {
    parks.value = []
  }
}

function handleSearch(): void {
  query.page = 1
  loadList()
}

function handleReset(): void {
  query.keyword = ''
  query.enterprise_type = ''
  query.audit_status = ''
  query.status = ''
  query.park_id = undefined
  query.page = 1
  loadList()
}

/* ---------------- 详情抽屉 ---------------- */
const drawerVisible = ref(false)
const detailLoading = ref(false)
const detail = ref<Enterprise | null>(null)
const stats = ref<EnterpriseStats | null>(null)

/* 企业展示图独立更换，避免误改企业主数据。 */
const imageVisible = ref(false)
const imageSaving = ref(false)
const imageEnterprise = ref<Enterprise | null>(null)
const imageUrl = ref('')
const imageFileKey = ref('')
const imageNewUrl = ref('')

function openImage(row: Enterprise): void {
  imageEnterprise.value = row
  imageUrl.value = row.image_url || ''
  imageFileKey.value = ''
  imageNewUrl.value = ''
  imageVisible.value = true
}

async function saveImage(): Promise<void> {
  if (!imageEnterprise.value || !imageFileKey.value || imageUrl.value !== imageNewUrl.value) {
    ElMessage.warning('请先上传一张新图片')
    return
  }
  imageSaving.value = true
  try {
    await setEnterpriseImage(imageEnterprise.value.id, imageFileKey.value)
    ElMessage.success('企业展示图已更新，门户页面刷新后可见')
    imageVisible.value = false
    await loadList()
    if (detail.value?.id === imageEnterprise.value.id) {
      detail.value = await getEnterprise(imageEnterprise.value.id)
    }
  } catch {
    /* 错误由请求拦截器提示 */
  } finally {
    imageSaving.value = false
  }
}

async function openDetail(row: Enterprise): Promise<void> {
  drawerVisible.value = true
  detailLoading.value = true
  detail.value = row
  stats.value = null
  try {
    const [info, stat] = await Promise.all([
      getEnterprise(row.id),
      getEnterpriseStats(row.id).catch(() => null)
    ])
    detail.value = info
    stats.value = stat
  } catch {
    /* 已提示 */
  } finally {
    detailLoading.value = false
  }
}

/* ---------------- 新增 / 编辑 ---------------- */
const dialogVisible = ref(false)
const dialogTitle = ref('新增商户')
const submitting = ref(false)
const formRef = ref<FormInstance>()
const editingId = ref<number | null>(null)
const form = reactive<EnterprisePayload & { license_url: string }>({
  code: '',
  name: '',
  unified_social_credit_code: '',
  enterprise_type: 'merchant',
  legal_person: '',
  registered_capital: '',
  business_scope: '',
  profile: '',
  qualifications: [],
  contact_name: '',
  contact_phone: '',
  email: '',
  region: '',
  address: '',
  park_id: null,
  stall_id: null,
  settle_bank: '',
  settle_account_name: '',
  settle_account_no: '',
  remark: '',
  license_url: ''
})
const qualificationsText = ref('')

const rules: FormRules = {
  name: [{ required: true, message: '请输入企业名称', trigger: 'blur' }],
  enterprise_type: [{ required: true, message: '请选择企业类型', trigger: 'change' }],
  unified_social_credit_code: [
    { pattern: /^[0-9A-Z]{18}$/, message: '统一社会信用代码为 18 位大写字母或数字', trigger: 'blur' }
  ],
  contact_phone: [{ pattern: /^1[3-9]\d{9}$/, message: '手机号格式不正确', trigger: 'blur' }]
}

function resetForm(): void {
  Object.assign(form, {
    code: '',
    name: '',
    unified_social_credit_code: '',
    enterprise_type: 'merchant',
    legal_person: '',
    registered_capital: '',
    business_scope: '',
    profile: '',
    qualifications: [],
    contact_name: '',
    contact_phone: '',
    email: '',
    region: '',
    address: '',
    park_id: null,
    stall_id: null,
    settle_bank: '',
    settle_account_name: '',
    settle_account_no: '',
    remark: '',
    license_url: ''
  })
  qualificationsText.value = ''
}

function openCreate(): void {
  editingId.value = null
  dialogTitle.value = '新增商户'
  resetForm()
  dialogVisible.value = true
}

function openEdit(row: Enterprise): void {
  editingId.value = row.id
  dialogTitle.value = `编辑：${row.name}`
  Object.assign(form, {
    code: row.code,
    name: row.name,
    unified_social_credit_code: row.unified_social_credit_code || '',
    enterprise_type: row.enterprise_type,
    legal_person: row.legal_person || '',
    registered_capital: row.registered_capital || '',
    business_scope: row.business_scope || '',
    profile: row.profile || '',
    qualifications: row.qualifications || [],
    contact_name: row.contact_name || '',
    contact_phone: row.contact_phone || '',
    email: row.email || '',
    region: row.region || '',
    address: row.address || '',
    park_id: row.park_id ?? null,
    stall_id: row.stall_id ?? null,
    settle_bank: row.settle_bank || '',
    settle_account_name: row.settle_account_name || '',
    settle_account_no: row.settle_account_no || '',
    remark: row.remark || '',
    license_url: ''
  })
  qualificationsText.value = (row.qualifications || []).join('\n')
  dialogVisible.value = true
}

async function submitForm(): Promise<void> {
  const el = formRef.value
  if (!el) return
  await el.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    const { license_url, ...payload } = form
    payload.qualifications = qualificationsText.value.split(/\r?\n/).map(item => item.trim()).filter(Boolean)
    void license_url
    try {
      if (editingId.value === null) {
        await createEnterprise(payload)
        ElMessage.success('商户创建成功，等待审核')
      } else {
        await updateEnterprise(editingId.value, payload)
        ElMessage.success('商户信息已更新')
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

/* ---------------- 审核 ---------------- */
const auditVisible = ref(false)
const auditSubmitting = ref(false)
const auditForm = reactive<{ id: number | null; name: string; approved: boolean; remark: string }>({
  id: null,
  name: '',
  approved: true,
  remark: ''
})

function openAudit(row: Enterprise, approved: boolean): void {
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
    await auditEnterprise(auditForm.id, { approved: auditForm.approved, remark: auditForm.remark })
    ElMessage.success(auditForm.approved ? '审核通过' : '已驳回')
    auditVisible.value = false
    loadList()
    if (drawerVisible.value && detail.value?.id === auditForm.id) {
      detail.value = await getEnterprise(auditForm.id).catch(() => detail.value)
    }
  } catch {
    /* 已提示 */
  } finally {
    auditSubmitting.value = false
  }
}

async function handleDelete(row: Enterprise): Promise<void> {
  try {
    await ElMessageBox.confirm(`确认删除商户「${row.name}」？`, '危险操作', {
      type: 'error',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }
  try {
    await deleteEnterprise(row.id)
    ElMessage.success('删除成功')
    loadList()
  } catch {
    /* 已提示 */
  }
}

onMounted(async () => {
  await Promise.all([loadList(), loadParks()])
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
                placeholder="企业名称 / 编码 / 信用代码"
                clearable
                style="width: 220px"
                @keyup.enter="handleSearch"
              />
            </el-form-item>
            <el-form-item label="企业类型">
              <DictSelect v-model="query.enterprise_type" group="enterpriseType" with-all placeholder="全部类型" />
            </el-form-item>
            <el-form-item label="审核状态">
              <DictSelect v-model="query.audit_status" group="auditStatus" with-all placeholder="全部状态" />
            </el-form-item>
            <el-form-item label="经营状态">
              <DictSelect v-model="query.status" group="commonStatus" with-all placeholder="全部" />
            </el-form-item>
            <el-form-item label="所属园区">
              <el-select v-model="query.park_id" placeholder="全部园区" clearable style="width: 180px">
                <el-option v-for="item in parks" :key="item.id" :label="item.name" :value="item.id" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleSearch">查询</el-button>
              <el-button @click="handleReset">重置</el-button>
            </el-form-item>
          </el-form>
        </div>
      </template>

      <template #toolbar>
        <el-button v-permission="'merchant:write'" type="primary" @click="openCreate">
          <el-icon><Plus /></el-icon>
          <span>新增商户</span>
        </el-button>
      </template>

      <el-table-column label="展示图" width="100" align="center">
        <template #default="{ row }">
          <el-image v-if="row.image_url" :src="row.image_url" fit="cover" class="enterprise-thumb" :preview-src-list="[row.image_url]" preview-teleported />
          <span v-else class="text-sub">示意图</span>
        </template>
      </el-table-column>
      <el-table-column prop="code" label="企业编码" width="130" />
      <el-table-column prop="name" label="企业名称" min-width="200" show-overflow-tooltip>
        <template #default="{ row }">
          <el-link type="primary" :underline="false" @click="openDetail(row as Enterprise)">{{ row.name }}</el-link>
        </template>
      </el-table-column>
      <el-table-column label="类型" width="90">
        <template #default="{ row }">
          <StatusTag group="enterpriseType" :value="row.enterprise_type" />
        </template>
      </el-table-column>
      <el-table-column prop="legal_person" label="法定代表人" width="110" />
      <el-table-column prop="contact_name" label="联系人" width="100" />
      <el-table-column prop="contact_phone" label="联系电话" width="130" />
      <el-table-column label="审核状态" width="100">
        <template #default="{ row }">
          <StatusTag group="auditStatus" :value="row.audit_status" />
        </template>
      </el-table-column>
      <el-table-column label="经营状态" width="90">
        <template #default="{ row }">
          <StatusTag group="commonStatus" :value="row.status" />
        </template>
      </el-table-column>
      <el-table-column label="入驻园区" min-width="150">
        <template #default="{ row }">{{ row.park_name || '-' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="330" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row as Enterprise)">详情</el-button>
          <el-button v-permission="'merchant:write'" link type="primary" @click="openEdit(row as Enterprise)">编辑</el-button>
          <el-button v-if="userStore.isSuperuser" link type="primary" @click="openImage(row as Enterprise)">更换展示图</el-button>
          <el-button
            v-permission="'merchant:audit'"
            link
            type="success"
            :disabled="row.audit_status === 'approved'"
            @click="openAudit(row as Enterprise, true)"
          >
            通过
          </el-button>
          <el-button
            v-permission="'merchant:audit'"
            link
            type="warning"
            :disabled="row.audit_status === 'rejected'"
            @click="openAudit(row as Enterprise, false)"
          >
            驳回
          </el-button>
          <el-button v-permission="'merchant:write'" link type="danger" @click="handleDelete(row as Enterprise)">删除</el-button>
        </template>
      </el-table-column>
    </PageTable>

    <el-dialog v-model="imageVisible" :title="`更换企业展示图：${imageEnterprise?.name || ''}`" width="480px" append-to-body>
      <p class="image-hint">建议使用真实企业厂区、加工或仓储照片；保存后同步显示在门户企业卡片和手机端。</p>
      <el-image v-if="imageUrl" :src="imageUrl" fit="cover" class="image-preview" />
      <FileUpload v-model="imageUrl" biz-type="enterprise_image" accept=".jpg,.jpeg,.png,.webp" :max-size="10" @uploaded="(file) => { imageFileKey = file.file_key; imageNewUrl = file.url }" />
      <template #footer>
        <el-button @click="imageVisible = false">取消</el-button>
        <el-button type="primary" :loading="imageSaving" :disabled="!imageFileKey || imageUrl !== imageNewUrl" @click="saveImage">保存展示图</el-button>
      </template>
    </el-dialog>

    <!-- 详情抽屉 -->
    <el-drawer v-model="drawerVisible" title="商户档案详情" size="620px">
      <div v-loading="detailLoading">
        <template v-if="detail">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="企业编码">{{ detail.code }}</el-descriptions-item>
            <el-descriptions-item label="企业类型">
              <StatusTag group="enterpriseType" :value="detail.enterprise_type" />
            </el-descriptions-item>
            <el-descriptions-item label="企业名称" :span="2">{{ detail.name }}</el-descriptions-item>
            <el-descriptions-item label="信用代码" :span="2">
              {{ detail.unified_social_credit_code || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="法定代表人">{{ detail.legal_person || '-' }}</el-descriptions-item>
            <el-descriptions-item label="注册资本">
              {{ detail.registered_capital ? `${detail.registered_capital} 万元` : '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="联系人">{{ detail.contact_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="联系电话">{{ detail.contact_phone || '-' }}</el-descriptions-item>
            <el-descriptions-item label="邮箱" :span="2">{{ detail.email || '-' }}</el-descriptions-item>
            <el-descriptions-item label="行政区划">{{ detail.region || '-' }}</el-descriptions-item>
            <el-descriptions-item label="所属园区">{{ detail.park_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="地址" :span="2">{{ detail.address || '-' }}</el-descriptions-item>
            <el-descriptions-item label="审核状态">
              <StatusTag group="auditStatus" :value="detail.audit_status" />
            </el-descriptions-item>
            <el-descriptions-item label="经营状态">
              <StatusTag group="commonStatus" :value="detail.status" />
            </el-descriptions-item>
            <el-descriptions-item label="审核意见" :span="2">{{ detail.audit_remark || '-' }}</el-descriptions-item>
            <el-descriptions-item label="结算银行">{{ detail.settle_bank || '-' }}</el-descriptions-item>
            <el-descriptions-item label="开户名">{{ detail.settle_account_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="结算账号" :span="2">{{ detail.settle_account_no || '-' }}</el-descriptions-item>
            <el-descriptions-item label="经营范围" :span="2">
              {{ detail.business_scope || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="企业简介" :span="2">{{ detail.profile || '-' }}</el-descriptions-item>
            <el-descriptions-item label="企业资质" :span="2">{{ detail.qualifications?.join('、') || '-' }}</el-descriptions-item>
            <el-descriptions-item label="备注" :span="2">{{ detail.remark || '-' }}</el-descriptions-item>
            <el-descriptions-item label="创建时间" :span="2">
              {{ formatDateTime(detail.created_at) }}
            </el-descriptions-item>
          </el-descriptions>

          <div class="detail-block">
            <div class="detail-block__title">资质附件（营业执照 / 检测资质）</div>
            <FileUpload
              v-if="detail.id"
              :model-value="''"
              biz-type="enterprise_license"
              tip="上传后请在编辑弹窗中保存文件地址（后端 sys_file 已按 biz_type 归档）"
              @uploaded="() => ElMessage.success('资质附件已上传，可在文件管理中查看')"
            />
          </div>

          <div class="detail-block">
            <div class="detail-block__title">经营统计（/enterprises/{id}/stats）</div>
            <el-row :gutter="10">
              <el-col :span="6">
                <div class="stat-cell">
                  <div class="stat-cell__label">商品总数</div>
                  <div class="stat-cell__value">{{ stats?.product_count ?? '-' }}</div>
                </div>
              </el-col>
              <el-col :span="6">
                <div class="stat-cell">
                  <div class="stat-cell__label">库存总量</div>
                  <div class="stat-cell__value">{{ formatQuantity(stats?.inventory_quantity) }} 吨</div>
                </div>
              </el-col>
              <el-col :span="6">
                <div class="stat-cell">
                  <div class="stat-cell__label">订单数</div>
                  <div class="stat-cell__value">{{ stats?.order_count ?? '-' }}</div>
                </div>
              </el-col>
              <el-col :span="6">
                <div class="stat-cell">
                  <div class="stat-cell__label">交易额</div>
                  <div class="stat-cell__value">{{ formatAmount(stats?.order_amount) }}</div>
                </div>
              </el-col>
            </el-row>
          </div>

          <div class="drawer-footer">
            <el-button
              v-permission="'merchant:audit'"
              type="success"
              :disabled="detail.audit_status === 'approved'"
              @click="openAudit(detail, true)"
            >
              审核通过
            </el-button>
            <el-button
              v-permission="'merchant:audit'"
              type="warning"
              :disabled="detail.audit_status === 'rejected'"
              @click="openAudit(detail, false)"
            >
              驳回
            </el-button>
          </div>
        </template>
      </div>
    </el-drawer>

    <!-- 新增 / 编辑 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="720px" append-to-body>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="120px">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="企业编码">
              <el-input v-model="form.code" placeholder="留空由后端生成" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="企业类型" prop="enterprise_type">
              <DictSelect
                v-model="form.enterprise_type"
                group="enterpriseType"
                :clearable="false"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="企业名称" prop="name">
              <el-input v-model="form.name" placeholder="请输入营业执照上的企业全称" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="信用代码" prop="unified_social_credit_code">
              <el-input v-model="form.unified_social_credit_code" placeholder="18 位统一社会信用代码" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="法定代表人">
              <el-input v-model="form.legal_person" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="注册资本(万元)">
              <el-input v-model="form.registered_capital" placeholder="如 500" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="所属园区">
              <el-select v-model="form.park_id" placeholder="请选择园区" clearable style="width: 100%">
                <el-option v-for="item in parks" :key="item.id" :label="item.name" :value="item.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="联系人">
              <el-input v-model="form.contact_name" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="联系电话" prop="contact_phone">
              <el-input v-model="form.contact_phone" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="邮箱">
              <el-input v-model="form.email" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="行政区划">
              <el-input v-model="form.region" placeholder="如 新疆·阿勒泰" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="详细地址">
              <el-input v-model="form.address" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="结算银行">
              <el-input v-model="form.settle_bank" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="开户名">
              <el-input v-model="form.settle_account_name" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="结算账号">
              <el-input v-model="form.settle_account_no" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="营业执照">
              <FileUpload v-model="form.license_url" biz-type="enterprise_license" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="经营范围">
              <el-input v-model="form.business_scope" type="textarea" :rows="2" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="企业简介">
              <el-input v-model="form.profile" type="textarea" :rows="3" maxlength="2000" show-word-limit placeholder="用于企业展示主页，请填写真实的企业介绍" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="企业资质">
              <el-input v-model="qualificationsText" type="textarea" :rows="3" placeholder="每行一项资质名称，资质附件仍在详情页上传" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="备注">
              <el-input v-model="form.remark" type="textarea" :rows="2" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>

    <!-- 审核 -->
    <el-dialog
      v-model="auditVisible"
      :title="auditForm.approved ? '审核通过' : '审核驳回'"
      width="480px"
      append-to-body
    >
      <el-form label-width="90px">
        <el-form-item label="企业名称">
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
.enterprise-thumb { width: 72px; height: 52px; border-radius: 6px; display: block; margin: 2px auto; }
.image-preview { width: 100%; height: 190px; border-radius: 8px; margin: 8px 0 16px; }
.image-hint { color: var(--gz-text-sub); font-size: 13px; line-height: 1.6; }
.detail-block {
  margin-top: 16px;
}

.detail-block__title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 8px;
}

.stat-cell {
  padding: 10px;
  border-radius: 4px;
  background: #f7f9fa;
  text-align: center;
}

.stat-cell__label {
  font-size: 12px;
  color: var(--gz-text-sub);
}

.stat-cell__value {
  font-size: 16px;
  font-weight: 600;
  margin-top: 4px;
}

.drawer-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 20px;
}
</style>

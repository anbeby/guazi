<script setup lang="ts">
/**
 * 商品分类树管理：GET /categories/tree（含商品数），POST/PUT/DELETE /categories。
 * 瓜子油料预置分类：葵花籽 / 南瓜籽 / 打瓜籽 / 加工产品。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'

import StatusTag from '@/components/StatusTag.vue'
import DictSelect from '@/components/DictSelect.vue'
import { createCategory, deleteCategory, getCategoryTree, updateCategory } from '@/api/category'
import type { Category, CategoryPayload } from '@/api/types'

const loading = ref(false)
const tree = ref<Category[]>([])
const tableRef = ref<{ toggleRowExpansion: (row: Category, expanded?: boolean) => void }>()

interface FlatCategory extends Category {
  depth: number
  parent_name: string
  has_children: boolean
}

function flatten(nodes: Category[], depth = 0, parentName = ''): FlatCategory[] {
  const rows: FlatCategory[] = []
  nodes.forEach((node) => {
    rows.push({
      ...node,
      depth,
      parent_name: parentName,
      has_children: Boolean(node.children && node.children.length > 0)
    })
    if (node.children?.length) {
      rows.push(...flatten(node.children, depth + 1, node.name))
    }
  })
  return rows
}

const flatRows = computed(() => flatten(tree.value))

const totalProductCount = computed(() =>
  flatRows.value.reduce((sum, item) => sum + (item.product_count || 0), 0)
)

async function loadTree(): Promise<void> {
  loading.value = true
  try {
    tree.value = await getCategoryTree()
  } catch {
    tree.value = []
  } finally {
    loading.value = false
  }
}

/* el-table 树形展开控制 */
function toggleExpand(row: Category, expanded: boolean): void {
  tableRef.value?.toggleRowExpansion(row, expanded)
}

function expandAll(): void {
  flatRows.value.forEach((row) => toggleExpand(row, true))
}

function collapseAll(): void {
  flatRows.value.forEach((row) => toggleExpand(row, false))
}

/* ---------------- 新增 / 编辑 ---------------- */
const dialogVisible = ref(false)
const dialogTitle = ref('新增分类')
const submitting = ref(false)
const formRef = ref<FormInstance>()
const editingId = ref<number | null>(null)
const form = reactive<CategoryPayload>({
  code: '',
  name: '',
  parent_id: null,
  sort: 0,
  status: 'active',
  description: ''
})

const rules: FormRules = {
  code: [{ required: true, message: '请输入分类编码，如 GZ-SUN', trigger: 'blur' }],
  name: [{ required: true, message: '请输入分类名称', trigger: 'blur' }]
}

/** 父级候选：排除自身与子孙，避免形成环 */
const parentOptions = computed(() => {
  const excludeIds = new Set<number>()
  const collect = (node: Category): void => {
    excludeIds.add(node.id)
    node.children?.forEach(collect)
  }
  if (editingId.value !== null) {
    const find = (nodes: Category[]): Category | null => {
      for (const node of nodes) {
        if (node.id === editingId.value) return node
        const hit = node.children ? find(node.children) : null
        if (hit) return hit
      }
      return null
    }
    const self = find(tree.value)
    if (self) collect(self)
  }

  const rows: { label: string; value: number }[] = []
  const walk = (nodes: Category[], depth: number): void => {
    nodes.forEach((node) => {
      if (!excludeIds.has(node.id)) {
        rows.push({ label: `${'　'.repeat(depth)}${node.name}`, value: node.id })
      }
      if (node.children?.length) walk(node.children, depth + 1)
    })
  }
  walk(tree.value, 0)
  return rows
})

function openCreate(parent?: Category): void {
  editingId.value = null
  dialogTitle.value = parent ? `新增子分类：${parent.name}` : '新增分类'
  Object.assign(form, {
    code: '',
    name: '',
    parent_id: parent ? parent.id : null,
    sort: 0,
    status: 'active',
    description: ''
  })
  dialogVisible.value = true
}

function openEdit(row: Category): void {
  editingId.value = row.id
  dialogTitle.value = `编辑分类：${row.name}`
  Object.assign(form, {
    code: row.code,
    name: row.name,
    parent_id: row.parent_id ?? null,
    sort: row.sort ?? 0,
    status: row.status || 'active',
    description: row.description || ''
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
        await createCategory({ ...form })
        ElMessage.success('分类创建成功')
      } else {
        await updateCategory(editingId.value, { ...form })
        ElMessage.success('分类已更新')
      }
      dialogVisible.value = false
      loadTree()
    } catch {
      /* 已提示 */
    } finally {
      submitting.value = false
    }
  })
}

async function handleDelete(row: Category): Promise<void> {
  if (row.children && row.children.length > 0) {
    ElMessage.warning('请先删除或迁移子分类')
    return
  }
  if ((row.product_count || 0) > 0) {
    ElMessage.warning(`该分类下存在 ${row.product_count} 个商品，无法删除`)
    return
  }
  try {
    await ElMessageBox.confirm(`确认删除分类「${row.name}」？`, '危险操作', {
      type: 'error',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }
  try {
    await deleteCategory(row.id)
    ElMessage.success('删除成功')
    loadTree()
  } catch {
    /* 已提示 */
  }
}

onMounted(loadTree)
</script>

<template>
  <div class="page-container">
    <div class="page-card">
      <div class="page-title">
        <span>
          商品分类树
          <span class="page-title__sub">
            共 {{ flatRows.length }} 个分类 · 关联商品 {{ totalProductCount }} 个
          </span>
        </span>
        <div class="flex-center" style="gap: 8px">
          <el-button size="small" @click="expandAll">展开全部</el-button>
          <el-button size="small" @click="collapseAll">收起全部</el-button>
          <el-button size="small" @click="loadTree">
            <el-icon><Refresh /></el-icon>
            <span>刷新</span>
          </el-button>
          <el-button v-permission="'product:write'" size="small" type="primary" @click="openCreate()">
            <el-icon><Plus /></el-icon>
            <span>新增分类</span>
          </el-button>
        </div>
      </div>

      <el-table
        ref="tableRef"
        v-loading="loading"
        :data="tree"
        row-key="id"
        border
        default-expand-all
        :tree-props="{ children: 'children' }"
      >
        <el-table-column prop="name" label="分类名称" min-width="240">
          <template #default="{ row }">
            <span class="category-name">
              <el-icon v-if="row.children && row.children.length" class="category-name__icon">
                <Folder />
              </el-icon>
              <el-icon v-else class="category-name__icon"><Document /></el-icon>
              {{ row.name }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="code" label="分类编码" min-width="130" />
        <el-table-column label="商品数" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.product_count" size="small" type="success">{{ row.product_count }}</el-tag>
            <span v-else class="text-sub">0</span>
          </template>
        </el-table-column>
        <el-table-column label="层级" width="80" align="center">
          <template #default="{ row }">{{ row.level ?? '-' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <StatusTag group="commonStatus" :value="row.status" />
          </template>
        </el-table-column>
        <el-table-column label="排序" width="80" align="center">
          <template #default="{ row }">{{ row.sort ?? 0 }}</template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button v-permission="'product:write'" link type="primary" @click="openCreate(row as Category)">
              新增子类
            </el-button>
            <el-button v-permission="'product:write'" link type="primary" @click="openEdit(row as Category)">编辑</el-button>
            <el-button v-permission="'product:write'" link type="danger" @click="handleDelete(row as Category)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="520px" append-to-body>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="分类编码" prop="code">
          <el-input v-model="form.code" placeholder="如 GZ-SUN（葵花籽）" :disabled="editingId !== null" />
        </el-form-item>
        <el-form-item label="分类名称" prop="name">
          <el-input v-model="form.name" placeholder="如 葵花籽" />
        </el-form-item>
        <el-form-item label="上级分类">
          <el-select v-model="form.parent_id" placeholder="顶级分类留空" clearable style="width: 100%">
            <el-option v-for="item in parentOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <DictSelect v-model="form.status" group="commonStatus" :clearable="false" style="width: 100%" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sort" :min="0" :max="9999" style="width: 100%" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.category-name {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.category-name__icon {
  color: var(--gz-primary);
}
</style>

<script setup lang="ts">
/**
 * 文件上传组件（对接 POST /api/v1/files/upload，multipart/form-data：file、biz_type）。
 *
 * 用法：
 *   <FileUpload v-model="form.test_report_url" biz-type="product_report" accept=".pdf,.jpg,.png" />
 */
import { computed, ref } from 'vue'
import { ElMessage, type UploadRequestOptions } from 'element-plus'

import { uploadFile } from '@/api/file'
import { formatFileSize } from '@/utils/format'

const props = withDefaults(
  defineProps<{
    modelValue?: string | null
    /** 业务类型，透传给后端 sys_file.biz_type */
    bizType?: string
    accept?: string
    /** 大小上限（MB） */
    maxSize?: number
    /** 是否允许多选（多选时 modelValue 用逗号分隔） */
    multiple?: boolean
    disabled?: boolean
    tip?: string
  }>(),
  {
    modelValue: '',
    bizType: 'common',
    accept: '.pdf,.jpg,.jpeg,.png,.webp,.doc,.docx,.xls,.xlsx',
    maxSize: 20,
    multiple: false,
    disabled: false,
    tip: ''
  }
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'uploaded', payload: { file_key: string; url: string; size: number }): void
}>()

const uploading = ref(false)
const progress = ref(0)

const urls = computed<string[]>(() => {
  if (!props.modelValue) return []
  return String(props.modelValue)
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
})

const tips = computed(() => {
  if (props.tip) return props.tip
  return `支持 ${props.accept}，单个文件不超过 ${props.maxSize}MB`
})

function beforeUpload(file: File): boolean {
  const overSize = file.size / 1024 / 1024 > props.maxSize
  if (overSize) {
    ElMessage.warning(`文件大小不能超过 ${props.maxSize}MB`)
    return false
  }
  return true
}

async function customUpload(options: UploadRequestOptions): Promise<void> {
  const file = options.file as File
  uploading.value = true
  progress.value = 0
  try {
    const result = await uploadFile(file, props.bizType, (percent) => {
      progress.value = percent
    })
    const nextUrls = props.multiple ? [...urls.value, result.url] : [result.url]
    emit('update:modelValue', nextUrls.join(','))
    emit('uploaded', result)
    ElMessage.success(`上传成功（${formatFileSize(result.size)}）`)
  } catch {
    // 错误提示由 axios 拦截器统一处理
  } finally {
    uploading.value = false
  }
}

function removeAt(index: number): void {
  const next = urls.value.filter((_, i) => i !== index)
  emit('update:modelValue', next.join(','))
}

function fileName(url: string): string {
  const clean = url.split('?')[0]
  const segments = clean.split('/')
  return segments[segments.length - 1] || url
}
</script>

<template>
  <div class="file-upload">
    <div v-if="urls.length > 0" class="file-upload__list">
      <div v-for="(url, index) in urls" :key="url" class="file-upload__item">
        <el-icon><Document /></el-icon>
        <a class="file-upload__link text-ellipsis" :href="url" target="_blank" rel="noopener">
          {{ fileName(url) }}
        </a>
        <el-icon v-if="!disabled" class="file-upload__remove" @click="removeAt(index)">
          <Delete />
        </el-icon>
      </div>
    </div>

    <el-upload
      :show-file-list="false"
      :multiple="multiple"
      :disabled="disabled || uploading"
      :accept="accept"
      :before-upload="beforeUpload"
      :http-request="customUpload"
    >
      <el-button :loading="uploading" :disabled="disabled" size="small">
        <el-icon><UploadFilled /></el-icon>
        <span>{{ uploading ? `上传中 ${progress}%` : '选择文件上传' }}</span>
      </el-button>
    </el-upload>

    <div class="file-upload__tip">{{ tips }}</div>
  </div>
</template>

<style scoped>
.file-upload__list {
  margin-bottom: 8px;
}

.file-upload__item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  line-height: 24px;
}

.file-upload__link {
  max-width: 320px;
  color: var(--gz-primary);
}

.file-upload__remove {
  cursor: pointer;
  color: #c0392b;
}

.file-upload__tip {
  margin-top: 4px;
  font-size: 12px;
  color: var(--gz-text-sub);
}
</style>

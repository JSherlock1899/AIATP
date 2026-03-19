<template>
  <div class="source-code-parse-container">
    <div class="header">
      <el-button @click="goBack">返回</el-button>
      <h2>源码解析 - {{ project?.name }}</h2>
      <div class="header-actions">
        <el-button type="primary" @click="showParseDialog = true">新建解析</el-button>
      </div>
    </div>

    <el-tabs v-model="activeTab" class="parse-tabs">
      <el-tab-pane label="解析任务" name="projects">
        <div class="projects-header">
          <span>共 {{ sourceProjects.length }} 个解析任务</span>
        </div>
        <el-table :data="sourceProjects" v-loading="loadingProjects" stripe>
          <el-table-column prop="id" label="ID" width="80" />
          <el-table-column prop="name" label="名称" show-overflow-tooltip />
          <el-table-column prop="source_path" label="源码路径" show-overflow-tooltip />
          <el-table-column prop="language" label="语言" width="100" />
          <el-table-column prop="status" label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="getStatusType(row.status)">{{ getStatusText(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="endpoints_count" label="端点数" width="100" />
          <el-table-column prop="created_at" label="创建时间" width="180">
            <template #default="{ row }">
              {{ formatDate(row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="200">
            <template #default="{ row }">
              <el-button type="primary" size="small" @click="handleViewDetails(row)">详情</el-button>
              <el-button
                type="warning"
                size="small"
                :loading="row.id === parsingId"
                :disabled="row.status === 'parsing'"
                @click="handleReParse(row)"
                v-if="row.status === 'failed'"
              >
                重试
              </el-button>
              <el-button type="danger" size="small" @click="handleDelete(row.id)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div v-if="sourceProjects.length === 0 && !loadingProjects" class="placeholder">
          暂无解析任务，点击"新建解析"开始
        </div>
      </el-tab-pane>

      <el-tab-pane label="解析详情" name="details" :disabled="!selectedProject">
        <div v-if="selectedProject" class="detail-content">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="名称">{{ selectedProject.name }}</el-descriptions-item>
            <el-descriptions-item label="源码路径">{{ selectedProject.source_path }}</el-descriptions-item>
            <el-descriptions-item label="语言">{{ selectedProject.language }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="getStatusType(selectedProject.status)">
                {{ getStatusText(selectedProject.status) }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="端点数量">{{ selectedProject.endpoints_count }}</el-descriptions-item>
            <el-descriptions-item label="解析时间">
              {{ selectedProject.parsed_at ? formatDate(selectedProject.parsed_at) : '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="错误信息" :span="2" v-if="selectedProject.error_message">
              <span style="color: #f56c6c">{{ selectedProject.error_message }}</span>
            </el-descriptions-item>
          </el-descriptions>

          <el-divider />

          <div class="endpoints-section">
            <div class="endpoints-header">
              <span>解析出的 API 端点 ({{ endpoints.length }})</span>
            </div>
            <el-table :data="endpoints" v-loading="loadingEndpoints" stripe>
              <el-table-column prop="id" label="ID" width="80" />
              <el-table-column prop="path" label="路径" show-overflow-tooltip />
              <el-table-column prop="method" label="方法" width="100">
                <template #default="{ row }">
                  <el-tag :type="getMethodType(row.method)">{{ row.method }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="summary" label="描述" show-overflow-tooltip />
              <el-table-column label="参数" width="120">
                <template #default="{ row }">
                  {{ row.parameters?.length || 0 }}
                </template>
              </el-table-column>
            </el-table>
            <div v-if="endpoints.length === 0 && !loadingEndpoints" class="placeholder">
              暂无端点数据
            </div>
          </div>
        </div>
        <div v-else class="placeholder">请先选择一个解析任务查看详情</div>
      </el-tab-pane>
    </el-tabs>

    <!-- 新建解析对话框 -->
    <el-dialog v-model="showParseDialog" title="新建源码解析" width="500px">
      <el-form :model="parseForm" :rules="parseRules" ref="parseFormRef" label-width="120px">
        <el-form-item label="任务名称" prop="name">
          <el-input v-model="parseForm.name" placeholder="请输入解析任务名称" />
        </el-form-item>
        <el-form-item label="源码路径" prop="source_path">
          <el-input
            v-model="parseForm.source_path"
            placeholder="请输入源码路径，如 /path/to/project"
          />
        </el-form-item>
        <el-form-item label="语言" prop="language">
          <el-select v-model="parseForm.language" placeholder="请选择语言" style="width: 100%">
            <el-option label="Java (Spring Boot)" value="java" />
            <el-option label="Python (FastAPI)" value="python" />
            <el-option label="TypeScript" value="typescript" />
            <el-option label="Go" value="go" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showParseDialog = false">取消</el-button>
        <el-button type="primary" :loading="parsing" @click="handleParse">开始解析</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { projectsApi } from '@/api/projects'
import { sourceCodeApi, type SourceCodeProject, type Endpoint } from '@/api/sourceCode'

const router = useRouter()
const route = useRoute()
const projectId = Number(route.params.id)

const activeTab = ref('projects')
const loadingProjects = ref(false)
const loadingEndpoints = ref(false)
const parsing = ref(false)
const parsingId = ref<number | null>(null)
const showParseDialog = ref(false)
const project = ref<any>(null)
const sourceProjects = ref<SourceCodeProject[]>([])
const endpoints = ref<Endpoint[]>([])
const selectedProject = ref<SourceCodeProject | null>(null)
const parseFormRef = ref<FormInstance>()

const parseForm = reactive({
  name: '',
  source_path: '',
  language: 'java'
})

const parseRules: FormRules = {
  name: [{ required: true, message: '请输入解析任务名称', trigger: 'blur' }],
  source_path: [{ required: true, message: '请输入源码路径', trigger: 'blur' }],
  language: [{ required: true, message: '请选择语言', trigger: 'change' }]
}

const getStatusType = (status: string) => {
  const types: Record<string, any> = {
    pending: 'info',
    parsing: 'warning',
    completed: 'success',
    failed: 'danger'
  }
  return types[status] || 'info'
}

const getStatusText = (status: string) => {
  const texts: Record<string, string> = {
    pending: '等待中',
    parsing: '解析中',
    completed: '已完成',
    failed: '失败'
  }
  return texts[status] || status
}

const getMethodType = (method?: string) => {
  if (!method) return ''
  const types: Record<string, any> = {
    GET: '',
    POST: 'success',
    PUT: 'warning',
    DELETE: 'danger',
    PATCH: 'info'
  }
  return types[method] || ''
}

const formatDate = (dateStr?: string) => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN')
}

const fetchProject = async () => {
  try {
    project.value = await projectsApi.getById(projectId)
  } catch (error) {
    ElMessage.error('获取项目信息失败')
  }
}

const fetchSourceProjects = async () => {
  loadingProjects.value = true
  try {
    sourceProjects.value = await sourceCodeApi.list(projectId)
  } catch (error) {
    ElMessage.error('获取解析任务列表失败')
  } finally {
    loadingProjects.value = false
  }
}

const fetchEndpoints = async (sourceProjectId: number) => {
  loadingEndpoints.value = true
  try {
    endpoints.value = await sourceCodeApi.getEndpoints(projectId, sourceProjectId)
  } catch (error) {
    ElMessage.error('获取端点列表失败')
    endpoints.value = []
  } finally {
    loadingEndpoints.value = false
  }
}

const goBack = () => {
  router.push(`/projects/${projectId}`)
}

const handleParse = async () => {
  if (!parseFormRef.value) return

  await parseFormRef.value.validate(async (valid) => {
    if (valid) {
      parsing.value = true
      try {
        await sourceCodeApi.parse(projectId, {
          project_id: projectId,
          name: parseForm.name,
          source_path: parseForm.source_path
        })
        ElMessage.success('解析任务已创建')
        showParseDialog.value = false
        resetForm()
        fetchSourceProjects()
        // 刷新列表直到状态变为completed或failed
        pollParseStatus()
      } catch (error: any) {
        ElMessage.error(error.message || '创建解析任务失败')
      } finally {
        parsing.value = false
      }
    }
  })
}

const pollParseStatus = () => {
  const checkStatus = async () => {
    await fetchSourceProjects()
    const pendingOrParsing = sourceProjects.value.some(
      p => p.status === 'pending' || p.status === 'parsing'
    )
    if (pendingOrParsing) {
      setTimeout(checkStatus, 2000)
    }
  }
  setTimeout(checkStatus, 2000)
}

const handleReParse = async (item: SourceCodeProject) => {
  parsingId.value = item.id
  try {
    await sourceCodeApi.parse(projectId, {
      project_id: projectId,
      name: item.name,
      source_path: item.source_path
    })
    ElMessage.success('重新解析已启动')
    fetchSourceProjects()
    pollParseStatus()
  } catch (error: any) {
    ElMessage.error(error.message || '重新解析失败')
  } finally {
    parsingId.value = null
  }
}

const handleViewDetails = async (item: SourceCodeProject) => {
  selectedProject.value = item
  activeTab.value = 'details'
  await fetchEndpoints(item.id)
}

const handleDelete = async (sourceProjectId: number) => {
  try {
    await ElMessageBox.confirm('确定要删除该解析任务吗？', '提示', { type: 'warning' })
    await sourceCodeApi.delete(projectId, sourceProjectId)
    ElMessage.success('删除成功')
    if (selectedProject.value?.id === sourceProjectId) {
      selectedProject.value = null
      endpoints.value = []
      activeTab.value = 'projects'
    }
    fetchSourceProjects()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const resetForm = () => {
  parseForm.name = ''
  parseForm.source_path = ''
  parseForm.language = 'java'
}

onMounted(() => {
  fetchProject()
  fetchSourceProjects()
})
</script>

<style scoped>
.source-code-parse-container {
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.header h2 {
  margin: 0;
  flex: 1;
  text-align: center;
}

.header-actions {
  display: flex;
  gap: 10px;
  align-items: center;
}

.parse-tabs {
  background: #fff;
  padding: 20px;
  border-radius: 4px;
}

.projects-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.placeholder {
  text-align: center;
  color: #999;
  padding: 40px;
}

.detail-content {
  padding: 10px;
}

.endpoints-section {
  margin-top: 20px;
}

.endpoints-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
</style>

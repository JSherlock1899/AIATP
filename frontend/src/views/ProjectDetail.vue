<template>
  <div class="project-detail-container">
    <div class="header">
      <el-button @click="goBack">返回</el-button>
      <h2>{{ project?.name }}</h2>
      <div class="header-actions">
        <el-tag :type="aiStatus.available ? 'success' : 'info'" size="small">
          AI: {{ aiStatus.available ? aiStatus.model || 'OpenAI' : '未配置' }}
        </el-tag>
        <el-button @click="goToSourceCodeParse">源代码解析</el-button>
        <el-button type="primary" @click="showAddDialog = true">添加测试用例</el-button>
      </div>
    </div>

    <el-tabs v-model="activeTab" class="detail-tabs">
      <el-tab-pane label="API 端点" name="endpoints">
        <div class="endpoint-header">
          <span>共 {{ endpoints.length }} 个端点</span>
          <el-button
            type="primary"
            size="small"
            :loading="generatingTestCases"
            @click="handleAIGenerateTestCases"
            :disabled="endpoints.length === 0"
          >
            <el-icon><MagicStick /></el-icon> AI 生成测试用例
          </el-button>
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
          <el-table-column label="参数" width="100">
            <template #default="{ row }">
              {{ row.parameters?.length || 0 }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="200">
            <template #default="{ row }">
              <el-button type="primary" size="small" @click="handleCreateTestCaseForEndpoint(row)">创建用例</el-button>
              <el-button type="warning" size="small" @click="handleAIEnhanceEndpoint(row)">
                <el-icon><MagicStick /></el-icon>
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="测试用例" name="testCases">
        <div class="test-case-header">
          <span>共 {{ testCases.length }} 个用例</span>
          <div class="test-case-actions">
            <el-button
              type="success"
              size="small"
              :disabled="selectedTestCaseIds.length === 0 || isExecuting"
              @click="handleBatchExecute"
            >
              <el-icon><VideoPlay /></el-icon> 批量执行
            </el-button>
          </div>
        </div>
        <el-table
          :data="testCases"
          v-loading="loadingCases"
          stripe
          @selection-change="handleSelectionChange"
          ref="testCaseTableRef"
        >
          <el-table-column type="selection" width="55" />
          <el-table-column prop="id" label="ID" width="80" />
          <el-table-column prop="name" label="用例名称" />
          <el-table-column prop="request_config.method" label="方法" width="100">
            <template #default="{ row }">
              <el-tag :type="getMethodType(row.request_config?.method)">{{ row.request_config?.method }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="request_config.url" label="URL" show-overflow-tooltip />
          <el-table-column label="操作" width="380">
            <template #default="{ row }">
              <el-button type="success" size="small" @click="handleExecute(row.id)">执行</el-button>
              <el-button type="primary" size="small" @click="handleEdit(row)">编辑</el-button>
              <el-button type="warning" size="small" @click="handleAIGenerateAssertions(row)">
                <el-icon><MagicStick /></el-icon> 智能断言
              </el-button>
              <el-button type="danger" size="small" @click="handleDeleteCase(row.id)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="测试结果" name="results">
        <!-- 进度条 -->
        <div v-if="isExecuting" class="execution-progress">
          <el-progress
            :percentage="executionProgress"
            :status="executionProgressStatus"
            :stroke-width="20"
          />
          <div class="progress-info">
            <span>正在执行: {{ currentExecutingName }}</span>
            <span>{{ executedCount }} / {{ totalCount }}</span>
          </div>
          <el-button type="danger" size="small" @click="cancelExecution">取消</el-button>
        </div>

        <div v-if="lastExecutionResult && !isExecuting" class="execution-summary">
          <el-row :gutter="20">
            <el-col :span="6">
              <el-statistic title="总数" :value="lastExecutionResult.total" />
            </el-col>
            <el-col :span="6">
              <el-statistic title="通过" :value="lastExecutionResult.passed" style="color: #67c23a" />
            </el-col>
            <el-col :span="6">
              <el-statistic title="失败" :value="lastExecutionResult.failed" style="color: #f56c6c" />
            </el-col>
            <el-col :span="6">
              <el-statistic title="耗时" :value="lastExecutionResult.execution_time" suffix="ms" />
            </el-col>
          </el-row>

          <!-- 批量重试失败按钮 -->
          <div v-if="lastExecutionResult.failed > 0" class="batch-retry">
            <el-divider />
            <el-button type="warning" @click="handleRetryFailed">
              <el-icon><RefreshRight /></el-icon> 重试所有失败用例
            </el-button>
          </div>

          <el-divider />

          <!-- 结果列表 -->
          <div v-for="result in lastExecutionResult.results" :key="result.id" class="result-item">
            <el-tag :type="result.status === 'passed' ? 'success' : 'danger'">
              {{ result.status === 'passed' ? '通过' : '失败' }}
            </el-tag>
            <span class="result-name">{{ getTestCaseName(result.test_case_id) }}</span>
            <span class="result-time">{{ result.response_time }}ms</span>
            <el-button
              type="warning"
              size="small"
              @click="handleRetrySingle(result.test_case_id)"
            >
              <el-icon><RefreshRight /></el-icon> 重试
            </el-button>
            <el-button
              v-if="result.status === 'failed'"
              type="info"
              size="small"
              @click="toggleResultDetail(result.id)"
            >
              <el-icon><More /></el-icon> 详情
            </el-button>
            <el-button
              v-if="result.status === 'failed'"
              type="warning"
              size="small"
              @click="handleAIAnalyzeFailure(result)"
            >
              <el-icon><MagicStick /></el-icon> AI 分析
            </el-button>

            <!-- 可展开的详情面板 -->
            <el-collapse-transition>
              <div v-if="expandedResultIds.has(result.id)" class="result-detail">
                <el-divider content-position="left">响应数据</el-divider>
                <div class="detail-section">
                  <h6>响应体 (body)</h6>
                  <pre class="code-block">{{ formatJSON(result.response_data?.body) }}</pre>
                </div>
                <div class="detail-section">
                  <h6>响应头 (headers)</h6>
                  <pre class="code-block">{{ formatJSON(result.response_data?.headers) }}</pre>
                </div>

                <el-divider content-position="left">断言结果</el-divider>
                <div class="assertion-results">
                  <div
                    v-for="(assertion, idx) in result.assertion_results"
                    :key="idx"
                    class="assertion-item"
                    :class="{ passed: assertion.passed, failed: !assertion.passed }"
                  >
                    <el-tag :type="assertion.passed ? 'success' : 'danger'" size="small">
                      {{ assertion.passed ? '通过' : '失败' }}
                    </el-tag>
                    <span class="assertion-type">{{ assertion.assertion_type }}</span>
                    <span class="assertion-field">{{ assertion.field }}</span>
                    <span class="assertion-expected">期望: {{ assertion.expected }}</span>
                    <span class="assertion-actual">实际: {{ assertion.actual }}</span>
                    <span v-if="assertion.error_message" class="assertion-error">{{ assertion.error_message }}</span>
                  </div>
                </div>

                <div v-if="result.error_message" class="detail-section">
                  <h6>错误信息</h6>
                  <pre class="code-block error">{{ result.error_message }}</pre>
                </div>
              </div>
            </el-collapse-transition>
          </div>

          <div v-if="lastExecutionResult.failed > 0" class="ai-analysis">
            <el-divider />
            <h4>AI 批量分析</h4>
            <el-button type="warning" @click="handleAIAnalyzeAllFailures">
              <el-icon><MagicStick /></el-icon> 分析所有失败
            </el-button>
          </div>
        </div>
        <div v-else-if="!isExecuting" class="placeholder">暂无测试结果</div>
      </el-tab-pane>
    </el-tabs>

    <!-- AI 建议对话框 -->
    <el-dialog v-model="showAISuggestions" :title="aiDialogTitle" width="800px">
      <div v-if="aiLoading" class="ai-loading">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>AI 思考中...</span>
      </div>
      <div v-else-if="aiSuggestions.length > 0" class="ai-suggestions">
        <div v-for="(suggestion, index) in aiSuggestions" :key="index" class="suggestion-item">
          <h5>{{ suggestion.name || suggestion.type || `建议 ${index + 1}` }}</h5>
          <p v-if="suggestion.description">{{ suggestion.description }}</p>
          <p v-if="suggestion.reasoning" class="reasoning">{{ suggestion.reasoning }}</p>

          <!-- 显示生成的请求体 -->
          <div v-if="suggestion.body" class="request-body-preview">
            <small>生成的请求体：</small>
            <pre>{{ typeof suggestion.body === 'string' ? suggestion.body : JSON.stringify(suggestion.body, null, 2) }}</pre>
          </div>

          <div v-if="suggestion.assertions?.length" class="assertions">
            <small>推荐断言：</small>
            <el-tag
              v-for="(assert, i) in suggestion.assertions"
              :key="i"
              size="small"
              type="info"
              style="margin-right: 4px;"
            >
              {{ assert.type }}: {{ assert.field }} = {{ assert.expected }}
            </el-tag>
          </div>
          <div class="suggestion-actions">
            <el-button type="primary" size="small" @click="applySuggestion(suggestion)">
              应用此建议
            </el-button>
          </div>
        </div>
      </div>
      <div v-else-if="aiAnalysisResult" class="ai-analysis-result">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="错误类型">
            <el-tag :type="getSeverityType(aiAnalysisResult.severity)">
              {{ aiAnalysisResult.error_type }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="严重程度">
            <el-tag :type="getSeverityType(aiAnalysisResult.severity)">
              {{ aiAnalysisResult.severity }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="可能原因">
            {{ aiAnalysisResult.root_cause }}
          </el-descriptions-item>
          <el-descriptions-item label="修复建议">
            <pre class="suggestion-pre">{{ aiAnalysisResult.suggestion }}</pre>
          </el-descriptions-item>
          <el-descriptions-item label="置信度">
            {{ (aiAnalysisResult.confidence * 100).toFixed(0) }}%
          </el-descriptions-item>
        </el-descriptions>
      </div>
      <div v-else class="placeholder">暂无 AI 建议</div>
      <template #footer>
        <el-button @click="showAISuggestions = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 添加/编辑测试用例对话框 -->
    <el-dialog v-model="showAddDialog" :title="editingId ? '编辑测试用例' : '添加测试用例'" width="700px">
      <el-form :model="caseForm" :rules="caseRules" ref="caseFormRef" label-width="100px">
        <el-form-item label="用例名称" prop="name">
          <el-input v-model="caseForm.name" placeholder="请输入用例名称" />
        </el-form-item>
        <el-form-item label="选择端点" prop="endpoint_id">
          <el-select v-model="caseForm.endpoint_id" placeholder="请选择API端点" style="width: 100%" clearable>
            <el-option v-for="ep in endpoints" :key="ep.id" :label="`${ep.method} ${ep.path}`" :value="ep.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="请求方法" prop="request_config.method">
          <el-select v-model="caseForm.request_config.method" style="width: 100%">
            <el-option label="GET" value="GET" />
            <el-option label="POST" value="POST" />
            <el-option label="PUT" value="PUT" />
            <el-option label="DELETE" value="DELETE" />
            <el-option label="PATCH" value="PATCH" />
          </el-select>
        </el-form-item>
        <el-form-item label="请求URL" prop="request_config.url">
          <el-input v-model="caseForm.request_config.url" placeholder="完整URL或路径" />
        </el-form-item>
        <el-form-item label="请求头">
          <el-input
            v-model="caseForm.headersInput"
            type="textarea"
            :rows="2"
            placeholder="格式: Content-Type: application/json (每行一个)"
            @blur="handleHeadersInputBlur"
          />
        </el-form-item>
        <el-form-item label="请求体" prop="body">
          <el-input v-model="caseForm.body" type="textarea" :rows="4" placeholder="JSON 格式" />
        </el-form-item>
        <el-form-item label="断言">
          <div class="assertions-list">
            <div v-for="(assert, index) in caseForm.assertions" :key="index" class="assertion-item">
              <el-tag size="small" type="info">{{ assert.type }}</el-tag>
              <span>{{ assert.field }} = {{ assert.expected }}</span>
              <el-button type="danger" size="small" link @click="removeAssertion(index)">删除</el-button>
            </div>
            <el-button v-if="aiStatus.available" type="warning" size="small" @click="handleAIEnhanceAssertions">
              <el-icon><MagicStick /></el-icon> AI 智能添加断言
            </el-button>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { MagicStick, Loading, RefreshRight, VideoPlay, More } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'
import { projectsApi } from '@/api/projects'
import { testCasesApi, type TestCase, type CreateTestCaseRequest, type TestExecutionResponse, type StreamProgress, type StreamResult, type StreamComplete } from '@/api/testCases'
import { aiApi, type AIStatus, type TestCaseSuggestion, type AssertionSuggestion, type AnomalyAnalysis } from '@/api/ai'
import { sourceCodeApi, type SourceCodeProject, type Endpoint as SourceCodeEndpoint } from '@/api/sourceCode'

const router = useRouter()
const route = useRoute()
const projectId = Number(route.params.id)

interface ApiEndpoint {
  id: number
  path: string
  method: string
  summary: string
  description?: string
  parameters?: Array<{
    name: string
    location: string
    required: boolean
  }>
  request_body?: any
  responses?: any[]
}

const activeTab = ref('endpoints')
const loadingEndpoints = ref(false)
const loadingCases = ref(false)
const saving = ref(false)
const showAddDialog = ref(false)
const project = ref<any>(null)
const testCases = ref<TestCase[]>([])
const endpoints = ref<ApiEndpoint[]>([])
const editingId = ref<number | null>(null)
const caseFormRef = ref<FormInstance>()
const testCaseTableRef = ref<any>()
const lastExecutionResult = ref<TestExecutionResponse | null>(null)

// Stream execution state
const isExecuting = ref(false)
const executionProgress = ref(0)
const executionProgressStatus = ref<'success' | 'warning' | 'exception' | ''>('')
const currentExecutingName = ref('')
const executedCount = ref(0)
const totalCount = ref(0)
const selectedTestCaseIds = ref<number[]>([])
const expandedResultIds = ref(new Set<number>())

// AI 相关状态
const aiStatus = ref<AIStatus>({ provider: 'openai', available: false })
const aiLoading = ref(false)
const showAISuggestions = ref(false)
const aiDialogTitle = ref('')
const aiSuggestions = ref<any[]>([])
const aiAnalysisResult = ref<AnomalyAnalysis | null>(null)
const generatingTestCases = ref(false)

const caseForm = reactive({
  endpoint_id: 0,
  name: '',
  description: '',
  request_config: {
    method: 'GET',
    url: '/',
    headers: {} as Record<string, string>,
    timeout: 30
  },
  headersInput: '',
  body: '',
  assertions: [] as AssertionSuggestion[],
  is_enabled: true
})

// Convert headers object to text for display
const headersToInput = (headers: Record<string, string> | undefined) => {
  if (!headers) return ''
  return Object.entries(headers)
    .map(([k, v]) => `${k}: ${v}`)
    .join('\n')
}

// Parse headers text to object
const handleHeadersInputBlur = () => {
  const lines = caseForm.headersInput.split('\n').filter(l => l.trim())
  const headers: Record<string, string> = {}
  for (const line of lines) {
    const colonIdx = line.indexOf(':')
    if (colonIdx > 0) {
      const key = line.slice(0, colonIdx).trim()
      const value = line.slice(colonIdx + 1).trim()
      if (key && value) {
        headers[key] = value
      }
    }
  }
  caseForm.request_config.headers = headers
}

const caseRules: FormRules = {
  name: [{ required: true, message: '请输入用例名称', trigger: 'blur' }],
  'request_config.method': [{ required: true, message: '请选择请求方法', trigger: 'change' }],
  'request_config.url': [{ required: true, message: '请输入URL', trigger: 'blur' }]
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

const getSeverityType = (severity: string) => {
  const types: Record<string, any> = {
    critical: 'danger',
    high: 'warning',
    medium: 'info',
    low: 'success'
  }
  return types[severity] || 'info'
}

const fetchProject = async () => {
  try {
    project.value = await projectsApi.getById(projectId)
  } catch (error) {
    ElMessage.error('获取项目信息失败')
  }
}

const fetchEndpoints = async () => {
  loadingEndpoints.value = true
  try {
    const sourceProjects = await sourceCodeApi.list(projectId)
    const allEndpoints: any[] = []

    for (const sp of sourceProjects) {
      if (sp.status === 'completed') {
        const eps = await sourceCodeApi.getEndpoints(projectId, sp.id)
        allEndpoints.push(...eps)
      }
    }

    endpoints.value = allEndpoints
  } catch (error) {
    console.error('Failed to load endpoints:', error)
  } finally {
    loadingEndpoints.value = false
  }
}

const fetchTestCases = async () => {
  loadingCases.value = true
  try {
    testCases.value = await testCasesApi.list()
  } catch (error) {
    ElMessage.error('获取测试用例失败')
  } finally {
    loadingCases.value = false
  }
}

const fetchAIStatus = async () => {
  try {
    aiStatus.value = await aiApi.getStatus()
  } catch (error) {
    aiStatus.value = { provider: 'openai', available: false }
  }
}

const goBack = () => {
  router.push('/projects')
}

const goToSourceCodeParse = () => {
  router.push(`/projects/${route.params.id}/source-code`)
}

const handleCreateTestCaseForEndpoint = (endpoint: ApiEndpoint) => {
  editingId.value = null
  caseForm.endpoint_id = endpoint.id
  caseForm.name = endpoint.summary || `${endpoint.method} ${endpoint.path}`
  caseForm.request_config.method = endpoint.method
  caseForm.request_config.url = endpoint.path
  caseForm.body = ''
  caseForm.assertions = []
  showAddDialog.value = true
}

const handleAIEnhanceEndpoint = async (endpoint: ApiEndpoint) => {
  aiLoading.value = true
  aiDialogTitle.value = `AI 增强: ${endpoint.method} ${endpoint.path}`
  aiSuggestions.value = []
  showAISuggestions.value = true

  try {
    const suggestions = await aiApi.generateTestCases({
      path: endpoint.path,
      method: endpoint.method,
      summary: endpoint.summary || '',
      description: endpoint.description || '',
      parameters: endpoint.parameters?.length ? endpoint.parameters : undefined,
      request_body: endpoint.request_body || undefined,
      responses: undefined
    }, 3)
    aiSuggestions.value = suggestions
  } catch (error: any) {
    ElMessage.error(error.message || 'AI 生成失败')
  } finally {
    aiLoading.value = false
  }
}

const handleAIGenerateTestCases = async () => {
  if (endpoints.value.length === 0) {
    ElMessage.warning('暂无端点可供生成')
    return
  }

  generatingTestCases.value = true
  aiDialogTitle.value = 'AI 批量生成测试用例'
  aiSuggestions.value = []
  showAISuggestions.value = true
  aiLoading.value = true

  try {
    // Parallel AI API calls with concurrency limit of 5
    const allSuggestions: any[] = []
    const concurrency = 5
    const endpointsCopy = [...endpoints.value]

    for (let i = 0; i < endpointsCopy.length; i += concurrency) {
      const batch = endpointsCopy.slice(i, i + concurrency)
      const batchPromises = batch.map(endpoint =>
        aiApi.generateTestCases({
          path: endpoint.path,
          method: endpoint.method,
          summary: endpoint.summary || '',
          description: endpoint.description || '',
          parameters: endpoint.parameters?.length ? endpoint.parameters : undefined,
          request_body: endpoint.request_body || undefined,
          responses: undefined
        }, 2).then(suggestions => ({ suggestions, endpoint }))
      )
      const batchResults = await Promise.all(batchPromises)
      for (const { suggestions, endpoint } of batchResults) {
        allSuggestions.push(...suggestions.map(s => ({ ...s, endpoint })))
      }
    }
    aiSuggestions.value = allSuggestions
  } catch (error: any) {
    ElMessage.error(error.message || 'AI 生成失败')
  } finally {
    generatingTestCases.value = false
    aiLoading.value = false
  }
}

// Fixed: handleAIEnhanceAssertions now executes the test first to get real response
const handleAIEnhanceAssertions = async () => {
  // 先执行测试获取真实响应
  if (!editingId.value) {
    ElMessage.warning('请先保存测试用例后再生成断言')
    return
  }

  aiLoading.value = true
  aiDialogTitle.value = 'AI 智能断言建议'
  aiSuggestions.value = []
  showAISuggestions.value = true

  try {
    // 执行测试获取真实响应
    const result = await testCasesApi.execute([editingId.value])
    if (result.results && result.results[0]) {
      const response = result.results[0].response_data || {}
      response.response_time = result.results[0].response_time

      const suggestions = await aiApi.generateAssertions(response, {
        test_case_id: editingId.value,
        url: caseForm.request_config.url,
        method: caseForm.request_config.method
      })
      aiSuggestions.value = suggestions.map(s => ({ assertions: [s] }))
    }
  } catch (error: any) {
    ElMessage.error(error.message || 'AI 生成失败')
  } finally {
    aiLoading.value = false
  }
}

const handleAIGenerateAssertions = async (testCase: TestCase) => {
  aiLoading.value = true
  aiDialogTitle.value = `AI 断言: ${testCase.name}`
  aiSuggestions.value = []
  showAISuggestions.value = true

  try {
    // 先执行测试获取响应
    const result = await testCasesApi.execute([testCase.id])
    if (result.results && result.results[0]) {
      const response = result.results[0].response_data || {}
      response.response_time = result.results[0].response_time

      const suggestions = await aiApi.generateAssertions(response, {
        test_case_id: testCase.id,
        url: testCase.request_config.url
      })
      aiSuggestions.value = suggestions.map(s => ({ assertions: [s] }))
    }
  } catch (error: any) {
    ElMessage.error(error.message || 'AI 生成失败')
  } finally {
    aiLoading.value = false
  }
}

const handleAIAnalyzeFailure = async (result: any) => {
  aiLoading.value = true
  aiDialogTitle.value = 'AI 失败分析'
  aiSuggestions.value = []
  aiAnalysisResult.value = null
  showAISuggestions.value = true

  try {
    aiAnalysisResult.value = await aiApi.analyzeAnomaly({
      status: result.status,
      error_message: result.error_message,
      response_data: result.response_data,
      assertion_results: result.assertion_results
    })
  } catch (error: any) {
    ElMessage.error(error.message || 'AI 分析失败')
  } finally {
    aiLoading.value = false
  }
}

const handleAIAnalyzeAllFailures = async () => {
  if (!lastExecutionResult.value) return

  const failedResults = lastExecutionResult.value.results.filter(r => r.status === 'failed')
  if (failedResults.length === 0) {
    ElMessage.info('没有失败的测试')
    return
  }

  aiLoading.value = true
  aiDialogTitle.value = 'AI 批量失败分析'
  aiAnalysisResult.value = null
  aiSuggestions.value = []
  showAISuggestions.value = true

  try {
    const analyses = await Promise.all(
      failedResults.map(r => aiApi.analyzeAnomaly({
        status: r.status,
        error_message: r.error_message,
        response_data: r.response_data,
        assertion_results: r.assertion_results
      }))
    )

    const criticalCount = analyses.filter(a => a.severity === 'critical' || a.severity === 'high').length
    aiAnalysisResult.value = {
      error_type: 'multiple',
      severity: criticalCount > 0 ? 'high' : 'medium',
      root_cause: `共有 ${failedResults.length} 个测试失败，其中 ${criticalCount} 个高严重性问题`,
      suggestion: analyses.map((a, i) => `${i + 1}. ${a.suggestion}`).join('\n'),
      confidence: analyses.reduce((sum, a) => sum + a.confidence, 0) / analyses.length
    }
  } catch (error: any) {
    ElMessage.error(error.message || 'AI 分析失败')
  } finally {
    aiLoading.value = false
  }
}

const applySuggestion = (suggestion: any) => {
  caseForm.name = suggestion.name || caseForm.name
  caseForm.description = suggestion.description || caseForm.description
  caseForm.request_config.method = suggestion.method || caseForm.request_config.method
  caseForm.request_config.url = suggestion.url || caseForm.request_config.url
  if (suggestion.body) {
    caseForm.body = typeof suggestion.body === 'string' ? suggestion.body : JSON.stringify(suggestion.body)
  }
  if (suggestion.assertions?.length) {
    caseForm.assertions = suggestion.assertions
  }
  if (suggestion.endpoint?.id) {
    caseForm.endpoint_id = suggestion.endpoint.id
  }
  showAISuggestions.value = false
  showAddDialog.value = true
  ElMessage.success('已应用 AI 建议')
}

const removeAssertion = (index: number) => {
  caseForm.assertions.splice(index, 1)
}

const handleExecute = async (testCaseId: number) => {
  try {
    const result = await testCasesApi.execute([testCaseId])
    lastExecutionResult.value = result
    ElMessage.success('执行完成')
    activeTab.value = 'results'
  } catch (error) {
    ElMessage.error('执行失败')
  }
}

// Batch execution with SSE streaming
let cleanupExecution: (() => void) | null = null

const handleBatchExecute = () => {
  if (selectedTestCaseIds.value.length === 0) {
    ElMessage.warning('请先选择要执行的测试用例')
    return
  }

  isExecuting.value = true
  executionProgress.value = 0
  executionProgressStatus.value = ''
  executedCount.value = 0
  totalCount.value = selectedTestCaseIds.value.length
  currentExecutingName.value = '准备开始...'
  lastExecutionResult.value = null

  // Initialize results array
  const results: any[] = []

  cleanupExecution = testCasesApi.executeStream(
    selectedTestCaseIds.value,
    undefined,
    {
      onProgress: (data: StreamProgress) => {
        executedCount.value = data.current
        totalCount.value = data.total
        executionProgress.value = Math.round((data.current / data.total) * 100)
        currentExecutingName.value = getTestCaseName(data.test_case_id)
      },
      onResult: (data: StreamResult) => {
        results.push({
          id: data.result_id || Date.now(),
          test_case_id: data.test_case_id,
          status: data.passed ? 'passed' : 'failed',
          response_data: null,
          response_time: data.response_time,
          error_message: data.error_message,
          assertion_results: data.assertion_results,
          executed_at: new Date().toISOString()
        })
      },
      onComplete: (data: StreamComplete) => {
        lastExecutionResult.value = {
          total: data.total,
          passed: data.passed,
          failed: data.failed,
          error: data.error,
          skipped: data.skipped,
          results: results,
          execution_time: data.execution_time
        }
        isExecuting.value = false
        executionProgress.value = 100
        executionProgressStatus.value = data.failed > 0 ? 'warning' : 'success'
        activeTab.value = 'results'
        ElMessage.success('批量执行完成')
      },
      onError: (error: Error) => {
        ElMessage.error(error.message || '执行失败')
        isExecuting.value = false
      }
    }
  )
}

const cancelExecution = () => {
  if (cleanupExecution) {
    cleanupExecution()
    cleanupExecution = null
  }
  isExecuting.value = false
  ElMessage.info('已取消执行')
}

// Retry single test case
const handleRetrySingle = async (testCaseId: number) => {
  try {
    const result = await testCasesApi.execute([testCaseId])
    if (lastExecutionResult.value) {
      // Update the specific result in the array
      const index = lastExecutionResult.value.results.findIndex(r => r.test_case_id === testCaseId)
      if (index >= 0 && result.results[0]) {
        lastExecutionResult.value.results[index] = result.results[0]
      }
      // Update counts
      if (result.results[0].status === 'passed') {
        lastExecutionResult.value.passed++
        lastExecutionResult.value.failed--
      }
    } else {
      lastExecutionResult.value = result
    }
    ElMessage.success('重试完成')
  } catch (error) {
    ElMessage.error('重试失败')
  }
}

// Retry all failed test cases
const handleRetryFailed = async () => {
  if (!lastExecutionResult.value) return

  const failedIds = lastExecutionResult.value.results
    .filter(r => r.status === 'failed')
    .map(r => r.test_case_id)

  if (failedIds.length === 0) {
    ElMessage.info('没有失败的用例')
    return
  }

  // Use batch execute with SSE
  isExecuting.value = true
  executionProgress.value = 0
  executedCount.value = 0
  totalCount.value = failedIds.length
  currentExecutingName.value = '准备重试...'

  const results: any[] = []
  const originalResults = [...lastExecutionResult.value.results]

  cleanupExecution = testCasesApi.executeStream(
    failedIds,
    undefined,
    {
      onProgress: (data: StreamProgress) => {
        executedCount.value = data.current
        totalCount.value = data.total
        executionProgress.value = Math.round((data.current / data.total) * 100)
        currentExecutingName.value = getTestCaseName(data.test_case_id)
      },
      onResult: (data: StreamResult) => {
        results.push({
          id: data.result_id || Date.now(),
          test_case_id: data.test_case_id,
          status: data.passed ? 'passed' : 'failed',
          response_data: null,
          response_time: data.response_time,
          error_message: data.error_message,
          assertion_results: data.assertion_results,
          executed_at: new Date().toISOString()
        })
      },
      onComplete: (data: StreamComplete) => {
        // Merge results with original
        const mergedResults = originalResults.map(original => {
          const retryResult = results.find(r => r.test_case_id === original.test_case_id)
          return retryResult || original
        })

        lastExecutionResult.value = {
          total: lastExecutionResult.value!.total,
          passed: lastExecutionResult.value!.passed + data.passed,
          failed: data.failed,
          error: data.error,
          skipped: lastExecutionResult.value!.skipped + data.skipped,
          results: mergedResults,
          execution_time: lastExecutionResult.value!.execution_time + data.execution_time
        }

        isExecuting.value = false
        executionProgress.value = 100
        executionProgressStatus.value = data.failed > 0 ? 'warning' : 'success'
        ElMessage.success('重试完成')
      },
      onError: (error: Error) => {
        ElMessage.error(error.message || '重试失败')
        isExecuting.value = false
      }
    }
  )
}

// Toggle result detail expansion
const toggleResultDetail = (resultId: number) => {
  if (expandedResultIds.value.has(resultId)) {
    expandedResultIds.value.delete(resultId)
  } else {
    expandedResultIds.value.add(resultId)
  }
}

// Format JSON for display
const formatJSON = (data: any) => {
  if (!data) return 'null'
  if (typeof data === 'string') {
    try {
      return JSON.stringify(JSON.parse(data), null, 2)
    } catch {
      return data
    }
  }
  return JSON.stringify(data, null, 2)
}

const handleSelectionChange = (selection: TestCase[]) => {
  selectedTestCaseIds.value = selection.map(s => s.id)
}

const handleEdit = (testCase: TestCase) => {
  editingId.value = testCase.id
  caseForm.endpoint_id = testCase.endpoint_id
  caseForm.name = testCase.name
  caseForm.description = testCase.description || ''
  caseForm.request_config = { ...testCase.request_config }
  caseForm.headersInput = headersToInput(testCase.request_config.headers)
  caseForm.body = typeof testCase.request_config.body === 'string'
    ? testCase.request_config.body
    : JSON.stringify(testCase.request_config.body, null, 2)
  caseForm.assertions = testCase.expected_response?.assertions || []
  showAddDialog.value = true
}

const handleDeleteCase = async (testCaseId: number) => {
  try {
    await ElMessageBox.confirm('确定要删除该测试用例吗？', '提示', { type: 'warning' })
    await testCasesApi.delete(testCaseId)
    ElMessage.success('删除成功')
    fetchTestCases()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const handleSave = async () => {
  if (!caseFormRef.value) return

  handleHeadersInputBlur()

  await caseFormRef.value.validate(async (valid) => {
    if (valid) {
      saving.value = true
      try {
        const data: CreateTestCaseRequest = {
          endpoint_id: caseForm.endpoint_id || 1,
          name: caseForm.name,
          description: caseForm.description,
          request_config: {
            ...caseForm.request_config,
            body: caseForm.body ? JSON.parse(caseForm.body) : undefined
          },
          assertions: caseForm.assertions,
          is_enabled: caseForm.is_enabled
        }

        if (editingId.value) {
          await testCasesApi.update(editingId.value, data)
          ElMessage.success('更新成功')
        } else {
          await testCasesApi.create(data)
          ElMessage.success('添加成功')
        }
        showAddDialog.value = false
        resetForm()
        fetchTestCases()
      } catch (error: any) {
        if (error?.message?.includes('JSON')) {
          ElMessage.error('请求体格式错误，请输入正确的JSON')
        } else {
          ElMessage.error('保存失败')
        }
      } finally {
        saving.value = false
      }
    }
  })
}

const resetForm = () => {
  editingId.value = null
  caseForm.endpoint_id = 0
  caseForm.name = ''
  caseForm.description = ''
  caseForm.request_config = { method: 'GET', url: '/', headers: {}, timeout: 30 }
  caseForm.headersInput = ''
  caseForm.body = ''
  caseForm.assertions = []
}

const getTestCaseName = (testCaseId: number) => {
  const tc = testCases.value.find(t => t.id === testCaseId)
  return tc?.name || `用例 #${testCaseId}`
}

onMounted(() => {
  fetchProject()
  fetchEndpoints()
  fetchTestCases()
  fetchAIStatus()
})

watch(activeTab, (newTab) => {
  if (newTab === 'endpoints' && endpoints.value.length === 0) {
    fetchEndpoints()
  }
})
</script>

<style scoped>
.project-detail-container {
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

.endpoint-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.test-case-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.test-case-actions {
  display: flex;
  gap: 10px;
}

.detail-tabs {
  background: #fff;
  padding: 20px;
  border-radius: 4px;
}

.placeholder {
  text-align: center;
  color: #999;
  padding: 40px;
}

.execution-summary {
  padding: 10px;
}

.execution-progress {
  margin-bottom: 20px;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 4px;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  margin-top: 8px;
  font-size: 14px;
  color: #606266;
}

.batch-retry {
  margin: 16px 0;
}

.result-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid #eee;
  flex-wrap: wrap;
}

.result-name {
  flex: 1;
  min-width: 200px;
}

.result-time {
  color: #999;
  font-size: 12px;
}

.result-detail {
  width: 100%;
  padding: 16px;
  background: #fafafa;
  border-radius: 4px;
  margin-top: 12px;
}

.detail-section {
  margin-bottom: 16px;
}

.detail-section h6 {
  margin: 0 0 8px 0;
  color: #606266;
  font-size: 12px;
}

.code-block {
  background: #f5f7fa;
  padding: 12px;
  border-radius: 4px;
  font-size: 12px;
  max-height: 300px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

.code-block.error {
  color: #f56c6c;
}

.assertion-results {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.assertion-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px;
  border-radius: 4px;
  font-size: 13px;
}

.assertion-item.passed {
  background: #f0f9eb;
}

.assertion-item.failed {
  background: #fef0f0;
}

.assertion-type {
  font-weight: 500;
  color: #409eff;
}

.assertion-field {
  color: #303133;
}

.assertion-expected,
.assertion-actual {
  color: #606266;
  font-size: 12px;
}

.assertion-error {
  color: #f56c6c;
  font-size: 12px;
  margin-left: auto;
}

.ai-loading {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 10px;
  padding: 40px;
  color: #909399;
}

.ai-suggestions {
  max-height: 500px;
  overflow-y: auto;
}

.suggestion-item {
  padding: 12px;
  border: 1px solid #eee;
  border-radius: 4px;
  margin-bottom: 12px;
}

.suggestion-item h5 {
  margin: 0 0 8px 0;
  color: #409eff;
}

.suggestion-item .reasoning {
  color: #909399;
  font-size: 12px;
  font-style: italic;
}

.suggestion-item .assertions {
  margin-top: 8px;
}

.suggestion-item .suggestion-actions {
  margin-top: 8px;
  text-align: right;
}

.suggestion-pre {
  background: #f5f7fa;
  padding: 8px;
  border-radius: 4px;
  margin: 0;
  white-space: pre-wrap;
  font-size: 12px;
}

.ai-analysis {
  margin-top: 20px;
}

.assertions-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.assertion-item {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>

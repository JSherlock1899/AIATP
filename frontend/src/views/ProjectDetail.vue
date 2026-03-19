<template>
  <div class="project-detail-container">
    <div class="header">
      <el-button @click="goBack">返回</el-button>
      <h2>{{ project?.name }}</h2>
      <div class="header-actions">
        <el-tag :type="aiStatus.available ? 'success' : 'info'" size="small">
          AI: {{ aiStatus.available ? aiStatus.model || 'OpenAI' : '未配置' }}
        </el-tag>
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
            <el-icon><Magic /></el-icon> AI 生成测试用例
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
          <el-table-column label="操作" width="200">
            <template #default="{ row }">
              <el-button type="primary" size="small" @click="handleCreateTestCaseForEndpoint(row)">创建用例</el-button>
              <el-button type="warning" size="small" @click="handleAIEnhanceEndpoint(row)">
                <el-icon><Magic /></el-icon>
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="测试用例" name="testCases">
        <el-table :data="testCases" v-loading="loadingCases" stripe>
          <el-table-column prop="id" label="ID" width="80" />
          <el-table-column prop="name" label="用例名称" />
          <el-table-column prop="request_config.method" label="方法" width="100">
            <template #default="{ row }">
              <el-tag :type="getMethodType(row.request_config?.method)">{{ row.request_config?.method }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="request_config.url" label="URL" show-overflow-tooltip />
          <el-table-column label="操作" width="300">
            <template #default="{ row }">
              <el-button type="success" size="small" @click="handleExecute(row.id)">执行</el-button>
              <el-button type="primary" size="small" @click="handleEdit(row)">编辑</el-button>
              <el-button type="warning" size="small" @click="handleAIGenerateAssertions(row)">
                <el-icon><Magic /></el-icon> 智能断言
              </el-button>
              <el-button type="danger" size="small" @click="handleDeleteCase(row.id)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="测试结果" name="results">
        <div v-if="lastExecutionResult" class="execution-summary">
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
          <el-divider />
          <div v-for="result in lastExecutionResult.results" :key="result.id" class="result-item">
            <el-tag :type="result.status === 'passed' ? 'success' : 'danger'">
              {{ result.status === 'passed' ? '通过' : '失败' }}
            </el-tag>
            <span class="result-name">{{ getTestCaseName(result.test_case_id) }}</span>
            <span class="result-time">{{ result.response_time }}ms</span>
            <el-button
              v-if="result.status === 'failed'"
              type="warning"
              size="small"
              @click="handleAIAnalyzeFailure(result)"
            >
              <el-icon><Magic /></el-icon> AI 分析
            </el-button>
          </div>
          <div v-if="lastExecutionResult.failed > 0" class="ai-analysis">
            <el-divider />
            <h4>AI 批量分析</h4>
            <el-button type="warning" @click="handleAIAnalyzeAllFailures">
              <el-icon><Magic /></el-icon> 分析所有失败
            </el-button>
          </div>
        </div>
        <div v-else class="placeholder">暂无测试结果</div>
      </el-tab-pane>
    </el-tabs>

    <!-- AI 建议对话框 -->
    <el-dialog v-model="showAISuggestions" :title="aiDialogTitle" width="700px">
      <div v-if="aiLoading" class="ai-loading">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>AI 思考中...</span>
      </div>
      <div v-else-if="aiSuggestions.length > 0" class="ai-suggestions">
        <div v-for="(suggestion, index) in aiSuggestions" :key="index" class="suggestion-item">
          <h5>{{ suggestion.name || suggestion.type || `建议 ${index + 1}` }}</h5>
          <p v-if="suggestion.description">{{ suggestion.description }}</p>
          <p v-if="suggestion.reasoning" class="reasoning">{{ suggestion.reasoning }}</p>
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
              <el-icon><Magic /></el-icon> AI 智能添加断言
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
import { ref, reactive, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Magic, Loading } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'
import { projectsApi } from '@/api/projects'
import { testCasesApi, type TestCase, type CreateTestCaseRequest, type TestExecutionResponse } from '@/api/testCases'
import { aiApi, type AIStatus, type TestCaseSuggestion, type AssertionSuggestion, type AnomalyAnalysis } from '@/api/ai'

const router = useRouter()
const route = useRoute()
const projectId = Number(route.params.id)

interface ApiEndpoint {
  id: number
  path: string
  method: string
  summary: string
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
const lastExecutionResult = ref<TestExecutionResponse | null>(null)

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
    headers: {},
    timeout: 30
  },
  body: '',
  assertions: [] as AssertionSuggestion[],
  is_enabled: true
})

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
    // 从 API 文档获取端点
    // 暂时为空，实际应调用 projects/{id}/api-docs/{doc_id}/endpoints
    endpoints.value = []
  } catch (error) {
    // 暂时不显示错误
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
      summary: endpoint.summary
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
    const allSuggestions: any[] = []
    for (const endpoint of endpoints.value) {
      const suggestions = await aiApi.generateTestCases({
        path: endpoint.path,
        method: endpoint.method,
        summary: endpoint.summary
      }, 2)
      allSuggestions.push(...suggestions.map(s => ({ ...s, endpoint })))
    }
    aiSuggestions.value = allSuggestions
  } catch (error: any) {
    ElMessage.error(error.message || 'AI 生成失败')
  } finally {
    generatingTestCases.value = false
    aiLoading.value = false
  }
}

const handleAIEnhanceAssertions = async () => {
  if (!caseForm.body) {
    ElMessage.warning('请先填写请求体')
    return
  }

  aiLoading.value = true
  aiDialogTitle.value = 'AI 智能断言建议'
  aiSuggestions.value = []
  showAISuggestions.value = true

  try {
    // 模拟 API 响应进行断言生成
    const mockResponse = {
      status_code: 200,
      body: JSON.parse(caseForm.body),
      headers: { 'content-type': 'application/json' }
    }
    const suggestions = await aiApi.generateAssertions(mockResponse, {
      url: caseForm.request_config.url,
      method: caseForm.request_config.method
    })
    aiSuggestions.value = suggestions.map(s => ({ assertions: [s] }))
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

    // 显示综合分析
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

const handleEdit = (testCase: TestCase) => {
  editingId.value = testCase.id
  caseForm.endpoint_id = testCase.endpoint_id
  caseForm.name = testCase.name
  caseForm.description = testCase.description || ''
  caseForm.request_config = { ...testCase.request_config }
  caseForm.body = typeof testCase.request_config.body === 'string'
    ? testCase.request_config.body
    : JSON.stringify(testCase.request_config.body, null, 2)
  // 解析断言
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

  await caseFormRef.value.validate(async (valid) => {
    if (valid) {
      saving.value = true
      try {
        const data: CreateTestCaseRequest = {
          endpoint_id: caseForm.endpoint_id || 1, // 临时用 1
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
  caseForm.body = ''
  caseForm.assertions = []
}

const getTestCaseName = (testCaseId: number) => {
  const tc = testCases.value.find(t => t.id === testCaseId)
  return tc?.name || `用例 #${testCaseId}`
}

onMounted(() => {
  fetchProject()
  fetchTestCases()
  fetchAIStatus()
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

.result-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid #eee;
}

.result-name {
  flex: 1;
}

.result-time {
  color: #999;
  font-size: 12px;
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

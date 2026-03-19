<template>
  <div class="project-detail-container">
    <div class="header">
      <el-button @click="goBack">返回</el-button>
      <h2>{{ project?.name }}</h2>
      <el-button type="primary" @click="showAddDialog = true">添加测试用例</el-button>
    </div>

    <el-tabs v-model="activeTab" class="detail-tabs">
      <el-tab-pane label="API 文档" name="apis">
        <div class="api-docs">
          <p class="placeholder">API 文档功能开发中...</p>
        </div>
      </el-tab-pane>

      <el-tab-pane label="测试用例" name="testCases">
        <el-table :data="testCases" v-loading="loadingCases" stripe>
          <el-table-column prop="id" label="ID" width="80" />
          <el-table-column prop="name" label="用例名称" />
          <el-table-column prop="method" label="方法" width="100">
            <template #default="{ row }">
              <el-tag :type="getMethodType(row.method)">{{ row.method }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="path" label="路径" show-overflow-tooltip />
          <el-table-column prop="expected_status" label="期望状态" width="100" />
          <el-table-column label="操作" width="250">
            <template #default="{ row }">
              <el-button type="success" size="small" @click="handleExecute(row.id)">执行</el-button>
              <el-button type="primary" size="small" @click="handleEdit(row)">编辑</el-button>
              <el-button type="danger" size="small" @click="handleDeleteCase(row.id)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="测试结果" name="results">
        <div class="test-results">
          <p class="placeholder">暂无测试结果</p>
        </div>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="showAddDialog" title="添加测试用例" width="600px">
      <el-form :model="caseForm" :rules="caseRules" ref="caseFormRef" label-width="100px">
        <el-form-item label="用例名称" prop="name">
          <el-input v-model="caseForm.name" placeholder="请输入用例名称" />
        </el-form-item>
        <el-form-item label="请求方法" prop="method">
          <el-select v-model="caseForm.method" style="width: 100%">
            <el-option label="GET" value="GET" />
            <el-option label="POST" value="POST" />
            <el-option label="PUT" value="PUT" />
            <el-option label="DELETE" value="DELETE" />
            <el-option label="PATCH" value="PATCH" />
          </el-select>
        </el-form-item>
        <el-form-item label="请求路径" prop="path">
          <el-input v-model="caseForm.path" placeholder="如: /api/users" />
        </el-form-item>
        <el-form-item label="请求体" prop="body">
          <el-input v-model="caseForm.body" type="textarea" :rows="4" placeholder="JSON 格式" />
        </el-form-item>
        <el-form-item label="期望状态码" prop="expected_status">
          <el-input-number v-model="caseForm.expected_status" :min="100" :max="599" />
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
import type { FormInstance, FormRules } from 'element-plus'
import { projectsApi, type Project } from '@/api/projects'
import { testCasesApi, type TestCase, type CreateTestCaseRequest } from '@/api/testCases'

const router = useRouter()
const route = useRoute()
const projectId = Number(route.params.id)

const activeTab = ref('testCases')
const loadingCases = ref(false)
const saving = ref(false)
const showAddDialog = ref(false)
const project = ref<Project | null>(null)
const testCases = ref<TestCase[]>([])
const editingId = ref<number | null>(null)
const caseFormRef = ref<FormInstance>()

const caseForm = reactive<CreateTestCaseRequest>({
  project_id: projectId,
  name: '',
  method: 'GET',
  path: '/',
  headers: {},
  body: '',
  expected_status: 200
})

const caseRules: FormRules = {
  name: [{ required: true, message: '请输入用例名称', trigger: 'blur' }],
  method: [{ required: true, message: '请选择请求方法', trigger: 'change' }],
  path: [{ required: true, message: '请输入请求路径', trigger: 'blur' }]
}

const fetchProject = async () => {
  try {
    project.value = await projectsApi.getById(projectId)
  } catch (error) {
    ElMessage.error('获取项目信息失败')
  }
}

const fetchTestCases = async () => {
  loadingCases.value = true
  try {
    const response = await testCasesApi.list(projectId)
    testCases.value = response.data
  } catch (error) {
    ElMessage.error('获取测试用例失败')
  } finally {
    loadingCases.value = false
  }
}

const goBack = () => {
  router.push('/projects')
}

const getMethodType = (method: string) => {
  const types: Record<string, any> = {
    GET: '',
    POST: 'success',
    PUT: 'warning',
    DELETE: 'danger',
    PATCH: 'info'
  }
  return types[method] || ''
}

const handleExecute = async (testCaseId: number) => {
  try {
    await testCasesApi.execute(projectId, [testCaseId])
    ElMessage.success('执行成功')
    activeTab.value = 'results'
  } catch (error) {
    ElMessage.error('执行失败')
  }
}

const handleEdit = (testCase: TestCase) => {
  editingId.value = testCase.id
  caseForm.name = testCase.name
  caseForm.method = testCase.method
  caseForm.path = testCase.path
  caseForm.body = testCase.body
  caseForm.expected_status = testCase.expected_status
  showAddDialog.value = true
}

const handleDeleteCase = async (testCaseId: number) => {
  try {
    await ElMessageBox.confirm('确定要删除该测试用例吗？', '提示', {
      type: 'warning'
    })
    await testCasesApi.delete(projectId, testCaseId)
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
        if (editingId.value) {
          await testCasesApi.update(projectId, editingId.value, caseForm)
          ElMessage.success('更新成功')
        } else {
          await testCasesApi.create(projectId, caseForm)
          ElMessage.success('添加成功')
        }
        showAddDialog.value = false
        resetForm()
        fetchTestCases()
      } catch (error) {
        ElMessage.error('保存失败')
      } finally {
        saving.value = false
      }
    }
  })
}

const resetForm = () => {
  editingId.value = null
  caseForm.name = ''
  caseForm.method = 'GET'
  caseForm.path = '/'
  caseForm.body = ''
  caseForm.expected_status = 200
}

onMounted(() => {
  fetchProject()
  fetchTestCases()
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
</style>

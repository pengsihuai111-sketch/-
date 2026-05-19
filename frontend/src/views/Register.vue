<template>
  <div class="warm-login-page">
    <el-card class="warm-login-card" style="width: 460px">
      <div class="warm-login-brand">
        <h1 class="warm-login-title">智数<span class="warm-login-dot">·</span></h1>
        <p class="warm-login-subtitle">注册新账号</p>
      </div>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="0">
        <el-form-item prop="username">
          <el-input v-model="form.username" placeholder="用户名" size="large" :prefix-icon="User" />
        </el-form-item>
        <el-form-item prop="password">
          <el-input v-model="form.password" type="password" placeholder="密码（至少6位）" size="large" show-password :prefix-icon="Lock" />
        </el-form-item>
        <el-form-item prop="real_name">
          <el-input v-model="form.real_name" placeholder="真实姓名（选填）" size="large" :prefix-icon="EditPen" />
        </el-form-item>
        <el-form-item prop="grade_level">
          <el-select v-model="form.grade_level" placeholder="年级（选填）" size="large" style="width: 100%">
            <el-option label="四年级" value="四年级" />
            <el-option label="五年级" value="五年级" />
            <el-option label="六年级" value="六年级" />
            <el-option label="初一" value="初一" />
          </el-select>
        </el-form-item>
        <el-form-item prop="email">
          <el-input v-model="form.email" placeholder="邮箱（选填）" size="large" :prefix-icon="Message" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" size="large" class="warm-btn-block" @click="handleRegister" :loading="loading">注册</el-button>
        </el-form-item>
      </el-form>
      <div class="warm-login-footer">
        <router-link to="/login" class="warm-link">已有账号？去登录</router-link>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { User, Lock, EditPen, Message } from '@element-plus/icons-vue'
import { register } from '../api/auth'
import { setToken, setUser } from '../utils/storage'
import { ElMessage } from 'element-plus'

const router = useRouter()
const formRef = ref(null)
const loading = ref(false)

const form = reactive({
  username: '',
  password: '',
  real_name: '',
  grade_level: '',
  email: '',
})

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少6位', trigger: 'blur' },
  ],
}

async function handleRegister() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    const res = await register(form)
    setToken(res.access_token)
    setUser(res.user)
    ElMessage.success('注册成功')
    router.push('/dashboard')
  } finally {
    loading.value = false
  }
}
</script>

<style>
.warm-login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #064E3B 0%, #059669 50%, #6EE7B7 100%);
}

.warm-login-card {
  padding: 10px 20px 20px;
  border-radius: 14px !important;
}

.warm-login-brand {
  text-align: center;
  margin-bottom: 28px;
}

.warm-login-title {
  font-size: 32px;
  font-weight: 700;
  color: var(--text-primary, #141413);
  margin: 0;
  letter-spacing: 2px;
}

.warm-login-dot {
  color: var(--brand-primary, #10B981);
  margin: 0 2px;
}

.warm-login-subtitle {
  font-size: 14px;
  color: var(--text-secondary, #6c6a64);
  margin: 6px 0 0 0;
  letter-spacing: 1px;
}

.warm-btn-block {
  width: 100%;
}

.warm-login-footer {
  text-align: center;
  margin-top: 4px;
}

.warm-link {
  color: var(--brand-primary, #10B981);
  text-decoration: none;
  font-size: 14px;
}

.warm-link:hover {
  color: var(--brand-primary-hover, #059669);
  text-decoration: underline;
}
</style>

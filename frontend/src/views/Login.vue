<template>
  <div class="warm-login-page">
    <el-card class="warm-login-card">
      <div class="warm-login-brand">
        <h1 class="warm-login-title">智数<span class="warm-login-dot">·</span></h1>
        <p class="warm-login-subtitle">小升初学情诊断系统</p>
      </div>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="0">
        <el-form-item prop="username">
          <el-input v-model="form.username" placeholder="用户名" size="large" :prefix-icon="User" />
        </el-form-item>
        <el-form-item prop="password">
          <el-input v-model="form.password" type="password" placeholder="密码" size="large" show-password :prefix-icon="Lock" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" size="large" class="warm-btn-block" @click="handleLogin" :loading="loading">登录</el-button>
        </el-form-item>
      </el-form>
      <div class="warm-login-footer">
        <router-link to="/register" class="warm-link">还没有账号？立即注册</router-link>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { User, Lock } from '@element-plus/icons-vue'
import { login } from '../api/auth'
import { setToken, setUser } from '../utils/storage'
import { ElMessage } from 'element-plus'

const router = useRouter()
const formRef = ref(null)
const loading = ref(false)

const form = reactive({
  username: '',
  password: '',
})

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function handleLogin() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    const res = await login(form)
    setToken(res.access_token)
    setUser(res.user)
    ElMessage.success('登录成功')
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
  width: 420px;
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

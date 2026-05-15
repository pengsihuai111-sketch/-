<template>
  <el-container style="height: 100vh">
    <el-aside width="220px" class="warm-sidebar">
      <div class="warm-sidebar-header">
        <div class="warm-logo">
          <span class="warm-logo-name">智数</span>
          <span class="warm-logo-dot">·</span>
          <span class="warm-logo-sub">小升初学情诊断</span>
        </div>
      </div>
      <el-menu
        :default-active="route.path"
        router
        class="warm-menu"
      >
        <el-menu-item index="/dashboard">
          <el-icon><HomeFilled /></el-icon>
          <span>首页</span>
        </el-menu-item>
        <el-menu-item index="/questions">
          <el-icon><Reading /></el-icon>
          <span>题库浏览</span>
        </el-menu-item>
        <el-menu-item index="/question-input">
          <el-icon><Edit /></el-icon>
          <span>录入题目</span>
        </el-menu-item>
        <el-menu-item index="/wrong-questions">
          <el-icon><WarningFilled /></el-icon>
          <span>错题管理</span>
        </el-menu-item>
        <el-menu-item index="/practice">
          <el-icon><EditPen /></el-icon>
          <span>练习单</span>
        </el-menu-item>
        <el-menu-item index="/diagnosis">
          <el-icon><DataAnalysis /></el-icon>
          <span>学情诊断</span>
        </el-menu-item>
        <el-menu-item index="/member">
          <el-icon><Coin /></el-icon>
          <span>会员中心</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="warm-header">
        <span class="warm-header-title">{{ route.meta.title || '智数·学情诊断' }}</span>
        <div class="warm-header-right">
          <el-tag v-if="user" class="warm-member-tag" size="small">{{ user.member_type === 'free' ? '免费用户' : user.member_type === 'basic' ? '基础会员' : '高级会员' }}</el-tag>
          <el-button class="warm-logout-btn" link size="small" @click="handleLogout">退出登录</el-button>
        </div>
      </el-header>
      <el-main class="warm-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { useRoute } from 'vue-router'
import { useRouter } from 'vue-router'
import { getUser, removeToken } from '../utils/storage'
import { ref } from 'vue'

const route = useRoute()
const router = useRouter()
const user = ref(getUser())

function handleLogout() {
  removeToken()
  router.push('/login')
}
</script>

<style>
/* === Sidebar (作业帮风格 绿白配色) === */
.warm-sidebar {
  background: var(--sidebar-bg, #0F172A);
  display: flex;
  flex-direction: column;
}

.warm-sidebar-header {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-bottom: 1px solid var(--sidebar-border);
  padding: 0 16px;
}

.warm-logo {
  display: flex;
  align-items: baseline;
  gap: 2px;
}

.warm-logo-name {
  color: #FFFFFF;
  font-size: 20px;
  font-weight: 700;
  letter-spacing: 1px;
}

.warm-logo-dot {
  color: var(--brand-primary, #10B981);
  font-size: 22px;
  font-weight: 700;
  margin: 0 1px;
}

.warm-logo-sub {
  color: #CBD5E1;
  font-size: 13px;
  font-weight: 500;
}

.warm-sidebar .el-menu {
  background: transparent !important;
  border: none !important;
}

.warm-sidebar .el-menu-item {
  color: var(--sidebar-text, #E2E8F0) !important;
  background: transparent !important;
  border-radius: 8px;
  margin: 2px 8px;
  font-size: 14px;
  height: 42px;
  line-height: 42px;
}

.warm-sidebar .el-menu-item:hover {
  background: rgba(255, 255, 255, 0.08) !important;
  color: #FFFFFF !important;
}

.warm-sidebar .el-menu-item.is-active {
  color: #FFFFFF !important;
  background: var(--brand-primary, #10B981) !important;
}

.warm-sidebar .el-menu-item .el-icon {
  color: inherit !important;
}

/* === Header === */
.warm-header {
  height: 52px !important;
  line-height: 52px !important;
  background: var(--surface-card, #FFFFFF) !important;
  border-bottom: 1px solid var(--border-color, #E2E8F0);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 24px !important;
}

.warm-header-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary, #0F172A);
}

.warm-header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.warm-member-tag {
  border: none !important;
  background: var(--brand-primary-light, #D1FAE5) !important;
  color: var(--brand-primary, #10B981) !important;
  font-weight: 500;
}

.warm-logout-btn {
  color: var(--text-muted, #94A3B8) !important;
  font-size: 13px !important;
}

.warm-logout-btn:hover {
  color: var(--color-danger, #EF4444) !important;
}

/* === Main Content === */
.warm-main {
  background: var(--canvas, #F8FAFC) !important;
  padding: 20px !important;
  overflow-y: auto;
}

/* === Global Element Plus Overrides (绿色主题) === */
.el-card {
  border: 1px solid var(--border-color, #E2E8F0) !important;
  border-radius: 10px !important;
  background: var(--surface-card, #FFFFFF) !important;
  transition: box-shadow 0.2s ease;
}

.el-card:hover {
  box-shadow: 0 2px 12px rgba(0,0,0,0.04);
}

.el-card__header {
  padding: 14px 20px !important;
  border-bottom: 1px solid var(--border-soft, #F1F5F9) !important;
}

.el-button--primary {
  --el-button-bg-color: var(--brand-primary, #10B981) !important;
  --el-button-border-color: var(--brand-primary, #10B981) !important;
  --el-button-hover-bg-color: var(--brand-primary-hover, #059669) !important;
  --el-button-hover-border-color: var(--brand-primary-hover, #059669) !important;
  --el-button-active-bg-color: var(--brand-primary-active, #047857) !important;
}

.el-button--primary.is-link,
.el-button--primary:focus {
  color: var(--brand-primary, #10B981) !important;
}

.el-tabs__item.is-active {
  color: var(--brand-primary, #10B981) !important;
}

.el-tabs__active-bar {
  background-color: var(--brand-primary, #10B981) !important;
}

.el-tag--success {
  --el-tag-bg-color: #D1FAE5 !important;
  --el-tag-text-color: #047857 !important;
  --el-tag-border-color: #A7F3D0 !important;
}

.el-tag--danger {
  --el-tag-bg-color: #FEE2E2 !important;
  --el-tag-text-color: #DC2626 !important;
  --el-tag-border-color: #FCA5A5 !important;
}

.el-table__header th {
  background: var(--surface-soft, #F1F5F9) !important;
  color: var(--text-body, #334155) !important;
  font-weight: 600 !important;
}

.el-table--striped .el-table__body tr.el-table__row--striped td {
  background: var(--canvas, #F8FAFC) !important;
}

.el-pagination.is-background .el-pager li.is-active {
  background: var(--brand-primary, #10B981) !important;
}

.el-progress-bar__inner {
  background: var(--brand-primary, #10B981) !important;
}

.el-empty__description p {
  color: var(--text-muted, #94A3B8) !important;
}

.el-alert--info {
  --el-alert-bg-color: var(--brand-primary-lighter, #ECFDF5) !important;
  --el-alert-title-color: var(--text-body, #334155) !important;
}

.el-form-item__label {
  color: var(--text-body, #334155) !important;
  font-weight: 500 !important;
}

.el-radio__input.is-checked + .el-radio__label {
  color: var(--brand-primary, #10B981) !important;
}

.el-radio__input.is-checked .el-radio__inner {
  border-color: var(--brand-primary, #10B981) !important;
  background: var(--brand-primary, #10B981) !important;
}

.el-checkbox__input.is-checked + .el-checkbox__label {
  color: var(--brand-primary, #10B981) !important;
}

.el-checkbox__input.is-checked .el-checkbox__inner {
  background: var(--brand-primary, #10B981) !important;
  border-color: var(--brand-primary, #10B981) !important;
}

.el-select .el-input.is-focus .el-input__wrapper {
  box-shadow: 0 0 0 1px var(--brand-primary, #10B981) inset !important;
}

.el-date-table td.today {
  color: var(--brand-primary, #10B981) !important;
}

.el-date-table td.current:not(.disabled) span {
  background: var(--brand-primary, #10B981) !important;
}

.el-upload-dragger {
  border: 2px dashed var(--border-color, #E2E8F0) !important;
  border-radius: 10px !important;
}

.el-upload-dragger:hover {
  border-color: var(--brand-primary, #10B981) !important;
}

.el-dialog__header {
  border-bottom: 1px solid var(--border-soft, #F1F5F9) !important;
  padding: 16px 20px !important;
  margin-right: 0 !important;
}

::selection {
  background: var(--brand-primary-light, #D1FAE5);
  color: var(--text-primary, #0F172A);
}
</style>

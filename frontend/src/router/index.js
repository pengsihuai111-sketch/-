import { createRouter, createWebHistory } from 'vue-router'
import Layout from '../components/Layout.vue'
import Login from '../views/Login.vue'
import Register from '../views/Register.vue'
import Dashboard from '../views/Dashboard.vue'
import Questions from '../views/Questions.vue'
import QuestionInput from '../views/QuestionInput.vue'
import WrongQuestions from '../views/WrongQuestions.vue'
import Practice from '../views/Practice.vue'
import Diagnosis from '../views/Diagnosis.vue'
import Member from '../views/Member.vue'

const routes = [
  { path: '/login', name: 'Login', component: Login },
  { path: '/register', name: 'Register', component: Register },
  {
    path: '/',
    component: Layout,
    redirect: '/dashboard',
    children: [
      { path: 'dashboard', name: 'Dashboard', component: Dashboard, meta: { title: '首页' } },
      { path: 'questions', name: 'Questions', component: Questions, meta: { title: '题库浏览' } },
      { path: 'question-input', name: 'QuestionInput', component: QuestionInput, meta: { title: '录入题目' } },
      { path: 'wrong-questions', name: 'WrongQuestions', component: WrongQuestions, meta: { title: '错题管理' } },
      { path: 'practice', name: 'Practice', component: Practice, meta: { title: '练习单' } },
      { path: 'diagnosis', name: 'Diagnosis', component: Diagnosis, meta: { title: '学情诊断' } },
      { path: 'member', name: 'Member', component: Member, meta: { title: '会员中心' } },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 路由守卫
router.beforeEach((to, _, next) => {
  const token = localStorage.getItem('token')
  if (to.path !== '/login' && to.path !== '/register' && !token) {
    next('/login')
  } else {
    next()
  }
})

export default router

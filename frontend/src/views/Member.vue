<template>
  <div>
    <!-- 当前会员信息 -->
    <el-card shadow="hover" style="margin-bottom: 20px">
      <template #header><span style="font-weight: bold">我的会员</span></template>
      <div v-if="memberInfo">
        <div style="display: flex; align-items: center; gap: 20px">
          <div>
            <el-tag :type="memberInfo.member_type === 'premium' ? 'danger' : memberInfo.member_type === 'basic' ? 'warning' : 'info'" size="large" style="font-size: 18px; padding: 6px 20px">
              {{ memberInfo.member_type === 'free' ? '免费用户' : memberInfo.member_type === 'basic' ? '基础会员' : '高级会员' }}
            </el-tag>
          </div>
          <div v-if="memberInfo.member_type !== 'free'">
            <span v-if="memberInfo.is_expired" style="color: #f56c6c">已过期</span>
            <span v-else>剩余 <strong style="color: #409eff">{{ memberInfo.remaining_days }}</strong> 天</span>
            <span style="margin-left: 12px; color: #999">到期：{{ memberInfo.member_expire_date }}</span>
          </div>
          <div v-else style="color: #999">开通会员享受全部功能</div>
        </div>
      </div>
    </el-card>

    <!-- 会员套餐 -->
    <el-row :gutter="20">
      <el-col :span="8" v-for="plan in plans" :key="plan.type">
        <el-card shadow="hover" :style="plan.highlight ? 'border: 2px solid #409eff' : ''">
          <div style="text-align: center; padding: 20px">
            <div style="font-size: 20px; font-weight: bold; margin-bottom: 10px">{{ plan.name }}</div>
            <div style="font-size: 36px; color: #409eff; font-weight: bold; margin: 20px 0">
              ¥{{ plan.monthly }}
              <span style="font-size: 14px; color: #999">/月</span>
            </div>
            <div v-if="plan.annual" style="color: #e6a23c; margin-bottom: 16px">年付 ¥{{ plan.annual }}（省¥{{ plan.saved }}）</div>
            <el-divider />
            <div v-for="feature in plan.features" :key="feature" style="margin-bottom: 8px; color: #666">{{ feature }}</div>
            <el-button
              :type="plan.type === 'premium' ? 'danger' : 'primary'"
              style="width: 100%; margin-top: 16px"
              @click="showBuy(plan)"
              :disabled="memberInfo?.member_type === plan.type && !memberInfo?.is_expired"
            >
              {{ memberInfo?.member_type === plan.type && !memberInfo?.is_expired ? '当前会员' : '立即开通' }}
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 订单历史 -->
    <el-card shadow="hover" style="margin-top: 20px">
      <template #header><span style="font-weight: bold">订单记录</span></template>
      <el-table :data="orders" stripe style="width: 100%">
        <el-table-column prop="order_no" label="订单号" width="200" />
        <el-table-column label="类型" width="100">
          <template #default="{ row }">{{ row.member_type === 'basic' ? '基础会员' : '高级会员' }}</template>
        </el-table-column>
        <el-table-column prop="duration_months" label="时长(月)" width="80" />
        <el-table-column prop="amount" label="金额" width="80">
          <template #default="{ row }">¥{{ row.amount }}</template>
        </el-table-column>
        <el-table-column label="支付方式" width="100">
          <template #default="{ row }">{{ row.payment_method === 'wechat' ? '微信' : '支付宝' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.payment_status === 'paid' ? 'success' : 'info'">{{ row.payment_status === 'paid' ? '已支付' : '待支付' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_date" label="时间" width="180" />
      </el-table>
      <el-empty v-if="!orders.length" description="暂无订单" />
    </el-card>

    <!-- 购买对话框 -->
    <el-dialog v-model="buyVisible" title="选择套餐" width="420px">
      <div style="text-align: center; padding: 10px">
        <div style="font-size: 18px; font-weight: bold">{{ selectedPlan?.name }}</div>
        <el-radio-group v-model="selectedDuration" style="margin-top: 20px">
          <el-radio-button :value="1">1个月</el-radio-button>
          <el-radio-button :value="3">3个月</el-radio-button>
          <el-radio-button :value="6">6个月</el-radio-button>
          <el-radio-button :value="12">12个月</el-radio-button>
        </el-radio-group>
        <div style="font-size: 28px; color: #409eff; margin: 20px 0">
          ¥{{ selectedPlan?.prices?.[selectedDuration] || 0 }}
        </div>
        <div style="display: flex; gap: 12px; justify-content: center">
          <el-radio-group v-model="paymentMethod">
            <el-radio-button value="wechat">微信支付</el-radio-button>
            <el-radio-button value="alipay">支付宝</el-radio-button>
          </el-radio-group>
        </div>
      </div>
      <template #footer>
        <el-button @click="buyVisible = false">取消</el-button>
        <el-button type="primary" @click="handleBuy" :loading="buyLoading">确认支付 ¥{{ selectedPlan?.prices?.[selectedDuration] || 0 }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { getMemberInfo, listOrders, createOrder, payOrder, getPrices } from '../api/practice'
import { ElMessage } from 'element-plus'

const memberInfo = ref(null)
const orders = ref([])
const buyVisible = ref(false)
const buyLoading = ref(false)
const selectedPlan = ref(null)
const selectedDuration = ref(1)
const paymentMethod = ref('wechat')

const plans = [
  { type: 'free', name: '免费版', monthly: 0, features: ['每月10道练习', '基础错题管理', '简单学情报告'], highlight: false },
  { type: 'basic', name: '基础会员', monthly: 99, annual: 899, saved: 289, features: ['无限练习', '完整错题管理', '智能练习单生成', '详细学情分析'], highlight: false },
  { type: 'premium', name: '高级会员', monthly: 199, annual: 1799, saved: 589, features: ['全部基础会员功能', 'AI智能诊断', '个性化学习路径', '优先客服支持'], highlight: true },
]

async function loadData() {
  try {
    memberInfo.value = await getMemberInfo()
    const orderRes = await listOrders()
    orders.value = orderRes.orders || []
  } catch (e) { /* ignore */ }
}

async function showBuy(plan) {
  if (plan.type === 'free') {
    ElMessage.info('免费版无需开通')
    return
  }
  try {
    const prices = await getPrices()
    selectedPlan.value = { ...plan, prices: prices[plan.type] }
    selectedDuration.value = 1
    paymentMethod.value = 'wechat'
    buyVisible.value = true
  } catch (e) { /* ignore */ }
}

async function handleBuy() {
  buyLoading.value = true
  try {
    const order = await createOrder({
      member_type: selectedPlan.value.type,
      duration_months: selectedDuration.value,
      payment_method: paymentMethod.value,
    })
    // 模拟支付
    await payOrder(order.order_id)
    ElMessage.success('支付成功！会员已开通')
    buyVisible.value = false
    await loadData()
  } finally {
    buyLoading.value = false
  }
}

onMounted(loadData)
</script>

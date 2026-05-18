---
name: design-md
description: 从 awesome-design-md 合集（73 个知名网站设计规范）中选取风格，将 DESIGN.md 复制到项目根目录，指导 AI 生成风格一致的 UI。当用户提到"设计"、"风格"、"样式"、"DESIGN.md"、"UI设计"、"主题"时触发。
---

# DESIGN.md 设计风格选择器

从 70+ 知名网站的 DESIGN.md 设计规范中选择一个风格，应用到当前项目。

## 可用设计风格

### AI & LLM 平台
| 风格 | 说明 |
|------|------|
| `claude` | 温暖陶土色，简洁编辑风格 |
| `cohere` | 企业 AI 平台，鲜艳渐变色 |
| `elevenlabs` | 暗色影院风，音频波形美学 |
| `minimax` | 大胆暗色界面，霓虹强调 |
| `mistral.ai` | 法式极简，紫色调 |
| `ollama` | 终端优先，单色极简 |
| `opencode.ai` | 开发者暗色主题 |
| `replicate` | 干净白色画布，代码优先 |
| `runwayml` | 暗色影院风，纸白阅读区 |
| `together.ai` | 技术蓝图风格 |
| `voltagent` | 虚空黑画布，翠绿强调，终端原生 |
| `x.ai` | 极简单色，未来感 |

### 开发者工具 & IDE
| 风格 | 说明 |
|------|------|
| `cursor` | AI 代码编辑器，暗色渐变 |
| `expo` | React Native，暗色主题 |
| `lovable` | 友好渐变色，开发美学 |
| `raycast` | 暗色铬合金，渐变强调 |
| `vercel` | 黑白极简，Geist 字体 |
| `warp` | 现代终端，暗色 IDE |

### 数据库 & DevOps
| 风格 | 说明 |
|------|------|
| `clickhouse` | 黄色强调，技术文档风格 |
| `mongodb` | 绿色叶子品牌 |
| `posthog` | 暗色 UI，产品分析 |
| `sentry` | 暗色仪表盘，粉紫强调 |
| `supabase` | 暗色翠绿主题，代码优先 |

### 生产力 & SaaS
| 风格 | 说明 |
|------|------|
| `linear.app` | 超极简，紫色强调 |
| `notion` | 暖色调极简 |
| `mintlify` | 干净绿色强调，文档优化 |
| `resend` | 极简暗色，等宽强调 |
| `intercom` | 友好蓝色，对话式 UI |

### 设计 & 创意工具
| 风格 | 说明 |
|------|------|
| `figma` | 多彩活力 |
| `framer` | 大胆黑蓝，动感优先 |
| `miro` | 亮黄色强调 |
| `webflow` | 蓝色强调，精致营销风 |

### 金融 & 支付
| 风格 | 说明 |
|------|------|
| `stripe` | 紫色渐变，优雅极简 |
| `coinbase` | 干净蓝色，信任感 |
| `revolut` | 暗色界面，渐变卡片 |
| `wise` | 亮绿强调 |

### 电商 & 零售
| 风格 | 说明 |
|------|------|
| `shopify` | 暗色影院风，霓虹绿 |
| `nike` | 单色 UI，全幅摄影 |
| `airbnb` | 暖珊瑚色，圆角 UI |

### 媒体 & 消费科技
| 风格 | 说明 |
|------|------|
| `apple` | 高级白空间，SF Pro |
| `spotify` | 亮绿暗色，大胆字体 |
| `nvidia` | 绿黑能量感 |
| `tesla` | 极致减法，全幅视口 |
| `spacex` | 黑白色，全幅图片 |

### 汽车
| 风格 | 说明 |
|------|------|
| `ferrari` | 黑白明暗对比，法拉利红 |
| `porsche` | 德式精准，暗色高级感 |
| `bmw` | 暗色高级表面 |

## 用法

用户说"我想用 XXX 的设计风格"时：

1. **复制 DESIGN.md 到项目根目录**
   ```bash
   cp "d:\project\题库管理\awesome-design-md\design-md\{style-name}\DESIGN.md" "d:\project\题库管理\math_bank_v4\DESIGN.md"
   ```

2. **告知 AI 助手**：告诉 AI "按 DESIGN.md 的设计风格开发页面"

## 工作流程

1. 询问用户想用哪个网站的设计风格（如不确定，推荐适合其项目类型的风格）
2. 将对应 `DESIGN.md` 复制到项目根目录
3. 告知用户：AI 助手（Claude Code）读取到根目录的 `DESIGN.md` 后，后续生成的 UI 将自动遵循该设计规范

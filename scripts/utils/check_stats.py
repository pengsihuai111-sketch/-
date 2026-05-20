# -*- coding: utf-8 -*-
"""检查题库统计信息"""
import json
import os

base = 'math_bank_v3'

# 1. 主索引统计
with open(os.path.join(base, 'index', 'master_index.json'), 'r', encoding='utf-8') as f:
    master = json.load(f)
total = len(master['questions'])
print('=== 主索引统计 ===')
print(f'总题数: {total}')
print(f'版本: {master["_meta"]["version"]}')
print(f'最后更新: {master["_meta"]["last_updated"]}')
print(f'学校数: {master["_meta"]["total_schools"]}')
print(f'套卷数: {master["_meta"]["total_sets"]}')

# 2. 各分片统计
print('\n=== 各分片题量 ===')
shard_dir = os.path.join(base, 'questions')
total_shard = 0
for fname in sorted(os.listdir(shard_dir)):
    if fname.endswith('.json'):
        with open(os.path.join(shard_dir, fname), 'r', encoding='utf-8') as f:
            data = json.load(f)
        cnt = len(data['questions'])
        total_shard += cnt
        print(f'  {fname.replace(".json","")}: {cnt}题')
print(f'  分片合计: {total_shard}题')

# 3. 难度分布
print('\n=== 难度分布 ===')
diff_dist = {}
for q in master['questions']:
    d = q.get('difficulty', '未知')
    diff_dist[d] = diff_dist.get(d, 0) + 1
for d, c in sorted(diff_dist.items()):
    print(f'  {d}: {c}题')

# 4. 题型分布
print('\n=== 题型分布 ===')
type_dist = {}
for q in master['questions']:
    t = q.get('question_type', '未知')
    type_dist[t] = type_dist.get(t, 0) + 1
for t, c in sorted(type_dist.items()):
    print(f'  {t}: {c}题')

# 5. 答案状态
print('\n=== 答案验证状态 ===')
ans_dist = {}
for q in master['questions']:
    a = q.get('answer_status', 'unknown')
    ans_dist[a] = ans_dist.get(a, 0) + 1
for a, c in sorted(ans_dist.items()):
    print(f'  {a}: {c}题')

# 6. 带图题
img_count = sum(1 for q in master['questions'] if q.get('has_image'))
print(f'\n带图题: {img_count}题')

# 7. 知识点分布
print('\n=== 知识点分布（TOP 15） ===')
kp_dist = {}
for q in master['questions']:
    kp = q.get('knowledge_point', '未知')
    kp_dist[kp] = kp_dist.get(kp, 0) + 1
for kp, c in sorted(kp_dist.items(), key=lambda x: -x[1])[:15]:
    print(f'  {kp}: {c}题')
print(f'  知识点总数: {len(kp_dist)}个')

# 8. 学校分布
print('\n=== 学校分布 ===')
school_dist = {}
for q in master['questions']:
    s = q.get('source_school_full', '未知')
    school_dist[s] = school_dist.get(s, 0) + 1
for s, c in sorted(school_dist.items(), key=lambda x: -x[1]):
    print(f'  {s}: {c}题')

# 9. 图片文件统计
img_dir = os.path.join(base, 'image')
img_files = [f for f in os.listdir(img_dir) if f.endswith(('.png', '.jpg', '.jpeg'))]
print(f'\n=== 图片文件 ===')
print(f'图片总数: {len(img_files)}张')

# 10. 错题统计
print('\n=== 错题统计 ===')
with open(os.path.join(base, 'wrong_questions', 'wrong_question_bank.json'), 'r', encoding='utf-8') as f:
    wq = json.load(f)
print(f'错题总数: {len(wq["wrong_questions"])}道')

# 11. 学生状态
print('\n=== 学生状态 ===')
with open(os.path.join(base, 'student', '冯紫桐_学习状态.json'), 'r', encoding='utf-8') as f:
    stu = json.load(f)
km = stu.get('knowledge_mastery', {})
weak = [kp for kp, v in km.items() if isinstance(v, dict) and v.get('mastery_rate', 1) < 0.6]
print(f'知识点总数: {len(km)}个')
print(f'薄弱知识点（掌握度<60%）: {len(weak)}个')
for kp in sorted(weak)[:10]:
    rate = km[kp]['mastery_rate'] * 100
    print(f'  {kp}: {rate:.1f}%')

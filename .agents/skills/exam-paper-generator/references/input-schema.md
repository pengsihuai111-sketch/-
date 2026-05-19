# Input JSON schema

Create a UTF-8 JSON file with this shape:

```json
{
  "title": "期中考试试卷",
  "subtitle": "数学 七年级",
  "metadata": {
    "duration": "90分钟",
    "total_points": "100分",
    "date": "2026-05-11"
  },
  "instructions": [
    "请在答题区域内作答。",
    "考试结束后只提交答题纸。"
  ],
  "sections": [
    {
      "title": "一、选择题",
      "questions": [
        {
          "number": "1",
          "type": "single_choice",
          "prompt": "下列计算正确的是（  ）。",
          "options": ["A. 2+3=6", "B. 4-1=3", "C. 5×0=5", "D. 8÷2=2"],
          "points": "3分",
          "answer": "B",
          "explanation": "4-1=3。",
          "answer_space_lines": 0
        }
      ]
    },
    {
      "title": "二、解答题",
      "questions": [
        {
          "prompt": "解方程：2x+5=17。",
          "points": "8分",
          "answer": "x=6",
          "explanation": "2x=12，所以x=6。",
          "answer_space_lines": 4
        }
      ]
    }
  ]
}
```

## Field notes

- `title`: required.
- `subtitle`, `metadata`, `instructions`, and `sections[].title`: optional but recommended.
- `sections`: required; each section contains `questions`.
- `questions[].number`: optional. If absent, the script numbers questions continuously.
- `questions[].prompt`: required.
- `questions[].options`: optional list of strings.
- `questions[].subquestions`: optional list of strings for grouped prompts.
- `questions[].points`: optional string displayed beside the question.
- `questions[].answer`: optional string used only in `answers.pdf`.
- `questions[].explanation`: optional string used only in `answers.pdf`.
- `questions[].answer_space_lines`: optional integer; adds blank writing lines after the question in `exam.pdf`.

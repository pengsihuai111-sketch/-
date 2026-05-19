# Tesseract OCR 安装指南（Windows）

## 为什么需要 Tesseract？

当 PDF 是扫描件（没有文本层）时，系统需要使用 OCR（光学字符识别）来提取文字。Tesseract 是一个开源的 OCR 引擎，支持中英文识别。

## 安装步骤

### 1. 下载 Tesseract 安装程序

访问官方下载页面：
https://github.com/UB-Mannheim/tesseract/wiki

下载最新版本的 Windows 安装程序（推荐 64-bit）：
- 文件名类似：`tesseract-ocr-w64-setup-5.x.x.xxxxxxxx.exe`

### 2. 安装 Tesseract

1. 运行下载的安装程序
2. **重要**：在安装过程中，确保选择安装**中文语言包**
   - 在 "Choose Components" 步骤中
   - 展开 "Additional language data (download)"
   - 勾选 "Chinese - Simplified" (chi_sim)
   - 勾选 "Chinese - Traditional" (chi_tra) - 可选
3. 建议安装到默认路径：`C:\Program Files\Tesseract-OCR`
4. 完成安装

### 3. 验证安装

打开 PowerShell 或命令提示符，运行：

```powershell
& "C:\Program Files\Tesseract-OCR\tesseract.exe" --version
```

应该看到类似输出：
```
tesseract 5.x.x
 leptonica-1.x.x
  ...
```

### 4. 验证中文语言包

运行：

```powershell
& "C:\Program Files\Tesseract-OCR\tesseract.exe" --list-langs
```

应该看到输出中包含：
```
List of available languages (3):
chi_sim
chi_tra
eng
```

### 5. 重启后端服务

安装完成后，重启后端服务以使配置生效：

```powershell
# 停止当前运行的后端服务（如果有）
# 然后重新启动
cd D:\project\题库管理\math_bank_v4\backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 故障排除

### 问题 1：找不到 tesseract 命令

**原因**：Tesseract 未安装或安装路径不是默认路径

**解决方法**：
1. 确认 Tesseract 已安装
2. 如果安装在非默认路径，需要修改代码中的路径配置
3. 编辑 `app/utils/pdf_to_markdown.py`，找到这一行：
   ```python
   tesseract_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
   ```
   修改为你的实际安装路径

### 问题 2：OCR 识别不出中文

**原因**：缺少中文语言包

**解决方法**：
1. 手动下载中文语言包：
   - 访问：https://github.com/tesseract-ocr/tessdata
   - 下载 `chi_sim.traineddata`（简体中文）
2. 将下载的文件复制到 Tesseract 的 tessdata 目录：
   ```
   C:\Program Files\Tesseract-OCR\tessdata\
   ```
3. 重启后端服务

### 问题 3：OCR 识别准确率低

**建议**：
1. 确保 PDF 扫描质量足够高（至少 300 DPI）
2. 图片清晰，文字不模糊
3. 如果是手写体或特殊字体，OCR 准确率会降低

## 测试 OCR 功能

安装完成后，可以使用测试脚本验证：

```powershell
cd D:\project\题库管理\math_bank_v4\backend
python test_pdf_recognition.py
```

上传一个扫描件 PDF，查看后端日志：
- 如果看到 "Used OCR to extract text from scanned PDF"，说明 OCR 正常工作
- 如果看到错误信息，参考上面的故障排除部分

## 性能说明

- OCR 处理速度比直接提取文本慢（每页约 2-5 秒）
- 系统会自动判断：有文本层的 PDF 直接提取，扫描件才使用 OCR
- 建议上传有文本层的 PDF 以获得最佳性能和准确率

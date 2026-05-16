# 📈 AI 股票分析仪 (Stock Analyzer AI)

> 全栈 AI 股票分析应用，使用 Google Gemini 实时分析股票数据，严格返回结构化 JSON 结果。

---

## 1. 在线访问 URL

| 服务 | URL | 说明 |
|------|-----|------|
| 🖥️ **前端应用** | [https://stock-analyzer-ui-9l4l.onrender.com](https://stock-analyzer-ui-9l4l.onrender.com) | 用户界面，输入股票代码进行 AI 分析 |
| ⚙️ **后端 API** | [https://stock-analyzer-ai-fikt.onrender.com](https://stock-analyzer-ai-fikt.onrender.com) | FastAPI 后端服务 |
| 📊 **API 健康检查** | [https://stock-analyzer-ai-fikt.onrender.com/health](https://stock-analyzer-ai-fikt.onrender.com/health) | 检查服务和数据库连接状态 |
| 📋 **历史记录 API** | [https://stock-analyzer-ai-fikt.onrender.com/history](https://stock-analyzer-ai-fikt.onrender.com/history) | 查看最近的分析记录 |
| 🗄️ **GitHub 仓库** | [https://github.com/kyirejson/stock-analyzer-ai](https://github.com/kyirejson/stock-analyzer-ai) | 源代码 |

> ⚠️ Render 免费版服务会在 15 分钟无请求后休眠，首次访问可能需要等待 30-60 秒唤醒。

---

## 2. Prompt 设计：强制 LLM 只返回 JSON

### 核心策略：三层防御

我们采用 **API 层 + Prompt 层 + 代码层** 三重保障，确保 Gemini 严格返回 JSON 格式。

### 第 1 层：API 级别强制（最关键）

```python
# backend/main.py - 第 108-114 行
payload = json.dumps({
    "contents": [{"parts": [{"text": prompt}]}],
    "generationConfig": {
        "temperature": 0.3,
        "responseMimeType": "application/json"  # ✅ 核心：API 层面强制 JSON 输出
    }
}).encode("utf-8")
```

> `responseMimeType: "application/json"` 是 Gemini API 的原生功能，直接在模型输出层约束格式，模型**物理上无法**输出非 JSON 内容。

### 第 2 层：Prompt 模板约束

```python
# backend/main.py - 第 78-106 行
prompt = f"""You are a professional stock analyst. Analyze the following stock data 
and return ONLY a valid JSON object with no markdown, no code blocks, no extra text.

Stock Data:
- Ticker: {stock_data['ticker']}
- Company: {stock_data['name']}
- Current Price: ${stock_data['current_price']}
- Previous Close: ${stock_data['previous_close']}
- Market Cap: {stock_data['market_cap']}
- P/E Ratio: {stock_data['pe_ratio']}
- 52-Week High: {stock_data['52_week_high']}
- 52-Week Low: {stock_data['52_week_low']}
- Sector: {stock_data['sector']}
- Industry: {stock_data['industry']}
- Recent 5-Day Prices: {stock_data['price_history']['prices']}

Return EXACTLY this JSON structure (no other text):
{{
  "summary": "A concise 2-3 sentence analysis of this stock's current situation and outlook",
  "sentiment": "Bullish",
  "risk_level": "Medium",
  "key_points": ["point 1", "point 2", "point 3"],
  "recommendation": "Brief action recommendation"
}}

Rules:
- sentiment MUST be exactly one of: "Bullish", "Neutral", "Bearish"
- risk_level MUST be exactly one of: "Low", "Medium", "High"
- Return ONLY the JSON object, nothing else
"""
```

**Prompt 设计要点：**

| 技巧 | 说明 | 示例 |
|------|------|------|
| 角色设定 | 明确身份减少幻觉 | `You are a professional stock analyst` |
| 格式禁令 | 明确禁止非 JSON 输出 | `no markdown, no code blocks, no extra text` |
| 模板示例 | 给出完整 JSON 结构 | 展示完整的 `{}` 模板 |
| 枚举限定 | 约束字段取值范围 | `MUST be exactly one of: "Bullish", "Neutral", "Bearish"` |
| 首尾呼应 | 开头和结尾都强调只返回 JSON | `return ONLY` ... `nothing else` |

### 第 3 层：代码验证兜底

```python
# backend/main.py - 第 130-144 行
# 解析 JSON —— 如果不是合法 JSON，直接抛异常
analysis = json.loads(text)

# 校验必要字段存在
required = ["summary", "sentiment", "risk_level", "key_points", "recommendation"]
for field in required:
    if field not in analysis:
        raise ValueError(f"Missing field: {field}")

# 自动修正非法枚举值
if analysis["sentiment"] not in ["Bullish", "Neutral", "Bearish"]:
    analysis["sentiment"] = "Neutral"
if analysis["risk_level"] not in ["Low", "Medium", "High"]:
    analysis["risk_level"] = "Medium"
```

### LLM 返回结果示例

```json
{
  "summary": "Apple is trading near its 52-week high at $300.23, showing strong bullish momentum with a 5-day uptrend. The P/E ratio of 36.35 suggests premium valuation.",
  "sentiment": "Bullish",
  "risk_level": "Medium",
  "key_points": [
    "Stock is within 1% of its 52-week high ($303.20)",
    "Consistent 5-day uptrend from $292.68 to $300.23",
    "Above-average trading volume indicates strong buyer interest"
  ],
  "recommendation": "Hold current positions; consider taking partial profits near 52-week high resistance."
}
```

---

## 3. Debug 记录

### 🐛 Bug: Render 部署失败 —— Python 版本不兼容

**问题描述：**

首次部署到 Render.com 时，构建失败，报错如下：

```
==> Using Python version 3.14.3 (default)
...
error: subprocess-exited-with-error
  × Preparing metadata (pyproject.toml) did not run successfully.
  │ exit code: 1
  ╰─> error: failed to create directory `/usr/local/cargo/registry/cache/`
      Caused by: Read-only file system (os error 30)
      💥 maturin failed
==> Build failed 😞
```

**根因分析：**

Render 默认使用了最新的 Python 3.14.3，而 `pydantic-core` 没有为 Python 3.14 提供预编译的 wheel 包。Pip 尝试从源码编译，需要 Rust/Cargo 工具链，但 Render 构建环境的文件系统是只读的，导致 Cargo 无法创建缓存目录。

**解决方案：**

使用 AI 工具分析错误日志后，确定了两个修复措施：

1. **锁定 Python 版本**：创建 `backend/.python-version` 文件，指定 `3.11.12`（稳定且有预编译包）
2. **放宽依赖版本**：将 `requirements.txt` 中的精确版本锁定改为最低版本约束

```diff
# backend/.python-version（新增文件）
+ 3.11.12

# backend/requirements.txt
- fastapi==0.115.5
- pydantic==2.10.3
- yfinance==0.2.48
+ fastapi>=0.115.0
+ pydantic>=2.0.0
+ yfinance>=0.2.40
```

**修复结果：**

```
==> Using Python version 3.11.12
==> Running build command 'pip install -r requirements.txt'...
Successfully installed ... pydantic-2.13.4 pydantic-core-2.46.4 ...
==> Build successful 🎉
==> Your service is live 🎉
```

**经验总结：**

> 部署到云平台时，始终显式指定运行时版本，不要依赖平台默认值。使用 `>=` 而非 `==` 版本约束可以获得更好的跨平台兼容性。

---

## 技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| 前端 | HTML + CSS + JavaScript | 单文件，无框架依赖 |
| 后端 | FastAPI (Python 3.11) | RESTful API |
| AI | Google Gemini 2.5 Flash | 股票分析 + 严格 JSON 输出 |
| 股票数据 | yfinance | 免费实时行情，无需 API Key |
| 数据库 | Supabase (PostgreSQL) | 存储分析历史记录 |
| 部署 | Render.com | 后端 Web Service + 前端 Static Site |

## 项目结构

```
stock-analyzer-ai/
├── backend/
│   ├── main.py              # FastAPI 主应用（含 Gemini Prompt）
│   ├── requirements.txt     # Python 依赖
│   ├── .python-version      # Python 版本锁定 (3.11.12)
│   ├── Procfile              # Render 部署配置
│   └── .env.example          # 环境变量模板
├── frontend/
│   └── index.html            # 单文件前端
├── README.md                 # 本文档
└── .gitignore
```

## 环境变量

| 变量 | 说明 | 配置位置 |
|------|------|----------|
| `GEMINI_API_KEY` | Google Gemini API Key | Render Environment |
| `SUPABASE_URL` | Supabase 项目 URL | Render Environment |
| `SUPABASE_KEY` | Supabase Publishable Key | Render Environment |

> ⚠️ 所有密钥通过 Render 环境变量配置，不硬编码在代码中。

## Supabase 数据表结构

```sql
create table stock_analyses (
  id uuid default gen_random_uuid() primary key,
  ticker text not null,
  company_name text,
  current_price float,
  summary text,
  sentiment text check (sentiment in ('Bullish', 'Neutral', 'Bearish')),
  risk_level text check (risk_level in ('Low', 'Medium', 'High')),
  key_points jsonb,
  recommendation text,
  raw_stock_data jsonb,
  created_at timestamptz default now()
);
```

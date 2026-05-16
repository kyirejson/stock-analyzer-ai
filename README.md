# Stock Analyzer AI 📈

全栈 AI 股票分析应用，使用 Google Gemini 分析股票数据。

## 技术栈
- **前端**: 纯 HTML/CSS/JS (单文件)
- **后端**: FastAPI (Python)
- **股票数据**: yfinance (免费，无需 API Key)
- **AI**: Google Gemini 2.0 Flash
- **数据库**: Supabase
- **部署**: Render.com

## 项目结构
```
stock-analyzer/
├── backend/
│   ├── main.py          # FastAPI 主应用
│   ├── requirements.txt # Python 依赖
│   ├── Procfile         # Render 部署配置
│   └── .env.example     # 环境变量示例
└── frontend/
    └── index.html       # 单文件前端
```

## 本地运行
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

## 环境变量
| 变量 | 说明 |
|------|------|
| `GEMINI_API_KEY` | Google Gemini API Key |
| `SUPABASE_URL` | Supabase 项目 URL |
| `SUPABASE_KEY` | Supabase anon key |

## Supabase 数据表
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

# DeepSeek AI News Crew

一个自动收集和整理AI领域热点新闻的工具。

## 功能特点

- 自动搜索最新AI相关新闻，并进行评分筛选
- 每天输出7-15条高质量AI新闻摘要报告
- 支持将新闻报告发送到企业微信群
- 文件名中包含日期，方便历史查阅
- 可配置的搜索深度和评分阈值

## 技术栈

- Python 3.10+
- CrewAI: 多代理系统框架
- DeepSeek API: 大型语言模型服务
- Serper/Google/Bing API: 搜索引擎服务

## 文件输出

系统会在Outputs目录下生成以下文件，文件名包含日期(YYYYMMDD格式)：

- `raw_news_data_YYYYMMDD.json`: 包含原始新闻数据、评分和链接
- `ai_news_report_YYYYMMDD.md`: 最终生成的Markdown格式新闻报告

## 配置说明

### 环境变量

您可以通过创建`.env`文件来配置系统，主要参数包括：

- `MIN_NEWS_SCORE`: 最低新闻评分阈值(默认6分)
- `RAW_SEARCH_COUNT`: 初始搜索的新闻数量(默认50条)
- `MIN_NEWS_COUNT`: 最少包含的新闻条数(默认7条)
- `MAX_NEWS_COUNT`: 最多包含的新闻条数(默认15条)
- `TARGET_NEWS_COUNT`: 目标新闻条数(默认10条)

详细配置请参考`ENV_CONFIGURATION.md`文件。

## 使用方法

### 手动运行

```bash
crewai run
```

### 自动定时任务

Windows系统可使用任务计划程序设置每天自动运行：

1. 参考`README_AUTO_TASK.md`文件设置自动任务
2. 可导入`ai_news_daily_task.xml`到Windows任务计划程序

## 许可

[MIT License](LICENSE)

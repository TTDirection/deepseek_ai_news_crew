# DeepSeek AI News Crew 环境变量配置指南

本文档描述了如何通过`.env`文件配置DeepSeek AI News Crew系统的各项参数。

## 基本配置

在项目根目录创建一个名为`.env`的文件，内容如下：

```
# API相关配置
DEEPSEEK_API_KEY=your_deepseek_api_key
SEARCH_API_KEY=your_search_api_key
SEARCH_ENGINE_ID=your_search_engine_id
SEARCH_API_TYPE=serper  # 可选值: google, bing, serper

# 新闻评分和条数配置
MIN_NEWS_SCORE=6       # 最低新闻评分，低于此分数的新闻将被过滤
MIN_NEWS_COUNT=7       # 最少新闻条数
MAX_NEWS_COUNT=15      # 最多新闻条数
TARGET_NEWS_COUNT=10   # 目标新闻条数
RAW_SEARCH_COUNT=30    # 初始搜索的新闻数量

# 内容控制
INCLUDE_SOURCE=true    # 是否在输出中包含来源
INCLUDE_LINK=true      # 是否在输出中包含链接
INCLUDE_WECHAT=false   # 是否将内容发送到企业微信
VALIDATE_URLS=false    # 是否验证新闻URL可访问性

# 企业微信配置
WECHAT_WEBHOOK_KEY=your_wechat_webhook_key
```

## 配置参数说明

### API相关配置

- `DEEPSEEK_API_KEY`: DeepSeek API密钥，用于访问DeepSeek AI服务
- `SEARCH_API_KEY`: 搜索API密钥，根据选择的搜索服务而定
- `SEARCH_ENGINE_ID`: Google自定义搜索引擎ID（仅当使用Google搜索时需要）
- `SEARCH_API_TYPE`: 搜索API类型，可选值：
  - `google`: 使用Google自定义搜索
  - `bing`: 使用Bing搜索
  - `serper`: 使用Serper.dev API

### 新闻评分和条数配置

- `MIN_NEWS_SCORE`: 最低新闻评分（范围1-10），低于此分数的新闻将被过滤，默认为6
- `MIN_NEWS_COUNT`: 最少新闻条数，至少包含多少条新闻，默认为7
- `MAX_NEWS_COUNT`: 最多新闻条数，最多包含多少条新闻，默认为15
- `TARGET_NEWS_COUNT`: 目标新闻条数，系统将尝试收集这个数量的新闻，默认为10
- `RAW_SEARCH_COUNT`: 初始搜索的新闻数量，从中选择评分高于MIN_NEWS_SCORE的新闻，默认为30

### 内容控制

- `INCLUDE_SOURCE`: 是否在输出中包含来源信息，值为`true`或`false`
- `INCLUDE_LINK`: 是否在输出中包含链接，值为`true`或`false`
- `INCLUDE_WECHAT`: 是否将内容发送到企业微信，值为`true`或`false`
- `VALIDATE_URLS`: 是否验证新闻URL可访问性，值为`true`或`false`（设为true可能会减慢处理速度）

### 企业微信配置

- `WECHAT_WEBHOOK_KEY`: 企业微信群机器人的Webhook密钥，仅当`INCLUDE_WECHAT=true`时使用

## 注意事项

1. 环境变量值区分大小写，`true`和`false`必须使用小写
2. 确保`.env`文件不会被提交到版本控制系统中，已在`.gitignore`中忽略
3. 如果你的系统不支持`.env`文件，可以直接设置环境变量
4. 所有配置项都有默认值，但建议至少设置API密钥相关的配置

## 输出文件

系统会在以下位置生成输出文件：

- `Outputs/ai_news_report_YYYYMMDD.md`: 最终的AI新闻报告，包含日期
- `Outputs/raw_news_data_YYYYMMDD.json`: 原始新闻数据，包含完整信息和评分
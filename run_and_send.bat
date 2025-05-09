@echo off
echo 正在生成AI热点新闻...
crewai run

echo.
echo 生成完成，正在发送到企业微信...
python -m src.deepseek_ai_news_crew.send_to_wechat

echo.
echo 任务完成！
pause
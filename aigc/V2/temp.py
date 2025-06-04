import re

pattern = r'^(【[^】]+】[^\n]*)'
text = "【今日新闻】这是正文内容\n第二行内容"
match = re.match(pattern, text)
if match:
    print(match.group(0))  # 输出：【今日新闻】这是正文内容
    print(match.group(1))  # 输出：【今日新闻】这是正文内容
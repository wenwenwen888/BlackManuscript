"""找出 JSON 文件里所有半角双引号嵌套在中文里的位置。"""
import re

PATH = r"G:\WorkSpaces\BlackManuscript\site\src\content\daily\2026-07-19.json"
text = open(PATH, encoding="utf-8").read()

# 匹配形如 "xxx"yyy"zzz" 这种中文文本里夹半角双引号的问题
# 策略：找出所有字符串 value 内部含半角双引号的位置
# 简化：扫描每一行，找 value 部分（第二个 " 之后到行尾）里是否还有 "
lines = text.splitlines()
for i, line in enumerate(lines, 1):
    # 找出所有 "
    positions = [j for j, c in enumerate(line) if c == '"']
    if len(positions) > 4:
        # 4 个引号是合法的 key:value 结构（"key": "value"）
        # 超过 4 个说明 value 里嵌了 "
        print(f"L{i}: {line}")

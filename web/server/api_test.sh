#!/bin/bash
# 测试 API 服务器的 curl 脚本

BASE_URL="http://localhost:5000"

echo "======================================"
echo "API 测试脚本"
echo "======================================"
echo ""

# 1. 健康检查
echo ">>> 1. 健康检查"
curl -s "$BASE_URL/api/health" | python3 -m json.tool
echo ""

# 2. 搜索所有导师
echo ">>> 2. 搜索所有导师"
curl -s "$BASE_URL/api/teachers/search?limit=5" | python3 -m json.tool
echo ""

# 3. 按姓名搜索
echo ">>> 3. 按姓名搜索"
curl -s "$BASE_URL/api/teachers/search?name=陈" | python3 -m json.tool
echo ""

# 4. 按学校搜索
echo ">>> 4. 按学校搜索"
curl -s "$BASE_URL/api/teachers/search?school=浙江大学" | python3 -m json.tool
echo ""

# 5. 组合搜索
echo ">>> 5. 组合搜索（姓名+学校）"
curl -s "$BASE_URL/api/teachers/search?name=陈&school=浙江大学" | python3 -m json.tool
echo ""

# 6. 获取单个导师详情（需要先知道 ID）
echo ">>> 6. 获取导师详情"
curl -s "$BASE_URL/api/teachers/1" | python3 -m json.tool
echo ""

# 7. AI 匹配评价
echo ">>> 7. AI 匹配评价"
curl -s -X POST "$BASE_URL/api/match" \
  -H "Content-Type: application/json" \
  -d '{
    "raw_teacher_name": "陈永生",
    "raw_school_name": "浙江大学",
    "content": "陈老师讲课很好，非常负责任，学术水平很高"
  }' | python3 -m json.tool
echo ""

echo "======================================"
echo "测试完成"
echo "======================================"

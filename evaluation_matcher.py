"""
AI Agent评价匹配系统

使用DeepSeek API + Function Calling实现智能匹配
Agent可以调用工具函数查询老师信息，判断评价是否属于目标老师

匹配策略：
- 置信度 >= 0.9: 自动接受匹配
- 置信度 0.7-0.9: 自动接受但标记需注意
- 置信度 0.5-0.7: 保持pending状态，需人工审核
- 置信度 < 0.5: 拒绝匹配
"""

import json
import requests
from typing import Dict, List, Optional, Any, Tuple
from storage import StorageBackend


# 使用与parse_one.py相同的API配置
API_KEY = "sk-becd12b662a24b238ad964b956790629"
API_URL = "https://api.deepseek.com/v1/chat/completions"


class EvaluationMatcher:
    """评价匹配器：使用AI Agent智能匹配评价与老师"""

    def __init__(self, storage: StorageBackend):
        """
        初始化匹配器

        Args:
            storage: 存储后端（用于查询老师信息）
        """
        self.storage = storage
        self.api_key = API_KEY
        self.api_url = API_URL

    def _get_tools_definition(self) -> List[Dict[str, Any]]:
        """定义Agent可用的工具（Function Calling）"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "search_teachers",
                    "description": "搜索老师信息（模糊匹配）。可以根据姓名、学校、学院等条件查询老师。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "老师姓名（模糊匹配），例如：'张三'"
                            },
                            "school": {
                                "type": "string",
                                "description": "学校名称（模糊匹配），例如：'清华大学'"
                            },
                            "college": {
                                "type": "string",
                                "description": "学院名称（模糊匹配），例如：'计算机学院'"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "返回结果数量限制，默认10",
                                "default": 10
                            }
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_teacher_details",
                    "description": "根据老师ID获取详细信息",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "teacher_id": {
                                "type": "integer",
                                "description": "老师的唯一ID"
                            }
                        },
                        "required": ["teacher_id"]
                    }
                }
            }
        ]

    def _call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """
        执行工具调用

        Args:
            tool_name: 工具名称
            arguments: 工具参数

        Returns:
            工具执行结果（JSON字符串）
        """
        if tool_name == "search_teachers":
            name = arguments.get('name')
            school = arguments.get('school')
            college = arguments.get('college')
            limit = arguments.get('limit', 10)

            results = self.storage.search_teachers(
                name=name,
                school=school,
                college=college,
                limit=limit
            )
            return json.dumps(results, ensure_ascii=False, indent=2)

        elif tool_name == "get_teacher_details":
            teacher_id = arguments.get('teacher_id')
            teacher = self.storage.get_teacher_by_id(teacher_id)
            if teacher:
                return json.dumps(teacher, ensure_ascii=False, indent=2)
            else:
                return json.dumps({"error": f"未找到ID={teacher_id}的老师"}, ensure_ascii=False)

        else:
            return json.dumps({"error": f"未知工具: {tool_name}"}, ensure_ascii=False)

    def match_evaluation(
        self,
        evaluation_info: Dict[str, Any],
        max_iterations: int = 5
    ) -> Tuple[Optional[int], float, str, List[Dict]]:
        """
        使用AI Agent匹配评价

        Args:
            evaluation_info: 评价信息（包含raw_teacher_name, raw_school_name, content等）
            max_iterations: 最大迭代次数（防止Agent陷入循环）

        Returns:
            (teacher_id, confidence, reasoning, tool_calls)
            - teacher_id: 匹配的老师ID（None表示无法匹配）
            - confidence: 置信度（0-1）
            - reasoning: 匹配理由
            - tool_calls: Agent的工具调用记录
        """
        # 构建初始prompt
        system_prompt = """你是一个导师评价匹配助手。你的任务是判断一条评价是否属于数据库中的某位老师。

**可用工具**：
1. search_teachers(name, school, college) - 搜索老师信息
2. get_teacher_details(teacher_id) - 获取老师详细信息

**匹配标准**：
- 姓名必须完全匹配（不考虑同音异字）
- 学校必须匹配（允许简称，如"清华"对应"清华大学"）
- 学院可以有差异（如"计算机系"对应"计算机科学与技术学院"）
- 研究方向、职称等可以作为辅助判断

**置信度评分**：
- 0.9-1.0: 姓名+学校+学院完全匹配，或姓名+学校+研究方向高度吻合
- 0.7-0.9: 姓名+学校匹配，学院有差异但合理
- 0.5-0.7: 姓名+学校匹配，但其他信息不确定
- 0.0-0.5: 姓名不匹配，或学校不匹配，或信息严重冲突

**重要**：
- 如果找到多个同名老师，必须根据学校、学院等信息区分
- 如果评价信息不完整，宁可给低置信度，不要强行匹配
- 完成判断后，返回JSON格式：
  {
    "matched": true/false,
    "teacher_id": 123 或 null,
    "confidence": 0.85,
    "reasoning": "匹配理由说明"
  }
"""

        user_prompt = f"""请判断以下评价是否属于数据库中的某位老师：

**评价信息**：
- 老师姓名: {evaluation_info.get('raw_teacher_name', '未知')}
- 学校名称: {evaluation_info.get('raw_school_name', '未知')}
- 评价内容: {evaluation_info.get('content', '无')[:200]}...

请使用工具查询老师信息，并给出匹配结果。"""

        # 初始化消息历史
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # Agent迭代调用
        tool_calls_history = []
        for iteration in range(max_iterations):
            # 调用DeepSeek API
            payload = {
                "model": "deepseek-chat",
                "messages": messages,
                "tools": self._get_tools_definition(),
                "temperature": 0.1
            }
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            try:
                response = requests.post(
                    self.api_url,
                    json=payload,
                    headers=headers,
                    timeout=30
                )
                response.raise_for_status()
                result = response.json()
            except Exception as e:
                print(f"❌ API调用失败: {e}")
                return None, 0.0, f"API调用失败: {str(e)}", tool_calls_history

            # 解析响应
            choice = result['choices'][0]
            message = choice['message']
            finish_reason = choice.get('finish_reason')

            # 将assistant消息添加到历史
            messages.append(message)

            # 检查是否有工具调用
            if finish_reason == 'tool_calls' and message.get('tool_calls'):
                # 执行所有工具调用
                for tool_call in message['tool_calls']:
                    tool_name = tool_call['function']['name']
                    arguments = json.loads(tool_call['function']['arguments'])

                    # 记录工具调用
                    tool_calls_history.append({
                        'tool': tool_name,
                        'arguments': arguments,
                        'iteration': iteration
                    })

                    print(f"  🔧 Agent调用工具: {tool_name}({arguments})")

                    # 执行工具
                    tool_result = self._call_tool(tool_name, arguments)

                    # 将工具结果添加到消息历史
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call['id'],
                        "content": tool_result
                    })

                # 继续下一轮迭代（让Agent处理工具结果）
                continue

            # 如果finish_reason是stop，说明Agent给出了最终答案
            elif finish_reason == 'stop':
                content = message.get('content', '')

                # 尝试解析JSON结果
                try:
                    # 提取JSON部分
                    import re
                    json_match = re.search(r'\{.*\}', content, re.DOTALL)
                    if json_match:
                        result_json = json.loads(json_match.group(0))

                        matched = result_json.get('matched', False)
                        teacher_id = result_json.get('teacher_id')
                        confidence = float(result_json.get('confidence', 0.0))
                        reasoning = result_json.get('reasoning', '')

                        return teacher_id, confidence, reasoning, tool_calls_history
                    else:
                        # 没有找到JSON，使用默认值
                        print(f"⚠️  Agent响应中未找到JSON格式: {content}")
                        return None, 0.0, f"Agent响应格式错误: {content}", tool_calls_history

                except Exception as e:
                    print(f"❌ 解析Agent响应失败: {e}")
                    print(f"响应内容: {content}")
                    return None, 0.0, f"解析失败: {str(e)}", tool_calls_history

            else:
                # 其他finish_reason
                print(f"⚠️  未预期的finish_reason: {finish_reason}")
                break

        # 达到最大迭代次数
        print(f"⚠️  达到最大迭代次数({max_iterations})，匹配失败")
        return None, 0.0, "达到最大迭代次数，匹配失败", tool_calls_history

    def process_pending_evaluations(
        self,
        batch_size: int = 100,
        auto_match_threshold: float = 0.7
    ) -> Dict[str, int]:
        """
        批量处理待匹配的评价

        Args:
            batch_size: 批量处理数量
            auto_match_threshold: 自动匹配阈值（>= 此值自动关联）

        Returns:
            统计信息 {matched, rejected, needs_review, failed}
        """
        print(f"\n{'='*60}")
        print(f"🤖 开始批量匹配评价，批量大小={batch_size}")
        print(f"{'='*60}\n")

        # 获取待匹配评价
        pending_evaluations = self.storage.get_pending_evaluations(limit=batch_size)
        total = len(pending_evaluations)

        if total == 0:
            print("✅ 没有待匹配的评价")
            return {'matched': 0, 'rejected': 0, 'needs_review': 0, 'failed': 0}

        print(f"📋 待匹配评价: {total} 条\n")

        # 统计信息
        matched_count = 0
        rejected_count = 0
        needs_review_count = 0
        failed_count = 0

        # 逐条处理
        for idx, evaluation in enumerate(pending_evaluations, 1):
            eval_id = evaluation['id']
            raw_name = evaluation['raw_teacher_name']
            raw_school = evaluation['raw_school_name']

            print(f"[{idx}/{total}] 匹配评价ID={eval_id}: {raw_name} ({raw_school})")

            try:
                # 调用Agent匹配
                teacher_id, confidence, reasoning, tool_calls = self.match_evaluation(evaluation)

                print(f"  📊 置信度: {confidence:.2f}")
                print(f"  💬 理由: {reasoning}")

                # 根据置信度决定匹配状态
                if confidence >= 0.9:
                    # 高置信度：自动接受
                    match_status = 'matched'
                    self.storage.update_evaluation_match(
                        eval_id, teacher_id, confidence, reasoning, match_status
                    )
                    matched_count += 1
                    print(f"  ✅ 自动匹配成功: teacher_id={teacher_id}\n")

                elif confidence >= auto_match_threshold:
                    # 中等置信度：自动接受但标记
                    match_status = 'matched'
                    reasoning = f"[需注意] {reasoning}"
                    self.storage.update_evaluation_match(
                        eval_id, teacher_id, confidence, reasoning, match_status
                    )
                    matched_count += 1
                    print(f"  ⚠️  自动匹配（需注意）: teacher_id={teacher_id}\n")

                elif confidence >= 0.5:
                    # 低置信度：保持pending，需人工审核
                    match_status = 'pending'
                    self.storage.update_evaluation_match(
                        eval_id, teacher_id, confidence, f"[需人工审核] {reasoning}", match_status
                    )
                    needs_review_count += 1
                    print(f"  ⏸️  需人工审核: confidence={confidence:.2f}\n")

                else:
                    # 极低置信度：拒绝匹配
                    match_status = 'rejected'
                    self.storage.update_evaluation_match(
                        eval_id, None, confidence, reasoning, match_status
                    )
                    rejected_count += 1
                    print(f"  ❌ 拒绝匹配: confidence={confidence:.2f}\n")

                # 保存匹配历史
                self.storage.add_match_history({
                    'evaluation_id': eval_id,
                    'matched_teacher_id': teacher_id,
                    'confidence_score': confidence,
                    'match_decision': match_status,
                    'reasoning': reasoning,
                    'tool_calls': tool_calls
                })

            except Exception as e:
                print(f"  ❌ 匹配失败: {e}\n")
                failed_count += 1
                continue

        # 输出统计
        print(f"{'='*60}")
        print(f"✅ 批量匹配完成！")
        print(f"{'='*60}")
        print(f"📊 统计信息:")
        print(f"   - 总评价数: {total}")
        print(f"   - 自动匹配: {matched_count}")
        print(f"   - 需人工审核: {needs_review_count}")
        print(f"   - 拒绝匹配: {rejected_count}")
        print(f"   - 失败: {failed_count}")
        print(f"{'='*60}\n")

        return {
            'matched': matched_count,
            'rejected': rejected_count,
            'needs_review': needs_review_count,
            'failed': failed_count
        }


# 示例用法
if __name__ == '__main__':
    from storage import get_storage_backend

    # 连接PostgreSQL
    storage = get_storage_backend("postgresql")

    # 创建匹配器
    matcher = EvaluationMatcher(storage)

    # 测试单条评价匹配
    test_evaluation = {
        'raw_teacher_name': '陈永生',
        'raw_school_name': '同济大学',
        'content': '陈老师讲课很好，项目经验丰富，对学生很负责任...'
    }

    print("=== 测试单条评价匹配 ===\n")
    teacher_id, confidence, reasoning, tool_calls = matcher.match_evaluation(test_evaluation)
    print(f"\n匹配结果:")
    print(f"  teacher_id: {teacher_id}")
    print(f"  confidence: {confidence}")
    print(f"  reasoning: {reasoning}")
    print(f"  tool_calls: {len(tool_calls)} 次")

    # 批量处理待匹配评价
    print("\n=== 测试批量匹配 ===\n")
    stats = matcher.process_pending_evaluations(batch_size=10)
    print(f"\n统计: {stats}")

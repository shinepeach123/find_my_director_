"""
简单的 Flask API 服务器 - 用于测试和演示
"""
from flask import Flask, request, jsonify
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from storage import get_storage_backend
from evaluation_matcher import EvaluationMatcher

app = Flask(__name__)

# 初始化存储
storage = get_storage_backend("sqlite")


@app.route("/", methods=["GET"])
def index():
    """API 根路径说明"""
    return jsonify({
        "service": "find_my_director API server",
        "status": "ok",
        "message": "This is an API service. Use /api/* endpoints.",
        "endpoints": {
            "health": "/api/health",
            "search": "/api/teachers/search?name=xxx&school=xxx&college=xxx&limit=10",
            "teacher_detail": "/api/teachers/<id>",
            "match": "/api/match"
        }
    })


@app.route("/api/teachers/search", methods=["GET"])
def search_teachers():
    """搜索导师"""
    name = request.args.get("name", "")
    school = request.args.get("school", "")
    college = request.args.get("college", "")
    limit = int(request.args.get("limit", 10))

    query_params = {}
    if name:
        query_params["name"] = name
    if school:
        query_params["school"] = school
    if college:
        query_params["college"] = college

    results = storage.search_teachers(**query_params, limit=limit)
    return jsonify({
        "success": True,
        "count": len(results),
        "data": results
    })


@app.route("/api/teachers/<int:teacher_id>", methods=["GET"])
def get_teacher(teacher_id):
    """获取导师详情"""
    teacher = storage.get_teacher_by_id(teacher_id)
    if teacher:
        return jsonify({
            "success": True,
            "data": teacher
        })
    return jsonify({
        "success": False,
        "error": "Teacher not found"
    }), 404


@app.route("/api/match", methods=["POST"])
def match_evaluation():
    """AI 评价匹配"""
    data = request.json
    eval_info = {
        "raw_teacher_name": data.get("raw_teacher_name", ""),
        "raw_school_name": data.get("raw_school_name", ""),
        "content": data.get("content", "")
    }

    matcher = EvaluationMatcher(storage)
    teacher_id, confidence, reasoning, _ = matcher.match_evaluation(eval_info)

    if teacher_id:
        teacher = storage.get_teacher_by_id(teacher_id)
        return jsonify({
            "success": True,
            "teacher_id": teacher_id,
            "confidence": confidence,
            "reasoning": reasoning,
            "teacher": teacher
        })
    return jsonify({
        "success": False,
        "error": "No match found"
    })


@app.route("/api/health", methods=["GET"])
def health():
    """健康检查"""
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    print("启动 API 服务器: http://localhost:5000")
    print("")
    print("可用端点:")
    print("  GET  /api/teachers/search?name=xxx&school=xxx&college=xxx&limit=10")
    print("  GET  /api/teachers/<id>")
    print("  POST /api/match")
    print("  GET  /api/health")
    print("")
    app.run(host="0.0.0.0", port=5000, debug=True)

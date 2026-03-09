"""
搜索导师页面
"""
import streamlit as st
import sys
from pathlib import Path
import ast

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from storage import get_storage_backend

# 初始化存储
@st.cache_resource
def get_storage():
    return get_storage_backend("sqlite")

storage = get_storage()


@st.cache_data
def get_tag_options():
    """从数据库提取去重后的标签列表，用于下拉选择。"""
    teachers = storage.get_all_teachers(limit=10000)
    tags = set()
    for teacher in teachers:
        raw_tag = teacher.get("tag")
        if not raw_tag:
            continue
        if isinstance(raw_tag, list):
            parsed = raw_tag
        else:
            parsed = None
            text = str(raw_tag).strip()
            try:
                value = ast.literal_eval(text)
                if isinstance(value, list):
                    parsed = value
            except Exception:
                parsed = None
            if parsed is None:
                parsed = [x.strip() for x in text.replace("，", ",").split(",") if x.strip()]
        for tag in parsed:
            if tag:
                tags.add(str(tag).strip())
    return sorted(tags)


def teacher_matches_tag_and_keyword(
    teacher: dict,
    selected_tag: str,
    keyword: str,
    keyword_mode: str = "OR",
) -> bool:
    """按标签精确筛选 + 多关键词模糊筛选（覆盖tag和research）。"""
    raw_tag = teacher.get("tag")
    research = str(teacher.get("research", "") or "")
    tag_text = str(raw_tag or "")

    parsed_tags = []
    if isinstance(raw_tag, list):
        parsed_tags = [str(t).strip() for t in raw_tag if str(t).strip()]
    elif raw_tag:
        text = str(raw_tag).strip()
        try:
            value = ast.literal_eval(text)
            if isinstance(value, list):
                parsed_tags = [str(t).strip() for t in value if str(t).strip()]
        except Exception:
            parsed_tags = [x.strip() for x in text.replace("，", ",").split(",") if x.strip()]

    if selected_tag and selected_tag != "全部":
        if selected_tag not in parsed_tags:
            return False

    kw = (keyword or "").strip().lower()
    if kw:
        terms = [t for t in kw.split() if t]
        searchable = f"{' '.join(parsed_tags)} {tag_text} {research}".lower()
        if terms:
            if keyword_mode == "AND":
                if not all(term in searchable for term in terms):
                    return False
            else:
                if not any(term in searchable for term in terms):
                    return False

    return True


st.title("🔍 搜索导师")

# 搜索表单
with st.form("search_form"):
    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("姓名")
        school = st.text_input("学校")
    with col2:
        college = st.text_input("学院")
        title = st.selectbox("职称", ["全部", "教授", "副教授", "讲师", "助理教授"])
    col3, col4 = st.columns(2)
    with col3:
        tag_options = ["全部"] + get_tag_options()
        selected_tag = st.selectbox("Tag筛选（下拉）", tag_options)
    with col4:
        tag_keyword = st.text_input("Tag/方向关键词（手动模糊）", placeholder="如：大模型、视觉、网络安全")
    keyword_mode = st.radio("关键词匹配模式", ["OR", "AND"], horizontal=True)
    display_limit = st.number_input("最多显示条数", min_value=10, max_value=5000, value=500, step=10)

    submitted = st.form_submit_button("搜索")

# 执行搜索
if submitted:
    # 构建查询参数
    query_params = {}
    if name:
        query_params["name"] = name
    if school:
        query_params["school"] = school
    if college:
        query_params["college"] = college

    # 查询
    results = storage.search_teachers(**query_params, limit=int(display_limit))

    # 职称筛选
    if title and title != "全部":
        results = [r for r in results if r.get("title") == title]
    # tag筛选 + 手动关键词模糊匹配（包含research）
    results = [
        r
        for r in results
        if teacher_matches_tag_and_keyword(r, selected_tag, tag_keyword, keyword_mode=keyword_mode)
    ]

    # 显示结果
    if results:
        st.success(f"找到 {len(results)} 位导师")
        if len(results) >= int(display_limit):
            st.warning(f"结果可能已截断：当前只显示前 {int(display_limit)} 条。可调大“最多显示条数”后重新搜索。")
        for teacher in results:
            with st.expander(f"{teacher.get('name')} - {teacher.get('school')}"):
                st.write(f"**学院:** {teacher.get('college', '-')}")
                st.write(f"**职称:** {teacher.get('title', '-')}")
                st.write(f"**邮箱:** {teacher.get('email', '-')}")
                st.write(f"**研究方向:** {teacher.get('research', '-')}")
    else:
        st.info("未找到匹配的导师")

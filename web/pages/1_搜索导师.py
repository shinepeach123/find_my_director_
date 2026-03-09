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
                parsed = [x.strip() for x in text.replace("\uff0c", ",").split(",") if x.strip()]
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
            parsed_tags = [x.strip() for x in text.replace("\uff0c", ",").split(",") if x.strip()]

    if selected_tag and selected_tag != "\u5168\u90e8":
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


st.title("\U0001f50d \u641c\u7d22\u5bfc\u5e08")

# 搜索表单
with st.form("search_form"):
    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("\u59d3\u540d")
        school = st.text_input("\u5b66\u6821")
    with col2:
        college = st.text_input("\u5b66\u9662")
        title = st.selectbox("\u804c\u79f0", ["\u5168\u90e8", "\u6559\u6388", "\u526f\u6559\u6388", "\u8bb2\u5e08", "\u52a9\u7406\u6559\u6388"])
    col3, col4 = st.columns(2)
    with col3:
        tag_options = ["\u5168\u90e8"] + get_tag_options()
        selected_tag = st.selectbox("Tag\u7b5b\u9009\uff08\u4e0b\u62c9\uff09", tag_options)
    with col4:
        tag_keyword = st.text_input("Tag/\u65b9\u5411\u5173\u952e\u8bcd\uff08\u624b\u52a8\u6a21\u7cca\uff09", placeholder="\u5982\uff1a\u5927\u6a21\u578b\u3001\u89c6\u89c9\u3001\u7f51\u7edc\u5b89\u5168")
    keyword_mode = st.radio("\u5173\u952e\u8bcd\u5339\u914d\u6a21\u5f0f", ["OR", "AND"], horizontal=True)
    display_limit = st.number_input("\u6700\u591a\u663e\u793a\u6761\u6570", min_value=10, max_value=5000, value=500, step=10)

    submitted = st.form_submit_button("\u641c\u7d22")

if submitted:
    query_params = {}
    if name:
        query_params["name"] = name
    if school:
        query_params["school"] = school
    if college:
        query_params["college"] = college

    results = storage.search_teachers(**query_params, limit=10000)

    if title and title != "\u5168\u90e8":
        results = [r for r in results if r.get("title") == title]
    results = [
        r
        for r in results
        if teacher_matches_tag_and_keyword(r, selected_tag, tag_keyword, keyword_mode=keyword_mode)
    ]

    total_matched = len(results)
    limit = int(display_limit)
    results = results[:limit]

    if results:
        if total_matched > limit:
            st.success(f"\u627e\u5230 {total_matched} \u4f4d\u5bfc\u5e08\uff0c\u5f53\u524d\u663e\u793a\u524d {limit} \u6761")
            st.warning("\u7ed3\u679c\u5df2\u622a\u65ad\uff0c\u53ef\u8c03\u5927\u201c\u6700\u591a\u663e\u793a\u6761\u6570\u201d\u540e\u91cd\u65b0\u641c\u7d22\u3002")
        else:
            st.success(f"\u627e\u5230 {total_matched} \u4f4d\u5bfc\u5e08")
        for teacher in results:
            with st.expander(f"{teacher.get('name')} - {teacher.get('school')}"):
                st.write(f"**\u5b66\u9662:** {teacher.get('college', '-')}")
                st.write(f"**\u804c\u79f0:** {teacher.get('title', '-')}")
                st.write(f"**\u90ae\u7bb1:** {teacher.get('email', '-')}")
                st.write(f"**\u7814\u7a76\u65b9\u5411:** {teacher.get('research', '-')}")
    else:
        st.info("\u672a\u627e\u5230\u5339\u914d\u7684\u5bfc\u5e08")

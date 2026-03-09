"""
Streamlit 主入口 - 找导师工具前端面板
"""
import streamlit as st

# 页面配置
st.set_page_config(
    page_title="找导师",
    page_icon="🎓",
    layout="wide"
)

st.switch_page("pages/1_搜索导师.py")

# 修复chunk分页功能

## 问题
查看文档内容时，切换页码后chunk列表会关闭，需要重新点击"查看内容"按钮。

## 修复目标
- ✅ 实现上下页切换功能
- ✅ 切换页码后保持chunk列表显示
- ✅ 每页显示10个chunk
- ✅ 显示当前页码/总页数

## 修复步骤
1. 修复分页逻辑，使用session_state正确跟踪页码
2. 确保切换页码时不会重置视图
3. 测试分页功能正常

## 代码修改
修改 `src/frontend/app.py` 中的查看文档内容部分：
```python
# 在查看文档内容逻辑处
if chunks_response.status_code == 200:
    chunks_data = chunks_response.json()
    chunks = chunks_data.get("chunks", [])
    total_chunks = len(chunks)

    st.success(f"📄 {selected_view_doc} - 共 {total_chunks} 个chunks")

    # 每页显示数量
    chunks_per_page = 10
    total_pages = max(1, (total_chunks + chunks_per_page - 1) // chunks_per_page)

    # 使用session_state跟踪页码
    if "current_chunk_page" not in st.session_state:
        st.session_state.current_chunk_page = 1
    
    current_page = st.session_state.current_chunk_page

    # 分页按钮
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("◀ 上一页") and current_page > 1:
            st.session_state.current_chunk_page -= 1
            st.rerun()
    with col2:
        st.markdown(f"### 第 {current_page} / {total_pages} 页")
    with col3:
        if st.button("下一页 ▶") and current_page < total_pages:
            st.session_state.current_chunk_page += 1
            st.rerun()

    # 计算当前页chunks
    start = (current_page - 1) * chunks_per_page
    end = start + chunks_per_page
    current_chunks = chunks[start:end]

    # 显示每个chunk
    for chunk in current_chunks:
        idx = chunk.get("chunk_index", start + 1)
        content = chunk.get("content", "")
        
        # 处理图片
        content = process_markdown_images(content, selected_view_doc)
        
        with st.expander(f"📝 Chunk {idx}", expanded=False):
            st.markdown(content)
```

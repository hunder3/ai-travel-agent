import os
import json
import streamlit as st
from openai import OpenAI
from tavily import TavilyClient

# ==========================================
# 1. 网页基础配置
# ==========================================
st.set_page_config(page_title="智能旅行助手", page_icon="✈️", layout="centered")
st.title("✈️ 你的专属智能旅行助手")
st.caption("基于 DeepSeek 与 Tavily 搜索构建的 AI Agent")

# ==========================================
# 2. 配置与初始化 (请替换你的 Key)
# ==========================================
DEEPSEEK_API_KEY = st.secrets["DEEPSEEK_API_KEY"]
TAVILY_API_KEY = st.secrets["TAVILY_API_KEY"] 

# 使用 st.cache_resource 缓存客户端，避免每次刷新网页都重新连接
@st.cache_resource 
def get_clients():
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
    tavily_client = TavilyClient(api_key=TAVILY_API_KEY)
    return client, tavily_client

client, tavily_client = get_clients()

# ==========================================
# 3. 定义外部工具
# ==========================================
def web_search(query: str) -> str:
    try:
        response = tavily_client.search(query=query, search_depth="basic")
        results = [result["content"] for result in response.get("results", [])]
        return "\n".join(results)
    except Exception as e:
        return f"搜索失败: {e}"

tools = [{
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "当需要查询实时信息（如天气、新闻、景点推荐等）时调用此工具。",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "搜索关键词"}},
            "required": ["query"],
        },
    }
}]

# ==========================================
# 4. 网页状态管理 (让网页记住聊天历史)
# ==========================================
# messages 用于给大模型看（包含系统人设和后台工具调用）
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "system", "content": """你是一位资深且有品位的智能旅行规划师。
请遵循以下原则：
1. 【独立思考】：对于景点背景、路线统筹等，直接调动内在知识库。
2. 【克制搜索】：仅在查询实时天气、门票价格等必要时调用 web_search。
3. 【整合输出】：给出排版美观、逻辑清晰的旅行计划。"""}
    ]
# display_messages 用于在网页上展示给用户看（只展示用户问题和最终回答）
if "display_messages" not in st.session_state:
    st.session_state.display_messages = []

# 渲染历史聊天记录
for msg in st.session_state.display_messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ==========================================
# 5. 核心交互逻辑
# ==========================================
# st.chat_input 会在网页底部生成一个漂亮的输入框
if user_input := st.chat_input("你想去哪里玩？或者有什么旅行问题？"):
    
    # 将用户输入展示在界面上并存入记录
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.session_state.display_messages.append({"role": "user", "content": user_input})

    # 助手开始回复
    with st.chat_message("assistant"):
        # 🌟 亮点：使用 status 动画组件，实时展示 Agent 的内部“思考和动作”
        status_container = st.status("🧠 智能体正在思考规划中...", expanded=True)
        
        loop_count = 0
        max_loops = 5
        final_answer = ""

        while loop_count < max_loops:
            loop_count += 1
            
            try:
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=st.session_state.messages,
                    tools=tools,
                    tool_choice="auto"
                )
            except Exception as e:
                status_container.error(f"API 请求失败: {e}")
                break
            
            response_message = response.choices[0].message
            st.session_state.messages.append(response_message)

            # 判断是否调用工具
            if response_message.tool_calls:
                for tool_call in response_message.tool_calls:
                    func_name = tool_call.function.name
                    func_args = json.loads(tool_call.function.arguments)
                    
                    if func_name == "web_search":
                        query = func_args.get("query")
                        status_container.write(f"🔧 **动作**: 正在全网搜索 `{query}` ...")
                        
                        observation = web_search(query=query)
                        status_container.write(f"👀 **观察**: 获取到最新情报。")
                        
                        st.session_state.messages.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": func_name,
                            "content": observation,
                        })
            else:
                # 任务完成，输出最终回答
                final_answer = response_message.content
                status_container.update(label="✅ 规划完成！", state="complete", expanded=False)
                st.markdown(final_answer) # 在网页上打字输出
                break
        else:
            status_container.update(label="⚠️ 思考超时", state="error")
            st.error("达到最大循环次数，强行终止。")

        # 记录助手的最终回答
        if final_answer:
            st.session_state.display_messages.append({"role": "assistant", "content": final_answer})

# ==========================================
# 6. 导出文档功能
# ==========================================
if len(st.session_state.display_messages) > 0:
    st.divider() # 画一条分割线
    
    # 拼装导出文本
    export_text = "# 我的智能旅行攻略记录\n\n"
    for msg in st.session_state.display_messages:
        role_name = "👤 我" if msg["role"] == "user" else "✈️ 旅行助手"
        export_text += f"### {role_name}\n{msg['content']}\n\n---\n\n"
        
    # 生成下载按钮
    st.download_button(
        label="📥 将当前攻略下载为 Markdown 文档",
        data=export_text,
        file_name="旅行攻略.md",
        mime="text/markdown"
    )
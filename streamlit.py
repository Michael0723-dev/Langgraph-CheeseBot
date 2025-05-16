import streamlit as st
import time
import re  # For regex-based image URL detection

from database.pinecone.PineconeIndex import PineconeIndex
from database.mongo.MongoDB import MongoDB
from agent.cheese_bot.graph import GraphAgent
from langgraph.types import Command, interrupt
from prompt_template import hello
from typing import List

if __name__ == "__main__":
    if "pinecone_index" not in st.session_state:
        st.session_state.pinecone_index = PineconeIndex()
    if "mongo" not in st.session_state:
        st.session_state.mongo = MongoDB()
    if "agent" not in st.session_state:
        st.session_state.agent = GraphAgent(st.session_state.pinecone_index.indexModel, st.session_state.mongo)
        graph_code = st.session_state.agent.graph.get_graph().draw_mermaid()

        print(graph_code)
    if "interrupt" not in st.session_state:
        st.session_state.interrupt = False
    if "thinking"  not in st.session_state:
        st.session_state.thinking = ["No reasoning"]

    # --- Page Configuration ---
    st.set_page_config(
        page_title="CheeseBot",
        page_icon="🧀",
        layout="wide",
        initial_sidebar_state="expanded",
        menu_items={
            'Get Help': 'https://shop.kimelo.com/department/cheese/3365',
            'Report a bug': None,
            'About': "## 🧀 CheesyChat \n Your friendly AI assistant for all things cheese!"
        }
    )


    # --- Custom Action Function ---
    def perform_custom_action():
        st.toast("🔄 Custom Action Triggered!", icon="🎉")
        # Example: Reset a part of the session state or re-fetch something
        if "action_counter" not in st.session_state:
            st.session_state.action_counter = 0
        st.session_state.action_counter += 1
        st.info(f"Custom action performed! Counter: {st.session_state.action_counter}")
        # You might want to st.rerun() if this action needs to refresh data displayed elsewhere
        # st.rerun()


    # --- Theme Definitions (CSS Variables) ---
    LIGHT_THEME = """
    <style>
        :root {
            --primary-color: #1c83e1;
            --background-color: #ffffff;
            --secondary-background-color: #f0f2f6;
            --text-color: #31333F;
            --font: "Source Sans Pro", sans-serif;
        }
    </style>
    """

    DARK_THEME = """
    <style>
        :root {
            --primary-color: #ff4b4b;
            --background-color: #0e1117;
            --secondary-background-color: #262730;
            --text-color: #fafafa;
            --font: "Source Sans Pro", sans-serif;
        }
    </style>
    """

    # --- CSS for Fixed Top-Right Action Button and Chat Bubbles ---
    st.markdown("""
    <style>
        /* Container for the fixed button */
        .fixed-top-right-container {
            position: fixed;
            top: 0.8rem;      /* Adjust to avoid overlapping Streamlit's header/menu */
            right: 1rem;
            z-index: 1001;   /* High z-index to be on top of other elements */
        }

        /* Style the button itself within the fixed container */
        .fixed-top-right-container .stButton button {
            background-color: var(--primary-color); /* Use theme color */
            color: var(--background-color); /* Contrast text */
            border: 1px solid var(--primary-color);
            padding: 0.3rem 0.8rem;
            border-radius: 0.5rem;
            font-weight: bold;
        }
        .fixed-top-right-container .stButton button:hover {
            opacity: 0.8;
        }

        /* Chat bubble styling */
        .stChatMessage {
            border-radius: 10px;
            padding: 10px 15px;
            margin-bottom: 10px;
            /* background-color: var(--secondary-background-color) !important; /* Ensures it uses our theme */
        }
        .stChatMessage[data-testid="stChatMessageContent"] p {
            margin-bottom: 0.5em;
        }
        /* Ensure chat text color uses our theme variable */
        .stChatMessage[data-testid="stChatMessageContent"] {
            color: var(--text-color);
        }
    </style>
    """, unsafe_allow_html=True)


    def is_image_url(text):
        if isinstance(text, str) and text.lower().startswith(('http://', 'https://')):
            if re.search(r'\.(png|jpg|jpeg|gif|webp|svg)(\?|$)', text.lower()):
                return True
        return False


    # --- App Initialization ---
    if "messages" not in st.session_state:
        st.session_state.messages = []
        st.session_state.messages.append({"role": "assistant", "content": hello, "avatar": "🧀"})

    if "current_theme" not in st.session_state:
        st.session_state.current_theme = "dark"

    # --- Apply Theme CSS ---
    if st.session_state.current_theme == "dark":
        st.markdown(DARK_THEME, unsafe_allow_html=True)
    else:
        st.markdown(LIGHT_THEME, unsafe_allow_html=True)

    # --- Top-Right Fixed Action Button ---
    # This uses the "markdown wrapper" trick to create a styled container for the button.
    # st.markdown('<div class="fixed-top-right-container">', unsafe_allow_html=True)
    # if st.button("🔄 Action", key="custom_action_button"):
    #     perform_custom_action()
    # st.markdown('</div>', unsafe_allow_html=True)

    # --- Sidebar ---
    with st.sidebar:
        # st.header("🧀 CheesyChat Options")

        # if st.session_state.current_theme == "light":
        #     if st.button("🌙 Switch to Dark Mode", use_container_width=True):
        #         st.session_state.current_theme = "dark"
        #         st.rerun()
        # else:
        #     if st.button("☀️ Switch to Light Mode", use_container_width=True):
        #         st.session_state.current_theme = "light"
        #         st.rerun()
        # st.markdown("---")
        if st.button("Clear", use_container_width=False, type="primary"):
            if "messages" in st.session_state:
                del st.session_state.messages

            if "action_counter" in st.session_state:  # Also clear custom action counter for demo
                del st.session_state.action_counter
            st.rerun()
        # st.markdown("---")
        st.subheader("Agent Diagram")
        # st.graphviz_chart('''
        #     digraph LangGraph {
        #         START -> reasoning
        #         reasoning -> gen_sql_query [label="if MYSQL"]
        #         reasoning -> vector_search_node [label="if VECTORDB"]
        #         gen_sql_query -> sql_search_node
        #         sql_search_node -> data_retrieval
        #         vector_search_node -> data_retrieval
        #         data_retrieval -> human_assistance [label="if True"]
        #         data_retrieval -> generate_response [label="if False"]
        #         human_assistance -> reasoning
        #         generate_response -> END
        #
        #         START [shape=oval, style=filled, color=lightgray]
        #         END [shape=oval, style=filled, color=lightgray]
        #         reasoning [shape=box, style=filled, color=lightblue]
        #         gen_sql_query [shape=box, style=filled, color=lightblue]
        #         sql_search_node [shape=box, style=filled, color=lightblue]
        #         vector_search_node [shape=box, style=filled, color=lightblue]
        #         data_retrieval [shape=box, style=filled, color=lightblue]
        #         human_assistance [shape=box, style=filled, color=lightgreen]
        #         generate_response [shape=box, style=filled, color=lightblue]
        #     }
        # ''')
        st.image("Diagram.png")

    # --- Main Chat Interface ---
    st.title("🧀 CheeseBot")
    st.caption("Ask me anything about cheese!")

    # Display existing messages
    for message in st.session_state.messages:
        avatar = message.get("avatar", "🤵" if message["role"] == "user" else "🧀")
        with st.chat_message(message["role"], avatar=avatar):
            st.markdown(message["content"], unsafe_allow_html=True)

    if "count" not in st.session_state:
        st.session_state.count = 0


    # Get user input
    if query := st.chat_input("What kind of cheese do you like?"):
        st.session_state.messages.append({"role": "user", "content": query, "avatar": "🤵"})
        config = {"configurable": {"thread_id": "some_id"}}
        with st.chat_message("user", avatar="🤵"):
            st.markdown(query)

        with st.chat_message("assistant", avatar="🧀"):

            message_placeholder = st.empty()
            response = ''
            with st.spinner("The cheese expert is thinking..."):
                if st.session_state.interrupt == False:
                    for event in st.session_state.agent.graph.stream(
                            {"user_query": query, "chat_history": [{"role": "user", "content": query}],
                             "is_cheese_query": None, "is_query_question_analyze_check": False, "observation": "", "generated_sql": "", "db_search_results_summary": {}, "thoughts": ["Starting..."]}, config=config):
                        print("event:", event, event.values())
                        if '__interrupt__' in event:
                            st.session_state.interrupt = True
                            print(event['__interrupt__'][0].value)

                            response = "I understood your question as follows:" + "\n" + event['__interrupt__'][0].value["message"] + "\n" + "Am I right?"
                        elif 'generate_answer' in event:
                            print(event['generate_answer'])
                            response = event['generate_answer']["final_answer"]
                        elif 'reasoner' in event:
                            st.session_state.thinking = event['reasoner']["thoughts"]
                            # print("process: ", st.session_state.thinking)
                        # for value in event.values():
                        #     print("Assistant:", value)
                        #     pass
                else:
                    st.session_state.interrupt = False
                    print("Graph restarting...")
                    print("human feedback: ", query)
                    for event in st.session_state.agent.graph.stream(Command(resume=query), config=config):
                        print("2event:", event)
                        if 'generate_answer' in event:
                            print(event['generate_answer'])
                            response = event['generate_answer']["final_answer"]
                        # for value in event.values():
                        #     print("Assistant:", value)
                        #     pass

            # response = stream["final_answer"]
            # response = ''
            # for text in stream:
            #     response = text

            message_placeholder.markdown(response, unsafe_allow_html=True)
            #
            # st.session_state.count += 1
            # with open(f"response/{st.session_state.count}.md", "wb") as f:
            #     f.write(response.encode())
            #     f.close()

        st.session_state.messages.append({"role": "assistant", "content": response, "avatar": "🧀"})
        with st.chat_message("thinking", avatar="🧠"):
            for i, step in enumerate(st.session_state.thinking):
                if i == len(st.session_state.thinking)-1:
                    st.markdown("---")
                    st.markdown("Generated answer")
                    st.markdown("---")
                else:
                    st.markdown("---")
                    st.markdown(f"Step {i}")
                    st.markdown(step)


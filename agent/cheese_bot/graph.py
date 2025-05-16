import os
import json
from openai import OpenAI
from database.pinecone.PineconeIndex import PineconeIndex
from database.mongo.MongoDB import MongoDB
from .utils import limit_chat_history, get_embedding
from prompt_template import isCheeseChat, isPossibleQuery, query2filter, system, query2mongo, general, compare_with_requery, reasoner
from typing import Annotated,List, TypedDict, Optional, Union, List, Dict
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
from langchain_core.tools import tool
from langchain.chat_models import init_chat_model
from langchain_core.messages import ToolMessage

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.types import Command, interrupt
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel

class State(TypedDict):
    thoughts: Optional[List[str]]
    action_name: Optional[str]
    action_input: Optional[str]
    observation: Optional[List[str]]

    user_query: str
    chat_history: List[str]
    is_cheese_query: bool
    is_query_question_analyze_check: bool
    generated_sql: Optional[str]
    final_answer: Optional[str]
    db_search_results_summary: Optional[Union[List[Dict], str]]

class isPossible(BaseModel):
    flag: bool
    analyzed_query: str

class GraphAgent():
    def __init__(self, indexModel, mongo):
        self.indexModel = indexModel
        self.mongo = mongo
        self.client = OpenAI(api_key=os.environ['OPENAI_API_KEY'])

        self.memory = MemorySaver()
        self.graph_builder = StateGraph(State)
        self.graph_builder.add_node("reasoner", self.reasoner)
        self.graph_builder.add_node("cheese_question_check", self.cheese_question_check)
        self.graph_builder.add_node("question_analyze_check", self.question_analyze_check)
        self.graph_builder.add_node("generate_sql", self.generate_sql)
        self.graph_builder.add_node("mongodb_search", self.mongodb_search)
        self.graph_builder.add_node("generate_answer", self.generate_answer)

        self.graph_builder.add_conditional_edges(
            "reasoner",
            self.route_tools,
            {
                "cheese_question_check": "cheese_question_check",
                "generate_sql": "generate_sql",
                "question_analyze_check": "question_analyze_check",
                "generate_answer": "generate_answer"
            },
        )

        # Any time a tool is called, we return to the chatbot to decide the next step
        self.graph_builder.add_edge(START, "reasoner")
        self.graph_builder.add_edge("cheese_question_check", "reasoner")
        self.graph_builder.add_edge("question_analyze_check", "reasoner")
        self.graph_builder.add_edge("generate_sql", "mongodb_search")
        self.graph_builder.add_edge("mongodb_search", "reasoner")
        self.graph_builder.add_edge("generate_answer", END)
        self.graph = self.graph_builder.compile(checkpointer=self.memory)

    def route_tools(self, state: State):
        """
        Use in the conditional_edge to route to the ToolNode if the last message has tool calls. Otherwise, route to the end.
        """
        print(state)
        if state.get("action_name") == "cheese_question_check":
            print("cheese_question_check...")
            return "cheese_question_check"
        elif state.get("action_name") == "question_analyze_check":
            print("question_analyze_check...")
            return "question_analyze_check"
        elif state.get("action_name") == "generate_sql":
            print("generate_sql...")
            return "generate_sql"
        elif state.get("action_name") == "mongodb_search":
            print("mongodb_search...")
            return "mongodb_search"
        elif state.get("action_name") == "generate_answer":
            print("generate_answer...")
            return "generate_answer"
        return

    def reasoner(self, state: State):

        print("====================")
        print("...reasoning process")
        # print(state)
        print("====================")
        reasoning_process = self.client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {
                    "role": "developer", "content": reasoner
                },
                {
                    "role": "user", "content": "this is user query: " + state.get("user_query") + " and this is chat history: " + str(state.get("chat_history")) + " this is observation data: " + str(state.get("observation")) + " `is_cheese_query` is " + str(state.get("is_cheese_query")) + " and `is_query_confirmed_by_user` is " + str(state.get("is_query_confirmed_by_user"))
                }
            ],
            response_format={"type": "json_object"}
        )
        # print(state.get("is_query_question_analyze_check"))
        if json.loads(reasoning_process.choices[0].message.content)["action_name"] == "question_analyze_check" and state.get("is_query_question_analyze_check") == True:
            return {"thoughts": state.get("thoughts") + [str(json.loads(reasoning_process.choices[0].message.content)["thought"])], "action_name": "generate_answer","action_input": json.loads(reasoning_process.choices[0].message.content)["action_input"]}
        else:
            return {"thoughts": state.get("thoughts") + [str(json.loads(reasoning_process.choices[0].message.content)["thought"])], "action_name": json.loads(reasoning_process.choices[0].message.content)["action_name"], "action_input": json.loads(reasoning_process.choices[0].message.content)["action_input"]}

    def cheese_question_check(self, state: State) -> str:
        """Every user question has to be checked that is a question concern with cheese, or not"""
        print("===========================")
        print("...checking cheese question")
        # print(state)
        print("===========================")
        prompts = [{"role": "developer", "content": isCheeseChat}] + [
            {"role": "user", "content": "this is user query" + state.get("user_query", "") + " and this is chat history: " + str(state.get("chat_history")) }]
        response = self.client.chat.completions.create(
            model="gpt-4.1",
            messages=prompts,
            max_tokens=10,
            temperature=0.0
        )
        if response.choices[0].message.content.strip().lower() == "yes":
            return {"is_cheese_query": True, "observation": "this question is about cheese."}
        else:
            return {"is_cheese_query": False, "observation": "this question is not about cheese.", "chat_history": state.get("chat_history")}

    def question_analyze_check(self, state: State) -> str:

        print("======================================")
        print("...checking question confirmed by user")
        # print(state)
        print("=======================================")
        prompts = [{"role": "developer", "content": isPossibleQuery}] + [{"role": "user", "content": "this is user query: " + state.get("user_query") + "and this is chat history: " + str(state.get("chat_history"))}]
        response = self.client.beta.chat.completions.parse(
            model="gpt-4.1",
            messages=prompts,
            response_format=isPossible,
            temperature=0.1
        )
        # print(json.loads(response.choices[0].message.content))

        if json.loads(response.choices[0].message.content)["flag"] == True:
            return {"is_query_question_analyze_check": True, "observation": f"user_confirmed: true, confirmed_query: {state.get('user_query')}, user_feedback: yes, you are right."}

        else:
            print("===============")
            print("interrupting...")
            user_requery = interrupt(value={"message": (json.loads(response.choices[0].message.content))["analyzed_query"]})
            print("...Graph restarting")
            print("===================")
            response2 = self.client.beta.chat.completions.parse(
                model="gpt-4.1",
                messages=[
                    {
                        "role": "developer", "content": compare_with_requery
                    },
                    {
                        "role": "user", "content": "organized_question is " + (json.loads(response.choices[0].message.content))["analyzed_query"] + "and user's feedback is " + user_requery
                    }
                ],
                response_format=isPossible,
                temperature=0.1
            )

            # print("response2:", response2)
            if json.loads(response2.choices[0].message.content)["flag"] == True:
                print("...this is user confirmed question")
                return {"is_query_question_analyze_check": True, "observation": f"user_confirmed: true, confirmed_query: {state.get('user_query')}, user_feedback: yes"}

            else:
                print("...should be confirmed by user again")
                return {"user_query": json.loads(response2.choices[0].message.content)["analyzed_query"], "observation": f"user_confirmed: false, confirmed_query: {json.loads(response2.choices[0].message.content)["analyzed_query"]}, user_feedback: {user_requery}"}

    def generate_sql(self, state: State):

        print("=======================")
        print("...generating sql query")
        print("=======================")
        print(state.get("user_query"))
        prompts = [{"role": "developer", "content": query2mongo}] + [
            {"role": "user", "content": state.get("user_query")}]
        response = self.client.chat.completions.create(
            model="gpt-4.1",
            messages=prompts,
            response_format={"type": "json_object"},
            temperature=0.1
        )

        filter_data = json.loads(response.choices[0].message.content)

        if filter_data == {}:
            return {"generated_sql": filter_data, "observation": f"sql query: NO_QUERY_POSSIBLE, error: null"}
        else:
            return {"generated_sql": filter_data, "observation": f"sql query: {filter_data}, error: null"}

    def search_pinecone(self,query, filter, limit):

        print("=====================")
        print("...searching pinecone")
        print("=====================")
        embedding = get_embedding(query)

        results = self.indexModel.query(
            vector=embedding,
            filter=filter,
            top_k=limit,
            include_metadata=True,
            namespace=os.environ["PINECONE_ENV"]
        )
        return results.get("matches", [])

    def mongodb_search(self,state: State):

        print("====================")
        print("...searching mongodb")
        print("====================")
        if state.get("generated_sql")["search_type"]:
            skus = list(self.mongo.get_skus(state.get("generated_sql")["filter"], state.get("generated_sql")["sort"], state.get("generated_sql")["limit"]))
            flag = True
        else:
            skus, flag = list(self.mongo.aggregate(state.get("generated_sql")["pipeline"]))
        print(skus)

        if flag:
            results = self.search_pinecone(state.get("user_query"), {"sku": {"$in": skus}}, state.get("generated_sql")["limit"])
            context = "\n\n-----------------------------------------\n\n".join([json.dumps(result.get('metadata', {}), indent=4, ensure_ascii=False, sort_keys=False) for result in results])
        else:
            results = skus
            context = json.dumps(results, indent=4, ensure_ascii=False, sort_keys=False)

        print(f"      results: {len(results)}, {flag}")

        return {"db_search_results_summary": context, "observation": f"results: {context}, count of results: {len(results)}"}


    def generate_answer(self, state: State):

        print("====================")
        print("...answer generating")
        # print(state)
        print("====================")

        if state.get("is_cheese_query") == True:
            prompts = [{"role": "developer", "content": system + state.get("db_search_results_summary")}, {"role": "user", "content": state.get("user_query")}]
        else:
            prompts = [{"role": "developer", "content": general}, {"role": "user", "content": state.get("user_query")}]

        stream = self.client.chat.completions.create(
            model=os.environ["SYSTEM_CHAT_MODEL"],
            messages=prompts,
            temperature=0.1
        )

        return {"final_answer": stream.choices[0].message.content, "chat_history:": state.get("chat_history") + [f"assistant: {stream.choices[0].message.content}"]}

    # def format_conversation_history(self, messages: List[Dict[str, str]]) -> str:
    #     # return "\n".join([f"{msg.content['role']}: {msg.content['content']}" for msg in messages])
    #     return "\n".join([f"{msg.content}" for msg in messages])
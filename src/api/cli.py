from src.nodes.simple_chain import build_simple_ask_chain


def main() -> None:
    topic = input("请输入问题: ")
    if not topic.strip():
        print("输入为空。")
        return

    chain = build_simple_ask_chain()
    result = chain.invoke({"topic": topic})
    print(result.content)

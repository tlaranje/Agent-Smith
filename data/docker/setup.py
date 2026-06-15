
def final_answer(answer_string: str):
    with open("/tmp/agent/final_result.txt", "w", encoding="utf-8") as f:
        f.write(answer_string)

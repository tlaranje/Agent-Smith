
def final_answer(answer_string: str):
    with open("/tmp/agent/final_result.py", "w", encoding="utf-8") as f:
        f.write(answer_string)

def square_number(number):
    """
    This function takes a number as input and returns its square.
    """
    return number * number

# Test cases
assert square_number(5) == 25
assert square_number(-3) == 9
assert square_number(0) == 0
assert square_number(1.5) == 2.25

final_answer("""
def square_number(number):
    \"\"\"
    This function takes a number as input and returns its square.
    \"\"\"
    return number * number
""")
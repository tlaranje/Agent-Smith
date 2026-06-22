
def final_answer(answer_string: str):
    with open("/tmp/agent/final_result.py", "w", encoding="utf-8") as f:
        f.write(answer_string)

# Define the function to return the square of a number
def square_number(num):
    """
    This function calculates the square of a given number.

    Args:
        num (int or float): The number to be squared.

    Returns:
        int or float: The square of the input number.
    """
    return num ** 2

# Test the function with some examples
print(square_number(5))  # Expected output: 25
print(square_number(3.5))  # Expected output: 12.25
print(square_number(-4))  # Expected output: 16

# If tests pass, call this to finish the task:
final_answer("def square_number(num):\n    return num ** 2")
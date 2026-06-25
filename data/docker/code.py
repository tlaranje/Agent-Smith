def square_number(number):
    """
    This function takes a number as input and returns its square.

    Args:
        number: The input number.

    Returns:
        The square of the input number.
    """
    return number * number

# Test cases
assert square_number(5) == 25, f"Test Failed: Expected 25, got {square_number(5)}"
assert square_number(0) == 0, f"Test Failed: Expected 0, got {square_number(0)}"
assert square_number(-3) == 9, f"Test Failed: Expected 9, got {square_number(-3)}"
assert square_number(1.5) == 2.25, f"Test Failed: Expected 2.25, got {square_number(1.5)}"

print("All test cases passed!")

# Define the final_answer function to avoid the NameError
def final_answer(answer):
    print(f"The final answer is: {answer}")

final_answer("def square_number(number):\n    return number * number")
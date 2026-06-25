# Define a function that takes a number and returns its square
def square_number(num):
    """
    Returns the square of a given number.

    Args:
        num (float): The number to be squared.

    Returns:
        float: The square of the input number.
    """
    return num ** 2

# Test cases to verify the function works as expected
test_cases = [
    (0, 0),
    (1, 1),
    (2, 4),
    (3, 9),
    (4, 16),
    (5, 25),
    (-1, 1),
    (-2, 4),
    (-3, 9),
    (-4, 16),
    (-5, 25)
]

# Run the test cases
for num, expected_result in test_cases:
    result = square_number(num)
    assert result == expected_result, f"Test failed for input {num}, expected {expected_result}, got {result}"

# Define final_answer function
def final_answer(solution):
    print(f"The final answer is: {solution}")

# If all tests pass, submit the final answer
final_answer("def square_number(num):\n    return num ** 2")
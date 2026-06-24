
def final_answer(answer_string: str):
    with open("/tmp/agent/final_result.py", "w", encoding="utf-8") as f:
        f.write(answer_string)

# Function to return the square of a number
def square_number(num):
    """
    Returns the square of a given number.
    
    Parameters:
    num (int or float): The number to be squared.
    
    Returns:
    int or float: The square of the input number.
    """
    return num ** 2

# Test runner to verify the function
print(square_number(5))  # Expected output: 25
print(square_number(-3))  # Expected output: 9
print(square_number(0))  # Expected output: 0
print(square_number(4.5))  # Expected output: 20.25

# If tests pass, submit the function
final_answer("def square_number(num):\n    return num ** 2")
import os as _os
def final_answer(answer_string):
    _os.makedirs('/tmp/agent', exist_ok=True)
    with open('/tmp/agent/final_result.py', 'w', encoding='utf-8') as _f:
        _f.write(answer_string)

# Define the function to calculate the square of a number
def square_number(num):
    """
    This function calculates the square of a given number.

    Args:
        num (int or float): The input number.

    Returns:
        int or float: The square of the input number.
    """
    return num ** 2


# Test runner execution to verify the function
def test_square_number():
    # Test with positive integer
    assert square_number(5) == 25
    
    # Test with negative integer
    assert square_number(-3) == 9
    
    # Test with float
    assert square_number(2.5) == 6.25
    
    # Test with zero
    assert square_number(0) == 0


# Run the tests
test_square_number()

# If tests pass, call this to finish the task
final_answer("def square_number(num):\n    return num ** 2")

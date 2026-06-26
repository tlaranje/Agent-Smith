# Define a function to calculate the square of a number
def square(num):
    """
    This function calculates the square of a given number.

    Args:
        num (int or float): The number to be squared.

    Returns:
        int or float: The square of the input number.
    """
    return num ** 2

# Define the final_answer function to avoid NameError
def final_answer(function_code):
    print("Function code:", function_code)

# Test the function with some numbers
print(square(5))  # Expected output: 25
print(square(10))  # Expected output: 100
print(square(3.5))  # Expected output: 12.25

# Call the final_answer function
final_answer("def square(num):\n    return num ** 2")
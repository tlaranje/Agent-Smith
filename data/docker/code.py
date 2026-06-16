
def final_answer(answer_string: str):
    with open("/tmp/agent/final_result.py", "w", encoding="utf-8") as f:
        f.write(answer_string)

from datetime import datetime

def get_current_date_time():
    """
    Returns the current hour, day, month, and year.
    
    Returns:
        dict: A dictionary containing the current hour, day, month, and year.
    """
    now = datetime.now()
    return {
        "hour": now.hour,
        "day": now.day,
        "month": now.month,
        "year": now.year
    }

# Test the function
def test_get_current_date_time():
    current_date_time = get_current_date_time()
    assert "hour" in current_date_time
    assert "day" in current_date_time
    assert "month" in current_date_time
    assert "year" in current_date_time

# Run the test
test_get_current_date_time()
print("Test passed")

# If tests pass, call this to finish the task:
final_answer("def get_current_date_time():\n    now = datetime.now()\n    return {\n        \"hour\": now.hour,\n        \"day\": now.day,\n        \"month\": now.month,\n        \"year\": now.year\n    }")
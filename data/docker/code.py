import os as _os
def final_answer(answer_string):
    _os.makedirs('/tmp/agent', exist_ok=True)
    with open('/tmp/agent/final_result.py', 'w', encoding='utf-8') as _f:
        _f.write(answer_string)

def find_lists(Input):
    count = 0
    if isinstance(Input, list):
        return 1
    for item in Input:
        if isinstance(item, list):
            count += 1
    return count

# --- AUTOMATED TESTS ---
assert find_lists(([1, 2], [3, 4], [5, 6]))  == 3
assert find_lists(([9, 8, 7, 6, 5, 4, 3, 2, 1])) == 1

import os as _os
def final_answer(answer_string):
    _os.makedirs('/tmp/agent', exist_ok=True)
    with open('/tmp/agent/final_result.py', 'w', encoding='utf-8') as _f:
        _f.write(answer_string)



# --- AUTOMATED TESTS ---
assert find_length("10111") == 1
assert find_length("11011101100101") == 2

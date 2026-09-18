import os as _os
def final_answer(answer_string):
    _os.makedirs('/tmp/agent', exist_ok=True)
    with open('/tmp/agent/final_result.py', 'w', encoding='utf-8') as _f:
        _f.write(answer_string)

def max_difference(test_list):
    max_diff = 0
    for pair in test_list:
        diff = abs(pair[0] - pair[1])
        if diff > max_diff:
            max_diff = diff
    return max_diff

# --- AUTOMATED TESTS ---
assert max_difference([(4, 6), (2, 17), (9, 13), (11, 12)]) == 15
assert max_difference([(12, 35), (21, 27), (13, 23), (41, 22)]) == 23

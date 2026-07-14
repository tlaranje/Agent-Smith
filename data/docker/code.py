import os as _os
def final_answer(answer_string):
    _os.makedirs('/tmp/agent', exist_ok=True)
    with open('/tmp/agent/final_result.py', 'w', encoding='utf-8') as _f:
        _f.write(answer_string)

def bitwise_xor(test_tup1, test_tup2):
    return tuple(x ^ y for x, y in zip(test_tup1, test_tup2))

final_answer("def bitwise_xor(test_tup1, test_tup2):\n    return tuple(x ^ y for x, y in zip(test_tup1, test_tup2))")

# --- AUTOMATED TESTS ---
assert bitwise_xor((11, 5, 7, 10), (6, 3, 4, 4)) == (13, 6, 3, 14)
assert bitwise_xor((12, 6, 8, 11), (7, 4, 5, 6)) == (11, 2, 13, 13)

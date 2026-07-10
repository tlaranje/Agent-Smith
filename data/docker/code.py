import os as _os
def final_answer(answer_string):
    _os.makedirs('/tmp/agent', exist_ok=True)
    with open('/tmp/agent/final_result.py', 'w', encoding='utf-8') as _f:
        _f.write(answer_string)

def bitwise_xor(test_tup1, test_tup2):
    """
    Performs the mathematical bitwise xor operation across the given tuples.

    Args:
        test_tup1: The first tuple of integers.
        test_tup2: The second tuple of integers.

    Returns:
        A tuple containing the result of the bitwise XOR operation
        element-wise.
    """
    result = []
    for i in range(len(test_tup1)):
        result.append(test_tup1[i] ^ test_tup2[i])
    return tuple(result)

final_answer(
"""
def bitwise_xor(test_tup1, test_tup2):
    result = []
    for i in range(len(test_tup1)):
        result.append(test_tup1[i] ^ test_tup2[i])
    return tuple(result)
"""
)

# --- AUTOMATED TESTS ---
assert bitwise_xor((11, 5, 7, 10), (6, 3, 4, 4)) == (13, 6, 3, 14)
assert bitwise_xor((12, 6, 8, 11), (7, 4, 5, 6)) == (11, 2, 13, 13)

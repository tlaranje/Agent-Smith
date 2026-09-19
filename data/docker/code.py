import os as _os
def final_answer(answer_string):
    _os.makedirs('/tmp/agent', exist_ok=True)
    with open('/tmp/agent/final_result.py', 'w', encoding='utf-8') as _f:
        _f.write(answer_string)

from itertools import permutations

def rearrange_bigger(n):
    num_str = str(n)
    perms = set(int(''.join(p)) for p in permutations(num_str))
    bigger_nums = [p for p in perms if p > n]
    return min(bigger_nums) if bigger_nums else False

# --- AUTOMATED TESTS ---
assert rearrange_bigger(10)==False
assert rearrange_bigger(102)==120

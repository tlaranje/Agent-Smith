import os as _os
def final_answer(answer_string):
    _os.makedirs('/tmp/agent', exist_ok=True)
    with open('/tmp/agent/final_result.py', 'w', encoding='utf-8') as _f:
        _f.write(answer_string)

def soma(a, b):
    return a + b

final_answer('Sucesso!')

# --- AUTOMATED TESTS ---
assert soma(1, 2) == 3

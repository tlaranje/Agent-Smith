import os as _os
def final_answer(answer_string):
    _os.makedirs('/tmp/agent', exist_ok=True)
    with open('/tmp/agent/final_result.py', 'w', encoding='utf-8') as _f:
        _f.write(answer_string)

def merge_dictionaries_three(dict1,dict2, dict3):
    result = dict1.copy()
    result.update({k:v for k,v in dict2.items() if k not in result})
    result.update({k:v for k,v in dict3.items() if k not in result})
    return result

final_answer("def merge_dictionaries_three(dict1,dict2, dict3):\n    result = dict1.copy()\n    result.update({k:v for k,v in dict2.items() if k not in result})\n    result.update({k:v for k,v in dict3.items() if k not in result})\n    return result")

# --- AUTOMATED TESTS ---
assert merge_dictionaries_three({ "R": "Red", "B": "Black", "P": "Pink" }, { "G": "Green", "W": "White" },{"L":"lavender","B":"Blue"})=={'W': 'White', 'P': 'Pink', 'B': 'Black', 'R': 'Red', 'G': 'Green', 'L': 'lavender'}
assert merge_dictionaries_three({ "R": "Red", "B": "Black", "P": "Pink" },{"L":"lavender","B":"Blue"},{ "G": "Green", "W": "White" })=={'B': 'Black', 'P': 'Pink', 'R': 'Red', 'G': 'Green', 'L': 'lavender', 'W': 'White'}

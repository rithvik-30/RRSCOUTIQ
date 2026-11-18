"""
Critical consistency audit across:
- FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md
- submission/METHODOLOGY.md
- submission/README.md
- submission/PRESENTATION.md
- submission/DEMO_SCRIPT.md
"""
files = [
    'FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md',
    'submission/METHODOLOGY.md',
    'submission/README.md',
    'submission/PRESENTATION.md',
    'submission/DEMO_SCRIPT.md'
]

data = {}
for path in files:
    with open(path, encoding='utf-8') as f:
        data[path] = f.read()

terms_to_check = [
    'win-expectancy gradient',
    'win expectancy gradient',
    'causal ball-by-ball',
    '744',
    '776',
    '362',
    '381',
    '367',
    '408',
    '1.645',
    'Abhishek Sharma',
    'Sunil Narine',
    '+6.70%',
    '+2.72%',
    '-0.605',
    '+0.296'
]

print("=== TERM FREQUENCY AUDIT ===")
for t in terms_to_check:
    print(f'Term: "{t}"')
    for path in files:
        cnt = data[path].lower().count(t.lower())
        print(f'  {path}: {cnt}')

print("\n=== UNINTENDED TERMS CHECK ===")
forbidden = ['win-expectancy gradient', 'causal ball-by-ball', 'win probability estimate']
for f_term in forbidden:
    for path in files:
        if f_term in data[path].lower():
            print(f'WARNING: Found "{f_term}" in {path}')
        else:
            print(f'CLEAN: No "{f_term}" in {path}')

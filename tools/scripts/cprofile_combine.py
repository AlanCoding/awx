import os


DIR = '/var/log/tower/profile'


# example structure
# ncalls  tottime  percall  cumtime  percall filename:lineno(function)
#   14/1    0.000    0.000    0.159    0.159 /var/lib/awx/venv/awx/lib64/python3.9/site-packages/django/core/handlers/exception.py:52(inner)

text_positions = (0, 9, 18, 27, 36, 45)

data = {}


for file in os.listdir(DIR):
    if not file.endswith('.pstats'):
        continue
    path = os.path.join(DIR, file)
    # print(path)
    with open(path, 'r') as f:
        text = f.read()
    for line in text.split('\n')[6:]:
        if not line.strip():
            continue
        elements = []
        number_text = line[:45]
        elements = number_text.split()
        # for start_pos, end_pos in zip(text_positions[:-1], text_positions[1:]):
        #     elements.append(line[start_pos:end_pos].strip())
        line_id = line[45:].strip()
        # print((line_id, elements))
        cumtime = float(elements[3])
        if not cumtime:
            continue
        data.setdefault(line_id, 0.0)
        data[line_id] += cumtime
    # print(text.split('\n')[6])

sorted_data = sorted([(k, v) for k, v in data.items()], key=lambda x: -x[1])

for line_id, time in sorted_data:
    if time < 0.01:
        continue
    print(f'  {time:.2f} {line_id}')

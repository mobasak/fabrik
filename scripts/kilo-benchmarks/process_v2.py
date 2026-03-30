with open("process.py") as f:
    lines = f.readlines()

data_str = ""
in_data = False
for line in lines:
    if line.strip() == "data = [":
        in_data = True
        data_str += line
    elif in_data:
        data_str += line
        if line.strip() == "]":
            in_data = False
            break

# Re-read raw data
# We can just extract it since we need to do exactly the prompt logic

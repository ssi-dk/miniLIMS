
def expect(jsondict, expected_list):
    missing = []
    for key in expected_list:
        if key not in jsondict:
            missing.append(key)
    return missing

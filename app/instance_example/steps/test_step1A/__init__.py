# Template for a step

step = {
        "name": 'test_step1A',
        "display_name": "disp_test1",
        "category": "test_step1",
        "version": "1.0",
        "details": {
            "description": "asdasdasd"
        },
        "requirements": {
            "sample": {
                "steps": ["step1"]
            }
        },
        "input_output": [
            {
                "name": "script",
                "display_name": "This is script 1",
                "script": "script_input1",
                "stage": "stepstart",
                "output_values": [
                    {
                        "name": "out1",
                        "display_name": "output1",
                        "scope": "all",
                        "type_": "int"
                    }
                ]
            },
            {
                "name": "output1",
                "display_name": "This is output 1",
                "script": "script_output1",
                "stage": "stepend",
                "input_values": [
                    {
                        "name": "in1",
                        "display_name": "input1",
                        "scope": "all",
                        "type_": "int",
                        "showuser": True
                    }
                ]
            }
        ]
    }



def script_input1():
    print("executing input1")
    return {
        "all": {
            "out1": 123123123
        },
        "samples": {}
    }

def script_output1(in1):
    print("in1:", in1)
    return {}

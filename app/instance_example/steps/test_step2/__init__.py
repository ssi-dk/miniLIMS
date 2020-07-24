# Template for a step

step = {
        "name": 'test_step2',
        "display_name": "disp_test2",
        "category": "test_step2",
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
                        "type_": "number"
                    }
                ],
                "input_values": [
                    {
                        "name": "test_step1.in1",
                        "display_name": "input1",
                        "scope": "all",
                        "type_": "int",
                        "showuser": False
                    },
                    {
                        "name": "test_step1.out1",
                        "display_name": "input2",
                        "scope": "all",
                        "type_": "int",
                        "showuser": False
                    }
                ]
            },
        ]
    }



def script_input1(test_step1_in1, test_step1_out1):
    print("executing input1")
    return {
        "all": {
            "value1": "Text 1"
        },
        "samples": {}
    }

def script_output1(in1):
    print("in1:", in1)
    return {}

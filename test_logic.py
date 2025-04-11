from automation.rule.jsonlogic import jsonLogic


def testLogic():
    """Test the logic with the given data"""
    data = {
    "id": 3,
    "name": "Antoine-VM-Windows",
    "description": "Computer System Product",
    "serial": "00330-80000-00000-AA575",
    "osname": "Microsoft Windows 10 Pro",
    "osversion": "10.0.19045",
    "uuid": "C1C7673E-DFF9-4445-9EDF-590461BAE36A",
    "srcip": "10.0.2.15",
    "srcmac": "08-00-27-23-E5-4D",
    "domain": "WORKGROUP",
    "template": 1,
    "last_update": "2024-01-29T14:48:02.108415Z"
}

    logic = {
    "and": [
        {
            "and": [
                {
                    "==": [
                        {
                            "var": "osname"
                        },
                        "Microsoft Windows 10 Pro"
                    ]
                },
                {
                    "==": [
                        {
                            "var": "osversion"
                        },
                        "10.0.19045"
                    ]
                }
            ]
        },
        {
            #"in": ["WORKGROUP", {"var": "domain"}]
            "in": [{"var": "domain"}, "WORKGROUP2"]
            
        }
    ]
}
    return jsonLogic(logic, data)


if __name__ == "__main__":
    truc = testLogic()
    print(truc)

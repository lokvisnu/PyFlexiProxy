from schema import Schema, And, Use, Optional,Regex,SchemaError

DEFAULT_PORT = 8080
VALIDATE_HOST_NAME_REG_EX = r"^([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])(\.([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\-]{0,61}[a-zA-Z0-9]))*$"
VALIDATE_DOMAIN_NAME_REG_EX = r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.[A-Za-z]{2,})+$"

ConfigurationSchema = Schema(
    {
        "server" : {
            Optional("port",DEFAULT_PORT):And(int),
            "host":And(Use(str),Regex(VALIDATE_HOST_NAME_REG_EX)),
            "domain":Use(str),
            "workers":Use(int),
            Optional("headers",list()):[
                {
                    "key":Use(str),
                    "value":Use(str)
                }
            ],
            "upstreams":[
                {
                    "id":Use(str),
                    "host":And(Use(str),Regex(VALIDATE_HOST_NAME_REG_EX)),
                    "port":And(int)
                }
            ],
            "paths":[
                {
                    "path":Use(str),
                    "upstreams":[
                        Use(str)
                    ]
                }
            ]
        }
})

def validate_config (config_data):
    try:
        validated_data = ConfigurationSchema.validate(config_data)
        return validated_data
    except SchemaError as e:
        raise
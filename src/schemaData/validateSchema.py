from schema import SchemaError
from .schemaStructures import ConfigurationSchema

def validateConfig (config_data):
    try:
        validated_data = ConfigurationSchema.validate(config_data)
        return validated_data
    except SchemaError as e:
        print(e);
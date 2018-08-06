import os
import pickle
import pkg_resources

def get_schema(schema):
    schema_file = pkg_resources.resource_filename("seispy.pandas",
                                                  os.path.join("data",
                                                               "schemas",
                                                               "%s.pkl" % schema)
                                                 )
    ext_file = pkg_resources.resource_filename("seispy.pandas",
                                               os.path.join("data",
                                                            "schemas",
                                                            "%s.ext.pkl" % schema)
                                              )
    with open(schema_file, "rb") as inf:
        schema_data = pickle.load(inf)

    if os.path.isfile(ext_file):
        with open(ext_file, "rb") as inf:
            ext_data = pickle.load(inf)
        for attr in ext_data["Attributes"]:
            schema_data["Attributes"][attr] = ext_data["Attributes"][attr]
        for rel in ext_data["Relations"]:
            schema_data["Relations"][rel] = ext_data["Relations"][rel]
    return(schema_data)

def document(schema):
    blob = "# %s\n" % schema
    schema = get_schema(schema)
    blob += "## Relations/tables\n"
    for name in sorted(schema["Relations"]):
        blob += "### %s\n" % name
        blob += ", ".join(schema["Relations"][name]) + "\n"
    blob += "## Attributes/fields\n"
    blob += "field|dtype|format|null|width\n"
    blob += "---|---|---|---|---\n"
    for name in schema["Attributes"]:
        attr = schema["Attributes"][name]
        blob += name + "|"
        blob += str(attr["dtype"]).replace("<class '", "").replace("'>", "") + "|"
        blob += attr["format"] + "|"
        blob += str(attr["null"]) + "|"
        blob += str(attr["width"]) + "\n"
    return(blob)
        

"""TAKATAK Studio production request pack v1, creative data only."""
import re

MAX_PACK_BYTES=16384

def text(value,limit,allow_empty=False):
    if not isinstance(value,str):
        raise ValueError("Invalid creative field")
    clean=re.sub(r"[\x00-\x1f\x7f]"," ",value).strip()
    # Match the upstream TypeScript contract's UTF-16 length.
    if (not clean and not allow_empty) or len(clean.encode("utf-16-le"))//2>limit:
        raise ValueError("Invalid creative field length")
    return clean

def parse_brief(value):
    if not isinstance(value,dict):
        raise ValueError("Invalid brief")
    language=value.get("language")
    if language not in ("en","fr"):
        raise ValueError("Invalid brief language")
    characters=value.get("characters")
    if not isinstance(characters,list) or len(characters)>3:
        raise ValueError("Invalid character list")
    clean=[]
    for item in characters:
        if not isinstance(item,dict):
            raise ValueError("Invalid character")
        name=text(item.get("name"),60)
        if any(c["name"].lower()==name.lower() for c in clean):
            raise ValueError("Duplicate character")
        profile=text(item.get("profile"),250,allow_empty=True)
        clean.append({"name":name,"profile":profile})
    return {"title":text(value.get("title"),120),"brief":text(value.get("brief"),1000),
            "audience":text(value.get("audience"),150),"language":language,"characters":clean}

def parse_pack(value):
    if not isinstance(value,dict) or value.get("studio")!="TAKATAKSTUDIO" or type(value.get("version")) is not int or value["version"]!=1 or value.get("kind")!="production_request_pack":
        raise ValueError("Unsupported Studio pack")
    p=value.get("project")
    if not isinstance(p,dict):
        raise ValueError("Invalid project")
    language=p.get("language")
    if language=="English":
        language="en"
    elif language=="French":
        language="fr"
    return parse_brief({"title":p.get("title"),"brief":p.get("brief"),"audience":p.get("audience"),
                        "language":language,"characters":value.get("characters")})

def director_prompt(brief):
    # Creative data, not identity, authorization or execution instructions.
    lang="Canadian French" if brief["language"]=="fr" else "English"
    return f"Create a video edit for: {brief['title']}. Language: {lang}. Audience: {brief['audience']}. Creative brief: {brief['brief']}"

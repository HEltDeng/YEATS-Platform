from pydantic import BaseModel, Field, ConfigDict

class Input(BaseModel): model_config=ConfigDict(extra='forbid')
class Login(Input): code:str=Field(min_length=1,max_length=256)
class Phone(Input): code:str=Field(min_length=1,max_length=256)
class Profile(Input): name:str=Field(min_length=1,max_length=40)
class Submit(Input):
    text:str=Field(default='',max_length=4000)
    attachment_ids:list[str]=Field(default_factory=list,max_length=30)
    idempotency_key:str=Field(min_length=16,max_length=80)
class Ask(Input):
    text:str=Field(min_length=1,max_length=2000)
    idempotency_key:str=Field(min_length=16,max_length=80)
class Apply(Input):
    reason:str=Field(default='',max_length=1000)
    idempotency_key:str=Field(min_length=16,max_length=80)
class Ticket(Input):
    student_id:str|None=None
    purpose:str=Field(pattern='^(preview|download|play)$')
class Consent(Input): choices:dict[str,str]
class Watch(Input): seconds:int=Field(ge=0,le=60)

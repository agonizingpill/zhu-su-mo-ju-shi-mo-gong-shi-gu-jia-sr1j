from pydantic import BaseModel,Field,ConfigDict
class RateVersionInput(BaseModel):
    model_config=ConfigDict(str_strip_whitespace=True)
    machine:str=Field(min_length=1,max_length=40)
    rate:float=Field(gt=0,le=10000)
    note:str=Field(default='',max_length=300)

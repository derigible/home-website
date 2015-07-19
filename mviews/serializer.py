"""
A package that is committed to taking the best of the Django ORM and fixing
the poor serialization efforts

It also attempts to intelligently determine what serialization to use depending
on the Accept header passed in to the service. If no Accept header is
found, or the type is not supported, will default to application/json.

To make this possible, a few more attributes must be added to a model:

    1) the base queryset for the model must be added as the qs attribute
"""


import json
from xml.etree import ElementTree
from collections import OrderedDict as od

from django.http.response import HttpResponse as resp
from django.core.serializers.json import DjangoJSONEncoder as djson
from django.db import models
from django.db.models.manager import Manager


def _output_raw(field):
    """
    Helper function to output data in the correct format 
    """
    pass

def _serialize_xml(mview, qs, expand):
    """
    Serialize a queryset into xml.
    """
    raise NotImplementedError("Parsing of query sets to xml not yet supported.")

def foreign_obj_to_dict(mview, fobj, depth):
    print("*******************")
    print("getting new obj: {}".format(fobj))
    if hasattr(fobj, "public_fields"):
        fields = fobj.public_fields
    else:
        fields = fobj._meta.get_all_field_names()
    fkDict = {}
    for f in fields:
        print(type(f), f)
#         try:
        fo = getattr(fobj, f)
#         except AttributeError:
#             fo = fobj.serializable_value(f)
        print()
        print(f)
        if isinstance(fo, Manager):
            print("manager")
            if mview.sdepth >= depth:
                fkDict[f] = foreign_rel_to_dict(mview, fo, depth + 1)
#             else:
#                 fkDict[f] = fobj.serializable_value(f)
        elif isinstance(fo, models.Model):
            print("model")
            if mview.sdepth >= depth:
                fkDict[f] = foreign_obj_to_dict(mview, fo, depth + 1)
#             else:
#                 fkDict[f] = fobj.serializable_value(f + "_id")
        else:
            print("other")
            fkDict[f] = fobj.serializable_value(f)
    return fkDict

def foreign_rel_to_dict(mview, frel, depth):
    fks = []
    for fk in frel.all():
        if mview.sdepth >= depth:
            fkDict = foreign_obj_to_dict(mview, fk, depth + 1)
            fks.append(fkDict)
    return fks

def _serialize_json(mview, qs):
    """
    Serialize a queryset into json. If expand is true, will treat the qs as 
    models; if false, will treat as dictionaries.
    """
    
    expand = mview.expand
    if mview.fields:
        #get all of the field names specified and in the model
        field_names = set(mview.fields).intersection(mview.field_names)
    else:
        field_names = mview.field_names
    if not expand:
        if len(qs) > 1:
            rslt = json.dumps({"data" : list(qs)}, cls=djson)
        else:
            rslt = json.dumps(list(qs)[0] if len(qs) > 0 else {}, cls=djson)
    else:
        rslt = {"data" : []}
        vals = rslt["data"]
        for m in qs:
            obj = {}
            vals.append(obj)
            for f in field_names:
                field = getattr(m, f)
                # Check if has the all() method. If so, is a manager.
                if isinstance(field, Manager):
                    print("Getting the foreign values of {}".format(f))
                    obj[f] = foreign_rel_to_dict(mview, field, 1) 
                elif isinstance(field, models.Model):
                    print("Getting the object values of {}".format(f))
                    obj[f] = foreign_obj_to_dict(mview, field, 1)                     
                else:
                    obj[f] = field
        print(rslt)
        rslt = json.dumps(rslt, cls=djson)
        
    return rslt

def serialize(mview, qs, serializer=None):
    """
    One of two public methods of this package. Pass in the ModelAsView object 
    and the qs you wish to serialize with the model it is querying
    and the return value will be either json or xml. Other values are not 
    currently supported, but a serializer that accepts a query set  
    as argument may be used by passing it in through the serializer keyword.
    
    It is assumed that the models have added the proper attributes to fit in
    with this packages idea of what a model should look like.
    
    @param mview: the mview object
    @param qs: the queryset being parsed
    @param serializer: the serializer to use
    @param expand: expand the return to include foreign fields and m2m
    @return the serialized string of queryset qs
    """
    if serializer is not None:
        return serializer(qs)
    if "xml" in mview.accept:
        return _serialize_xml(qs)
    return _serialize_json(mview, qs)
    
def serialize_to_response(mview, qs, serializer=None, expand=False):
    """
    One of two public methods of this package. Pass in the ModelAsView object
    and the qs you wish to serialize and the return value will be either json
    or xml. Other values are not currently supported, but a serializer that
    accepts a model as a single argument may be used by passing it in
    through the serializer keyword.
    
    The Accept header is used to set the content_type of the response and
    a django.http.response.HttpResponse object is returned. If you pass in
    a custom serializer, you must set the response's content_type to the
    correct content_type manually.
    
    It is assumed that the models have added the proper attributes to fit in
    with this packages idea of what a model should look like.
    
    @param mview: the mview object
    @param qs: the queryset being parsed
    @param serializer: the serializer to use
    @param expand: expand the return to include foreign fields and m2m
    @return a response object with the serialized data as payload
    """
    retData = serialize(mview, qs, serializer, expand)
    if "xml" in mview.accept:
        accept = "application/xml"
    else:
        accept = "application/json"
    return resp(retData, content_type=accept)